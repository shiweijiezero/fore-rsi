# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Accept task submissions from the Coordinator and keep a revision history for each workflow session."""

import asyncio
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from fore_rsi.rsi_workflows.types import RequiredText
from fore_rsi.rsi_workflows.workflow_runtimes.agent_scheduler import AgentAllocation


class ExperimentResources(BaseModel):
    """Total measurement budget and the individual resources the team can divide among its members."""

    model_config = ConfigDict(extra="allow", strict=True)
    units: dict[RequiredText, RequiredText] = Field(default_factory=dict, description=(
        "Map each independently assignable resource to its scope, using one stable ID per unit across the team. "
        "Derive units from the machine description, not from team size: eight GPUs on one host give eight "
        "device slots, not three preassigned environments. Keep shared limits here as part of the total budget. "
        "If no independent units are known, the team shares one exclusive allocation."
    ))


class Resource(BaseModel):
    """Declared resource budgets for deployment and the complete experiment set."""

    deployment_resources: dict[str, object]
    experiment_resources: ExperimentResources


class TaskConstraints(BaseModel):
    """Task constraints grouped by their purpose."""

    common_constraints: dict[str, object]
    resources: Resource
    stop_conditions: list[str]
    time_budget: int | float | None


class AgentTeam(BaseModel):
    """Role allocations and collaboration notes requested for the task's Agent team."""

    roles: dict[RequiredText, list[AgentAllocation]]
    watchdog_interval_seconds: PositiveInt | None = Field(description=(
        "Seconds between Watchdog progress reviews. Use a positive interval when the Watchdog is enabled; "
        "null is allowed when the role is absent or paused."
    ))
    team_comments: list[str]


class TaskSubmission(BaseModel):
    """The task parsed by the Coordinator."""

    # Pydantic validation policy; this is not part of the submitted task payload.
    model_config = ConfigDict(extra="forbid", strict=True)

    goal: RequiredText = Field(description="What the task should achieve.")
    constraints: TaskConstraints
    agent_team: AgentTeam
    environment_variables: dict[RequiredText, str] = Field(
        description="Environment variable names and values required by the task."
    )
    task_comments: list[str]


@dataclass(frozen=True)
class TaskRevision:
    """One published task and the file that continues to identify it after later submissions."""

    revision_number: int
    revision_file_path: Path
    task_submission: TaskSubmission


class Task:
    """Own task revisions for one workflow session."""

    def __init__(self, session_directory: Path) -> None:
        """Create task history state for one new workflow session."""
        self.session_directory = session_directory
        self.task_revisions: list[TaskRevision] = []
        self.revision_changed = asyncio.Event()

    @property
    def current_task(self) -> TaskRevision | None:
        """Return the latest revision submitted during this Workflow run."""
        return self.task_revisions[-1] if self.task_revisions else None

    def publish_task(self, task_submission: TaskSubmission) -> TaskRevision:
        """Persist a changed submission, or return the current revision on an identical replay."""
        current = self.current_task
        if current is not None and current.task_submission == task_submission:
            return current
        revision = self.write_task_revision(len(self.task_revisions) + 1, task_submission)
        self.task_revisions.append(revision)
        self.revision_changed.set()
        self.revision_changed = asyncio.Event()
        return revision

    def write_task_revision(
        self, revision_number: int, task_submission: TaskSubmission
    ) -> TaskRevision:
        """Write one TaskRevision file for this workflow session."""
        self.session_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination = self.session_directory / f"task_revision_{revision_number}.json"
        destination.write_text(
            task_submission.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        return TaskRevision(
            revision_number=revision_number,
            revision_file_path=destination,
            task_submission=task_submission,
        )
