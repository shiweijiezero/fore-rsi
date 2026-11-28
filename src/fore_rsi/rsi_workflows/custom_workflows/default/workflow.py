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
from .subflows.experiment_subflow import ExperimentSubflow
from .subflows.exploration_subflow import ExplorationSubflow
from .subflows.watchdog_subflow import run_watchdog_subflow


class DefaultWorkflow(BaseWorkflow):
    """Run a general-purpose team workflow for tasks such as inference optimization."""

    workflow_name = "default"

    exploration_roles = (ExplorerAgent, CheckerAgent)
    agent_roles: ClassVar[dict[str, type[BaseAgent]]] = {
        role.role_name: role for role in (CoordinatorAgent, *exploration_roles, ExperimenterAgent, WatchdogAgent)
    }

    def __init__(self, config: WorkflowConfig, session_directory: Path) -> None:
        """Prepare the session's task history without starting any agents."""
        super().__init__(config, session_directory)
        self.task = Task(session_directory)
        self.exploration: ExplorationSubflow
        self.experiments: ExperimentSubflow

    async def run_workflow(self, workspace_id: str) -> None:
        """Start the team on the first submission and deliver later revisions while it runs.

        START --> create Coordinator --> receive_task

        [first task accepted] --> start concurrent subflows
            +-- exploration --> review directions and candidates --> submit approved experiments
            +-- experiments --> publish report on the item --> original group resumes analysis
            +-- task updates --> notify members of the latest revision
            +-- watchdog --> review progress when enabled

        [all exploration groups finished] --> stop experiment dispatch and watchdog --> END
        """
        self.exploration = ExplorationSubflow(self, workspace_id)
        self.experiments = ExperimentSubflow(self, workspace_id)
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
        self.subflow_tasks.create_task(self.receive_task_updates())
        experiment_dispatch = self.subflow_tasks.create_task(self.experiments.run())
        watchdog = self.subflow_tasks.create_task(run_watchdog_subflow(self, workspace_id))
        try:
            await self.exploration.run()  # Includes all measurements requested by the exploration groups.
        finally:
            experiment_dispatch.cancel()
            watchdog.cancel()

    async def receive_task(
        self,
        coordinator: CoordinatorAgent,
        *,
        task_file: Path | None = None,
    ) -> None:
        """Wait for the first submission, asking the Coordinator to parse the task file if supplied.

        [task file] --> parse_task --> request_submission
            +-- submitted --> wait_for_task_revision
            +-- attempts exhausted --> raise RuntimeError
        [no file] --> wait_for_task_revision

        wait_for_task_revision --> return on first submission
        """
        if task_file is not None and not await coordinator.parse_task(task_file):
            raise RuntimeError(
                f"{coordinator.agent_name} did not submit {task_file} after {self.config.max_attempts} attempts."
            )

        await self.task_revision_queue.get()

    async def receive_task_updates(self) -> None:
        """Relay the latest revision without interrupting a turn for an allocation-only change.

        wait for submission
            +-- same revision ------> wait again
            +-- only team or measurement allocation changed --> queue notice for next turn
            +-- requirements changed --> steer running members; notify others
            +-- queue drained and closed --> END
        """
        previous = self.task.task_revisions[0]
        while True:
            try:
                await self.task_revision_queue.get()
            except asyncio.QueueShutDown:
                return
            current = self.task.current_task
            assert current is not None
            if current is previous:
                continue
            # The experiment team applies new model slots and measurement resources after its runs drain.
            # Steering those native turns here would interrupt the work it is waiting to finish.
            allocation = {
                "agent_team": {"roles", "watchdog_interval_seconds"},
                "constraints": {"resources": {"experiment_resources"}},
            }
            changed_requirements = (current.task_submission.model_dump(exclude=allocation)
                                    != previous.task_submission.model_dump(exclude=allocation))
            await self.update_task_to_agents(current, steer=changed_requirements)
            previous = current

    async def update_task_to_agents(self, task_revision: TaskRevision, *, steer: bool) -> None:
        """Deliver requirements to live members; quota-only updates wait for their next prompt."""
        message = (
            f"Task revision {task_revision.revision_number} is available. "
            f"Read {task_revision.revision_file_path.resolve()} for the current requirements."
        )
        # Retained seeds still own their panes but do not take work or task revisions.
        for agent in tuple(self.agent_scheduler.active_agents):
            if agent not in self.agent_scheduler.active_agents:
                continue  # An earlier delivery may have yielded while this member left its slot.
            if steer and agent.state == AgentState.RUNNING:
                update = message
                if isinstance(agent, ExperimenterAgent):
                    update += (" Do not restart a measurement already issued. If its authorization or limits "
                               "changed, stop the affected work and report the actual outcome and cleanup status.")
                await agent.send_message(update, mode="steer")
            elif agent.state not in (AgentState.RETIRED, AgentState.FAILED):
                agent.add_to_inbox(message)
