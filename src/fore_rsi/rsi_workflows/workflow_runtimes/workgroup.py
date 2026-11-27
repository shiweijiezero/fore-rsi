# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Workgroup membership and startup for a workflow's agents."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator, Mapping, Sequence
from contextlib import AsyncExitStack
from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fore_rsi.rsi_workflows.base_agent import BaseAgent
    from fore_rsi.rsi_workflows.base_workflow import BaseWorkflow
    from fore_rsi.rsi_workflows.workflow_runtimes.task import TaskRevision


class Workgroup:
    """Own the agent instances belonging to one workgroup."""

    def __init__(self, workgroup_name: str) -> None:
        """Initialize an empty workgroup."""
        self.workgroup_name = workgroup_name
        self.agents: dict[str, BaseAgent] = {}

    async def start_members(
        self,
        workflow: BaseWorkflow,
        agents: Sequence[type[BaseAgent]],
        *,
        workspace_id: str,
        task_revision: TaskRevision | None,
    ) -> None:
        """Start members concurrently using each role's first allocation or the workflow defaults.

        If startup fails, retire only members from this batch, leaving other members in place.
        """
        roles = task_revision.task_submission.agent_team.roles if task_revision is not None else {}
        starts: list[asyncio.Task[BaseAgent]] = []
        try:
            async with asyncio.TaskGroup() as startup:
                for role in agents:
                    config = workflow.default_agent_config
                    if allocations := roles.get(role.role_name):
                        first = allocations[0]
                        config = replace(config, model=first.model, effort=first.effort)
                    task = startup.create_task(
                        workflow.agent_scheduler.create_agent(
                            agent_class=role,
                            workgroup=self,
                            agent_config=config,
                            workflow=workflow,
                            workspace_id=workspace_id,
                            is_entry_agent=False,
                        )
                    )
                    starts.append(task)
            # A TaskGroup can exit normally with a cancelled child; every member must be ready.
            for task in starts:
                task.result()
        except BaseException:
            async with AsyncExitStack() as cleanup:
                for task in starts:
                    if not task.cancelled() and task.exception() is None:
                        cleanup.push_async_callback(self.discard_member, task.result())
            raise

    async def close_members(self) -> None:
        """Close every current member, leaving only those that failed to close registered for retry."""
        async with AsyncExitStack() as cleanup:
            for agent in self.agents.values():
                cleanup.push_async_callback(self.discard_member, agent)

    async def discard_member(self, agent: BaseAgent) -> None:
        """Remove a member from the workgroup only after it closes successfully."""
        await agent.close()
        self.agents.pop(agent.agent_name, None)


class Workgroups(Mapping[str, Workgroup]):
    """Create and look up the named workgroups belonging to one workflow."""

    def __init__(self, workflow: BaseWorkflow) -> None:
        """Register the workflow's global workgroup before any agents start."""
        self.workflow = workflow
        self.workgroup_sequence = 0
        self.global_workgroup = Workgroup(workflow.config.GLOBAL_WORKGROUP_NAME)
        self.workgroups_by_name = {self.global_workgroup.workgroup_name: self.global_workgroup}

    def __getitem__(self, workgroup_name: str) -> Workgroup:
        return self.workgroups_by_name[workgroup_name]

    def __iter__(self) -> Iterator[str]:
        return iter(self.workgroups_by_name)

    def __len__(self) -> int:
        return len(self.workgroups_by_name)

    async def create(
        self,
        *,
        workspace_id: str,
        workgroup_name: str | None = None,
        agents: Sequence[type[BaseAgent]] = (),
        task_revision: TaskRevision | None = None,
    ) -> Workgroup:
        """Register an empty workgroup or start its initial members before returning it."""
        if workgroup_name is None:
            while True:
                self.workgroup_sequence += 1
                workgroup_name = f"workgroup-{self.workgroup_sequence}"
                if workgroup_name not in self.workgroups_by_name:
                    break
        elif workgroup_name in self.workgroups_by_name:
            raise ValueError(f"Workgroup {workgroup_name!r} already exists in this workflow.")

        workgroup = Workgroup(workgroup_name)
        self.workgroups_by_name[workgroup_name] = workgroup
        if agents:
            try:
                await workgroup.start_members(
                    self.workflow, agents, workspace_id=workspace_id, task_revision=task_revision
                )
            except BaseException:
                # Keep the workgroup reachable for shutdown if a member failed to close.
                if not workgroup.agents:
                    del self.workgroups_by_name[workgroup_name]
                raise
        return workgroup
