# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Execution interface and discovery metadata shared by ForeRSI workflows."""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Sequence
from contextlib import AsyncExitStack
from pathlib import Path
from typing import ClassVar

from fore_rsi.config import AgentConfig, WorkflowConfig
from fore_rsi.rsi_workflows.agent_runtimes.tool_mcp import ToolMcpHost
from fore_rsi.rsi_workflows.base_agent import AgentState, BaseAgent
from fore_rsi.rsi_workflows.workflow_runtimes.agent_scheduler import AgentScheduler
from fore_rsi.rsi_workflows.workgroup import Workgroup


class BaseWorkflow(ABC):
    """Base class for named workflows invoked and supervised by WorkflowRunner."""

    # Name selected by --workflow, independent of the module and class names.
    workflow_name: ClassVar[str]
    agent_roles: ClassVar[dict[str, type[BaseAgent]]]

    def __init__(self, config: WorkflowConfig, session_directory: Path) -> None:
        """Bind workflow settings and storage, then initialize scheduling and workgroups."""
        self.config = config
        self.session_directory = session_directory
        self.tool_mcp_host = ToolMcpHost()
        self.agent_scheduler = AgentScheduler(
            role_classes=self.agent_roles,
        )
        # Workflow owns global Agent and Workgroup naming; Scheduler owns active reservations.
        self.agent_name_counters: dict[str, int] = {}
        self.workgroup_sequence = 0
        self.global_workgroup = Workgroup(WorkflowConfig.GLOBAL_WORKGROUP_NAME)
        self.workgroups: dict[str, Workgroup] = {
            self.global_workgroup.workgroup_name: self.global_workgroup,
        }

    @abstractmethod
    async def run_workflow(self, workspace_id: str) -> None:
        """Execute this workflow in the workspace prepared by WorkflowRunner."""
        ...

    async def close_workflow(self) -> None:
        """Close the workflow's agents and release their reservations before the runner records the outcome."""
        for workgroup_name, workgroup in tuple(self.workgroups.items()):
            for agent_name in tuple(workgroup.agents):
                await self.close_agent(workgroup_name, agent_name)

    async def create_workgroup(
        self,
        *,
        workspace_id: str,
        workgroup_name: str | None = None,
        agents: Sequence[tuple[type[BaseAgent], AgentConfig]] = (),
    ) -> Workgroup:
        """Register a group and return it when all requested members are ready in the workspace."""
        if workgroup_name is None:
            self.workgroup_sequence += 1
            workgroup_name = f"workgroup-{self.workgroup_sequence}"
        if workgroup_name in self.workgroups:
            raise ValueError(
                f"Workgroup {workgroup_name!r} already exists in this workflow."
            )
        workgroup = Workgroup(workgroup_name)
        self.workgroups[workgroup_name] = workgroup
        if not agents:
            return workgroup

        member_starts: dict[str, asyncio.Task[BaseAgent]] = {}
        try:
            async with asyncio.TaskGroup() as startup:
                for agent_class, agent_config in agents:
                    agent_name = self.next_agent_name(agent_class.role_name)
                    member_starts[agent_name] = startup.create_task(
                        self.agent_scheduler.create_agent(
                            agent_class=agent_class,
                            agent_name=agent_name,
                            workgroup_name=workgroup_name,
                            agent_config=agent_config,
                            workflow=self,
                            workspace_id=workspace_id,
                            is_entry_agent=False,
                        )
                    )
            # TaskGroup does not raise for a child that was independently cancelled.
            for member_start in member_starts.values():
                member_start.result()
        except BaseException:
            # Only forget a member after it closes; workflow shutdown can retry failed closes.
            async def rollback_member(agent_name: str) -> None:
                await self.close_agent(workgroup.workgroup_name, agent_name)
                workgroup.agents.pop(agent_name, None)

            async with AsyncExitStack() as cleanup:
                for agent_name in member_starts:
                    cleanup.push_async_callback(rollback_member, agent_name)
            if not workgroup.agents:
                del self.workgroups[workgroup_name]
            raise
        return workgroup

    def next_agent_name(self, role_name: str) -> str:
        """Return a workflow-wide unique role-based instance name."""
        role_prefix = role_name.lower()
        agent_index = self.agent_name_counters.get(role_prefix, 0) + 1
        existing_agent_names = {
            agent.agent_name
            for workgroup in self.workgroups.values()
            for agent in workgroup.agents.values()
        }
        while f"{role_prefix}-{agent_index}" in existing_agent_names:
            agent_index += 1
        self.agent_name_counters[role_prefix] = agent_index
        return f"{role_prefix}-{agent_index}"

    async def close_agent(self, workgroup_name: str, agent_name: str) -> None:
        """Retire the member and release its slot without removing its workgroup entry."""
        workgroup = self.workgroups.get(workgroup_name)
        agent = workgroup.agents.get(agent_name) if workgroup is not None else None
        if agent is None:
            return
        agent.state = AgentState.RETIRED
        try:
            await agent.agent_runtime.close()
        finally:
            await self.agent_scheduler.release(agent)
