# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Execution interface and discovery metadata shared by ForeRSI workflows."""

import asyncio
from abc import ABC, abstractmethod
from contextlib import AsyncExitStack
from pathlib import Path
from typing import ClassVar

from fore_rsi.config import AgentConfig, WorkflowConfig
from fore_rsi.rsi_workflows.agent_runtimes.tool_mcp import ToolMcpHost
from fore_rsi.rsi_workflows.base_agent import BaseAgent
from fore_rsi.rsi_workflows.types import ExplorationPool
from fore_rsi.rsi_workflows.workflow_runtimes.agent_scheduler import AgentScheduler
from fore_rsi.rsi_workflows.workflow_runtimes.task import TaskRevision
from fore_rsi.rsi_workflows.workflow_runtimes.workgroup import Workgroups


class BaseWorkflow(ABC):
    """Base class for named workflows invoked and supervised by WorkflowRunner."""

    # Name selected by --workflow, independent of the module and class names.
    workflow_name: ClassVar[str]
    agent_roles: ClassVar[dict[str, type[BaseAgent]]]

    def __init__(self, config: WorkflowConfig, session_directory: Path) -> None:
        """Bind workflow settings and storage, then initialize scheduling and workgroups."""
        self.config = config
        self.default_agent_config = AgentConfig(harness=config.harness_or_default)
        self.session_directory = session_directory
        self.task_revision_queue: asyncio.Queue[TaskRevision] = asyncio.Queue()
        self.exploration_pool = ExplorationPool()
        self.task_submissions_closed = False
        self.subflow_tasks = asyncio.TaskGroup()
        self.tool_mcp_host = ToolMcpHost()
        self.agent_scheduler = AgentScheduler(
            role_classes=self.agent_roles,
        )
        self.workgroups = Workgroups(self)

    async def run(self, workspace_id: str) -> None:
        """Run the workflow to completion and release its agents after all subflows exit."""
        try:
            async with self.subflow_tasks:
                try:
                    await self.run_workflow(workspace_id)
                finally:
                    await self.close_workflow()
        finally:
            async with AsyncExitStack() as cleanup:
                for workgroup in self.workgroups.values():
                    cleanup.push_async_callback(workgroup.close_members)

    @abstractmethod
    async def run_workflow(self, workspace_id: str) -> None:
        """Implement the workflow's steps in the prepared workspace; return when its work is done."""
        ...

    async def close_workflow(self) -> None:
        """Stop new submissions and let listeners finish processing queued revisions."""
        self.task_submissions_closed = True
        self.task_revision_queue.shutdown()
