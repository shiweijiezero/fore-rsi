# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Accept the Checker's decision for the review requested in its current turn."""

from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypedDict

from mcp.server.mcpserver.exceptions import ToolError

from fore_rsi.rsi_workflows.types import RequiredText

if TYPE_CHECKING:
    from .agent import CheckerAgent


ExplorationCheckResult = Literal["continue_exploration", "approve_for_experiment", "retire_workgroup"]


class ExplorationCheck(TypedDict):
    """Decision and feedback returned to an Explorer after reviewing work on an item."""

    result: ExplorationCheckResult
    reason: str


async def submit_direction_check(approved: bool, reason: RequiredText, *, checker: "CheckerAgent") -> dict[str, bool]:
    """Record approval or rejection on the exploration item assigned for direction review.

    Explain why the approach and its starting point fit the task, or identify the change
    the Explorer should make when choosing a direction again.
    """
    checker.require_tool_submission(submit_direction_check.__name__)
    exploration_pool = checker.workflow.exploration_pool
    exploration_item_id = checker.proposed_exploration_item_id
    verdict = "approved" if approved else "rejected"
    checkout = None  # A rejected proposal gives up its unimplemented workspace.
    if approved:
        # Before releasing the selection lock, give the reservation a physical identity.
        # Peers then see the same directory through any filesystem alias, even before sources are copied.
        checkout = exploration_pool.get(exploration_item_id).code_workspace_path
        assert checkout is not None
        try:
            Path(checkout).mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise ToolError(f"Cannot reserve the proposed checkout {checkout}: {error}") from error
    exploration_pool.append_record(exploration_item_id, f"\n**Direction {verdict}:** {reason}\n")
    exploration_pool.update(exploration_item_id, status=verdict, code_workspace_path=checkout)
    checker.approval = approved, reason
    return {"submitted": True}


async def submit_exploration_check(
    result: ExplorationCheckResult, reason: RequiredText, *, checker: "CheckerAgent",
) -> dict[str, bool]:
    """Decide whether the reviewed item is ready to hand to the Experimenter.

    Use approve_for_experiment when the checkout, commands and comparison are ready to run.
    Use continue_exploration for a fixable problem, naming the change needed in reason.
    Use retire_workgroup when further work on the direction is not justified.
    Cite the evidence behind your decision.
    """
    checker.require_tool_submission(submit_exploration_check.__name__)
    checker.exploration_check = {"result": result, "reason": reason}
    return {"submitted": True}


async def submit_finish_check(approved: bool, reason: RequiredText, *, checker: "CheckerAgent") -> dict[str, bool]:
    """Approve or reject the request to finish this workgroup after its experiment.

    Explain why stopping is justified by the recorded result and task constraints. If not,
    identify the unresolved question so the Explorer can reconsider its next action.
    """
    checker.require_tool_submission(submit_finish_check.__name__)
    checker.approval = approved, reason
    return {"submitted": True}
