# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Tools for the default workflow's Checker."""

from collections.abc import Awaitable, Callable
from typing import Literal, TypedDict

from mcp.server.mcpserver.exceptions import ToolError


ExplorationCheckResult = Literal["continue_exploration", "approve_for_experiment", "retire_workgroup"]


class ExplorationCheck(TypedDict):
    result: ExplorationCheckResult
    reason: str


async def submit_exploration_check(
    result: ExplorationCheckResult,
    reason: str,
    *,
    submit_check_operation: Callable[[ExplorationCheck], Awaitable[None]],
) -> dict[str, object]:
    """Submit a review decision so the workflow can choose the next step for this exploration.

    Inspect the code or proposal referenced by the Explorer and compare the findings with the
    task requirements. Review the specific exploration attempt identified in the review request. Choose one result.
    In reason, explain your assessment and cite the code, proposal, or observation that
    supports your decision.

    - continue_exploration: Choose this when the Explorer can address a specific issue or gap.
      Identify it in reason and describe the change or check needed before another review.
    - approve_for_experiment: Choose this when the code or proposal is ready to test.
      Identify what the experiment should test and why the submitted work is ready.
    - retire_workgroup: Choose this when the workgroup should stop pursuing this direction.
      Explain what justifies stopping and why another exploration attempt would not help.
    """

    if not reason.strip():
        raise ToolError("Provide a reason for the exploration check result.")
    await submit_check_operation({"result": result, "reason": reason})
    return {"exploration_check_queued": True}
