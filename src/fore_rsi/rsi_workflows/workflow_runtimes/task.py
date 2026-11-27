# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Accept task submissions from the Coordinator and keep a revision history for each workflow session."""

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from fore_rsi.rsi_workflows.types import RequiredText
from fore_rsi.rsi_workflows.workflow_runtimes.agent_scheduler import AgentAllocation


class Resource(BaseModel):
    """Declared resource budgets for deployment and the complete experiment set."""

    deployment_resources: dict[str, object] = Field(default_factory=dict)
    experiment_resources: dict[str, object] = Field(default_factory=dict)


class TaskConstraints(BaseModel):
    """Task constraints grouped by their purpose."""

    common_constraints: dict[str, object] = Field(default_factory=dict)
    resources: Resource = Field(default_factory=Resource)
    stop_conditions: list[str] = Field(default_factory=list)
    time_budget: int | float | None = None


class AgentTeam(BaseModel):
    """Role allocations and collaboration notes requested for the task's Agent team."""

    roles: dict[RequiredText, list[AgentAllocation]] = Field(default_factory=dict)
    team_comments: list[str] = Field(default_factory=list)
    watchdog_interval_seconds: float = Field(default=3600, gt=0, allow_inf_nan=False)


class TaskSubmission(BaseModel):
    """The task parsed by the Coordinator."""

    # Pydantic validation policy; this is not part of the submitted task payload.
    model_config = ConfigDict(extra="forbid", strict=True)

    goal: RequiredText = Field(description="What the task should achieve.")
    constraints: TaskConstraints = Field(default_factory=TaskConstraints)
    agent_team: AgentTeam = Field(default_factory=AgentTeam)
    environment_variables: dict[RequiredText, str] = Field(
        default_factory=dict,
        description="Environment variable names and values required by the task.",
    )
    task_comments: list[str] = Field(default_factory=list)


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
