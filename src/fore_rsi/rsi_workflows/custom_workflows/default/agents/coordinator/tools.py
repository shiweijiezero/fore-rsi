# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Tool implementations for the default workflow's Coordinator."""

from typing import TYPE_CHECKING

from mcp.server.mcpserver.exceptions import ToolError

from fore_rsi.rsi_workflows.types import RequiredText, SingleLineText
from fore_rsi.rsi_workflows.workflow_runtimes.task import TaskSubmission

from ..watchdog import WatchdogAgent

if TYPE_CHECKING:
    from fore_rsi.rsi_workflows.custom_workflows.default.workflow import DefaultWorkflow


async def submit_task(
    task_submission: TaskSubmission,
    *,
    workflow: "DefaultWorkflow",
) -> dict[str, int]:
    """Convert the user's requirements into a complete and accurate task declaration for the team.

    Submit every field on the first submission and on updates. Preserve unchanged requirements. Use empty
    collections where appropriate and null for time_budget when none was specified. In agent_team.roles,
    provide at least one model, effort, and quota allocation for both Explorer and Checker. Use quota 0
    to pause a role. Keep credentials in the host environment.

    The tool returns revision_number after publication and quota application. An unchanged declaration
    returns the same revision number and still signals a submission to the workflow.
    """
    roles = task_submission.agent_team.roles
    try:
        async with workflow.agent_scheduler.role_quota_update(roles):
            if workflow.task_submissions_closed:
                raise ValueError("This workflow is no longer accepting task submissions.")
            for role in workflow.exploration_roles:
                if not roles.get(role.role_name):
                    raise ValueError(f"agent_team.roles.{role.role_name} must contain at least one allocation.")
            watchdog_enabled = any(allocation.quota for allocation in roles.get(WatchdogAgent.role_name, ()))
            if watchdog_enabled and task_submission.agent_team.watchdog_interval_seconds is None:
                raise ValueError("agent_team.watchdog_interval_seconds is required when Watchdog is enabled.")
            workflow.experiments.validate_execution_mode(task_submission)
            previous = workflow.task.current_task
            task_revision = workflow.task.publish_task(task_submission)
    except ValueError as error:
        raise ToolError(f"Task declaration was not accepted: {error}") from error

    # A listener may start agents as soon as it receives the revision, so apply quotas first.
    workflow.experiments.request_team_update(previous, task_revision)
    workflow.task_revision_queue.put_nowait(task_revision)
    return {"revision_number": task_revision.revision_number}


async def request_exploration_direction(direction: RequiredText, *, workflow: "DefaultWorkflow") -> dict[str, str]:
    """Request an additional independent investigation and explain what the new group should examine.

    Use this for a concrete line of work, not to change parallelism. The assigned Explorer submits
    a proposed item, and its Checker reviews the direction before implementation.
    """
    if workflow.task.current_task is None or workflow.task_submissions_closed:
        raise ToolError("Submit a task to an active workflow before requesting another direction.")
    workflow.exploration.request_direction(direction)
    return {"requested_direction": direction}


async def relay_experiment_result(
    exploration_id: RequiredText, report: RequiredText, experiment_summary: SingleLineText, *, workflow: "DefaultWorkflow",
) -> dict[str, str]:
    """Return an external report and a short outcome label for the measured exploration item.

    Use one line for experiment_summary, e.g. 'throughput +20%' or 'no data'. Relay the actual
    measurements, comparison conditions and evidence in report, including failures.
    """
    try:
        workflow.experiments.record_external_result(exploration_id, report, experiment_summary)
    except ValueError as error:
        raise ToolError(str(error)) from error
    return {"exploration_id": exploration_id}


async def confirm_experiment_cleanup(
    exploration_id: RequiredText, evidence: RequiredText, *, workflow: "DefaultWorkflow",
) -> dict[str, str]:
    """Release a held measurement environment after its operator confirms the run is stopped.

    Relay the observed cleanup of the identified experiment's services, jobs and reserved hardware.
    This returns its existing report to the Explorer without running the measurement again.
    """
    try:
        workflow.experiments.confirm_cleanup(exploration_id, evidence)
    except ValueError as error:
        raise ToolError(str(error)) from error
    return {"exploration_id": exploration_id}
