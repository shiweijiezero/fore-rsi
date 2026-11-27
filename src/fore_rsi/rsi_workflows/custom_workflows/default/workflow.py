# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Default workflow entry point and general-purpose collaboration stages."""

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import ClassVar

from fore_rsi.config import WorkflowConfig
from fore_rsi.rsi_workflows.base_agent import AgentState, BaseAgent
from fore_rsi.rsi_workflows.base_workflow import BaseWorkflow
from fore_rsi.rsi_workflows.workflow_runtimes.task import Task, TaskRevision

from .agents.checker import CheckerAgent
from .agents.coordinator import CoordinatorAgent
from .agents.experimenter import ExperimenterAgent
from .agents.explorer import ExplorerAgent
from .agents.watchdog import WatchdogAgent
from .subflows.experiment_subflow import run_experiment_subflow
from .subflows.exploration_subflow import run_exploration_subflow
from .subflows.watchdog_subflow import run_watchdog_subflow


class DefaultWorkflow(BaseWorkflow):
    """Run a general-purpose team workflow for tasks such as inference optimization."""

    workflow_name = "default"

    agent_roles: ClassVar[dict[str, type[BaseAgent]]] = {
        role.role_name: role
        for role in (
            CoordinatorAgent,
            ExplorerAgent,
            CheckerAgent,
            ExperimenterAgent,
            WatchdogAgent,
        )
    }

    def __init__(self, config: WorkflowConfig, session_directory: Path) -> None:
        """Prepare the session's task history without starting any agents."""
        super().__init__(config, session_directory)
        self.task = Task(session_directory)
        self.watchdog_task: asyncio.Task[None] | None = None

    async def run_workflow(self, workspace_id: str) -> None:
        """Start the team on the first submission and deliver later revisions while it runs.

        START --> create_agent[Coordinator] --> receive_task

        receive_task
              +--[exceed_limit_try] ---------> raise RuntimeError
              +--[first accepted submission]--+--> init_subflows
                                              +--> receive_task_updates

        [exploration and experiments finished] --> return
        """
        coordinator = await self.agent_scheduler.create_agent(
            agent_class=CoordinatorAgent,
            workgroup=self.workgroups.global_workgroup,
            agent_config=replace(
                self.default_agent_config,
                model=self.config.entry_model,
                effort=self.config.entry_effort,
            ),
            workflow=self,
            workspace_id=workspace_id,
            is_entry_agent=True,
        )
        await self.receive_task(coordinator, task_file=self.config.task)
        exploration, experiments = self.init_subflows(workspace_id)
        self.subflow_tasks.create_task(self.receive_task_updates())
        await exploration
        await experiments

    async def receive_task(
        self,
        coordinator: CoordinatorAgent,
        *,
        task_file: Path | None = None,
    ) -> None:
        """Wait for the first submission, asking the Coordinator to parse the task file if supplied.

        receive_task
              +--[task_file] --> parse_task --> wait_for_settle --> tool_submission_status
              +--[no_file] ----> wait_for_task_revision

        tool_submission_status
              +--[submitted] --------> wait_for_task_revision
              +--[not_submitted] ----> parse_task
              +--[exceed_limit_try] -> raise RuntimeError

        wait_for_task_revision --> return on first submission
        """
        if task_file is not None:
            status = "not_submitted"
            while status == "not_submitted":
                await coordinator.parse_task(task_file)
                await coordinator.wait_for_settle()
                status = coordinator.tool_submission_status(max_attempts=self.config.max_attempts)
            if status == "exceed_limit_try":
                raise RuntimeError(
                    f"{coordinator.agent_name} did not submit {task_file} "
                    f"after {self.config.max_attempts} attempts."
                )

        await self.task_revision_queue.get()

    def init_subflows(self, workspace_id: str) -> tuple[asyncio.Task[None], asyncio.Task[None]]:
        """Start the team and return the two tasks whose completion ends the workflow.

        init_subflows
              +--> run_exploration_subflow
              +--> run_experiment_subflow
              +--> run_watchdog_subflow
        """
        tasks = self.subflow_tasks
        exploration = tasks.create_task(run_exploration_subflow(self, workspace_id))
        experiments = tasks.create_task(run_experiment_subflow(self, workspace_id))
        self.watchdog_task = tasks.create_task(run_watchdog_subflow(self, workspace_id))
        return exploration, experiments

    async def receive_task_updates(self) -> None:
        """Notify agents on each accepted submission until the revision queue closes and drains.

        task_revision_queue.get
              +--[accepted] --> update_task_to_agents --> task_revision_queue.get
              +--[queue closed and empty] --> return
        """
        while True:
            try:
                task_revision = await self.task_revision_queue.get()
            except asyncio.QueueShutDown:
                return
            await self.update_task_to_agents(task_revision)

    async def update_task_to_agents(self, task_revision: TaskRevision) -> None:
        """Steer running agents to the task revision and leave it in the inboxes of other live members."""
        message = (
            f"Task revision {task_revision.revision_number} is available. "
            f"Read {task_revision.revision_file_path.resolve()} for the current requirements."
        )
        # Sending to a running agent yields control; take the recipient list before membership can change.
        members = [agent for workgroup in self.workgroups.values() for agent in workgroup.agents.values()]
        for agent in members:
            if agent.state == AgentState.RUNNING:
                await agent.send_message(message, mode="steer")
            elif agent.state not in (AgentState.RETIRED, AgentState.FAILED):
                agent.add_to_inbox(message)

    async def close_workflow(self) -> None:
        """Stop the watchdog and reject further task submissions when the workflow exits."""
        if self.watchdog_task is not None:
            self.watchdog_task.cancel()
        await super().close_workflow()
