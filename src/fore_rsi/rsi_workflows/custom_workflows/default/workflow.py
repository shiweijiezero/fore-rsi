# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Default workflow entry point and general-purpose collaboration stages."""

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import ClassVar

from loguru import logger

from fore_rsi.config import WorkflowConfig
from fore_rsi.rsi_workflows.base_agent import AgentState, BaseAgent
from fore_rsi.rsi_workflows.base_workflow import BaseWorkflow
from fore_rsi.rsi_workflows.workflow_runtimes.task import (
    Task,
    TaskRevision,
    TaskSubmission,
)

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
        for role in (CoordinatorAgent, ExplorerAgent, CheckerAgent, ExperimenterAgent, WatchdogAgent)
    }

    def __init__(self, config: WorkflowConfig, session_directory: Path) -> None:
        """Create task intake state without starting native Agent execution."""
        super().__init__(config, session_directory)
        self.task = Task(session_directory)
        self.task_revision_queue: asyncio.Queue[TaskRevision] = asyncio.Queue()
        self.accepting_tasks = True

    async def run_workflow(self, workspace_id: str) -> None:
        """Target execution flow for the default workflow in the runner's prepared workspace.

        START --> create_agent[Coordinator] --> receive_task

        receive_task
              +--[exceed_limit_try] --> END
              +--[first accepted submission]--+--> run_exploration_subflow
                                              +--> run_experiment_subflow
                                              +--> run_watchdog_subflow
                                              +--> receive_task_updates

        receive_task_updates:
            receive_task
                  +--[accepted] --> update_task_to_agents --> receive_task
                  +--[closed] ----> END

        submit_task (Coordinator MCP tool, including repeat submissions):
            accept_task --> validate role quotas --> publish_task --> apply quotas
                        --> enqueue TaskRevision --> return revision_number

        run_exploration_subflow --[submit_to_experiment]--> run_experiment_subflow
        run_experiment_subflow  --[experiment_result]-----> run_exploration_subflow
        """
        coordinator = await self.agent_scheduler.create_agent(
            agent_class=CoordinatorAgent,
            agent_name=self.next_agent_name(CoordinatorAgent.role_name),
            workgroup_name=self.global_workgroup.workgroup_name,
            agent_config=replace(
                self.default_agent_config,
                model=self.config.entry_model,
                effort=self.config.entry_effort,
            ),
            workflow=self,
            workspace_id=workspace_id,
            is_entry_agent=True,
        )
        # The tool has already published the revision and applied its quotas when this wait returns.
        task_revision = await self.receive_task(coordinator, task_file=self.config.task)
        if task_revision is None:
            return

        # These queues carry work between exploration and experiment. Task revisions arrive on the
        # Coordinator's separate queue, so applying a revision does not wait for an experiment result.
        experiment_pool = asyncio.Queue[str]()
        experiment_results = asyncio.Queue[str]()
        async with asyncio.TaskGroup() as workflow_tasks:
            exploration_task = workflow_tasks.create_task(
                run_exploration_subflow(
                    self,
                    workspace_id,
                    task_revision,
                    experiment_results=experiment_results,
                    submit_to_experiment=experiment_pool.put,
                )
            )
            experiment_task = workflow_tasks.create_task(
                run_experiment_subflow(
                    self,
                    workspace_id,
                    task_revision,
                    experiment_pool=experiment_pool,
                    publish_experiment_result=experiment_results.put,
                )
            )
            # When a producer finishes, its consumer can drain the queue and then stop waiting.
            exploration_task.add_done_callback(lambda _: experiment_pool.shutdown())
            experiment_task.add_done_callback(lambda _: experiment_results.shutdown())
            watchdog_task = workflow_tasks.create_task(
                run_watchdog_subflow(self, workspace_id, task_revision)
            )
            workflow_tasks.create_task(self.receive_task_updates(coordinator))

            # All four tasks are running. On normal completion, drain accepted submissions before
            # returning to WorkflowRunner for agent cleanup. TaskGroup handles failures and cancellation.
            try:
                await exploration_task
                await experiment_task
            finally:
                self.close_task_intake()
                watchdog_task.cancel()

    async def accept_task(self, submission: TaskSubmission) -> TaskRevision:
        """Handle submit_task: publish the task, apply its quotas and deliver one accepted revision.

        accept_task --> validate_role_quotas
                           +--[invalid] --> tool error
                           +--[valid] ----> publish_task --> apply quotas --> deliver TaskRevision
        """
        async with self.agent_scheduler.role_quota_update(submission.agent_team.roles):
            if not self.accepting_tasks:
                raise ValueError("Task intake is closed.")
            # No await between publication and delivery: concurrent tool calls keep publication order.
            task_revision = self.task.publish_task(submission)
            self.task_revision_queue.put_nowait(task_revision)
        return task_revision

    def close_task_intake(self) -> None:
        """Reject further submissions while allowing consumers to drain accepted revisions."""
        self.accepting_tasks = False
        self.task_revision_queue.shutdown()

    async def close_workflow(self) -> None:
        """Close task intake even if startup stopped before the subflows, then release the agents."""
        self.close_task_intake()
        await super().close_workflow()

    async def receive_task(
        self,
        coordinator: CoordinatorAgent,
        *,
        task_file: Path | None = None,
    ) -> TaskRevision | None:
        """Take one accepted revision, or return None if file parsing fails or intake closes.

        receive_task
              +--[task_file] --> parse_task --> wait_for_settle --> tool_submission_status
              +--[no_file] ----> wait_for_task_revision

        tool_submission_status
              +--[submitted] --------> wait_for_task_revision
              +--[not_submitted] ----> parse_task
              +--[exceed_limit_try] -> END

        wait_for_task_revision
              +--[received] --> return TaskRevision
              +--[closed] ----> END
        """
        if task_file is not None:
            status = "not_submitted"
            while status == "not_submitted":
                await coordinator.parse_task(task_file)
                await coordinator.wait_for_settle()
                status = coordinator.tool_submission_status(max_attempts=self.config.max_attempts)
            if status == "exceed_limit_try":
                logger.warning(
                    "{} did not submit {} after {} attempts",
                    coordinator.agent_name,
                    task_file,
                    self.config.max_attempts,
                )
                return None

        try:
            return await self.task_revision_queue.get()
        except asyncio.QueueShutDown:
            return None

    async def receive_task_updates(self, coordinator: CoordinatorAgent) -> None:
        """Notify agents on each accepted submission, even when it reuses the current task revision."""
        while (task_revision := await self.receive_task(coordinator)) is not None:
            await self.update_task_to_agents(task_revision)

    async def update_task_to_agents(self, task_revision: TaskRevision) -> None:
        """Steer running agents to the task revision and leave it in the inboxes of other live members."""
        message = (
            f"Task revision {task_revision.revision_number} is available. "
            f"Read {task_revision.revision_file_path.resolve()} for the current requirements."
        )
        # Sending to a running agent yields control; take the recipient list before membership can change.
        members = [agent for group in self.workgroups.values() for agent in group.agents.values()]
        for agent in members:
            if agent.state == AgentState.RUNNING:
                await agent.send_message(message, mode="steer")
            elif agent.state not in (AgentState.RETIRED, AgentState.FAILED):
                agent.add_to_inbox(message)
