# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Tool implementations for the default workflow's Coordinator."""

from collections.abc import Awaitable, Callable

from mcp.server.mcpserver.exceptions import ToolError

from fore_rsi.rsi_workflows.workflow_runtimes.task import TaskRevision, TaskSubmission


async def submit_task(
    task_submission: TaskSubmission,
    *,
    submit_to_workflow: Callable[[TaskSubmission], Awaitable[TaskRevision]],
) -> dict[str, int]:
    """Convert the user's requirements into a complete and accurate task declaration for the team.

    Preserve every known requirement. Make reasonable assumptions and fill optional details from the available
    context. Ask for clarification only when ambiguity would materially change the goal, evaluation, safety, or
    resource budget. Include the goal, constraints, agent_team allocations, environment_variables as name/value
    pairs, and task_comments when known. Keep credentials in the host environment instead of the task declaration.
    In constraints, preserve common_constraints, resources, stop_conditions, and time_budget. In agent_team,
    declare each role's model, effort, and quota. For updates, provide the complete current task again and retain
    unchanged requirements. A successful call returns revision_number after publication and quota application.
    An unchanged declaration returns the same revision number and still signals a submission to the workflow.
    """
    try:
        task_revision = await submit_to_workflow(task_submission)
    except ValueError as error:
        raise ToolError(f"Task declaration was not accepted: {error}") from error
    return {"revision_number": task_revision.revision_number}
