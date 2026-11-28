# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Explorer tools for registering an item, submitting its experiment commands and choosing the next action."""

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from mcp.server.mcpserver.exceptions import ToolError

from fore_rsi.rsi_workflows.types import RequiredText
from fore_rsi.rsi_workflows.workflow_runtimes.exploration_pool import (
    ExplorationItem,
    ExplorationSubmission,
)

if TYPE_CHECKING:
    from .agent import ExplorerAgent


type NextAction = Literal["continue_exploration", "start_new_round", "finish"]


async def submit_exploration_item(
    item: ExplorationSubmission, *, explorer: "ExplorerAgent"
) -> dict[str, str]:
    """Submit the baseline or a direction for review. Return its ID and absolute exploration_record_path.

    For the baseline, describe its revision and configuration, supply an empty parent list,
    and give the absolute path of the populated starting checkout. No experiment is needed.
    For a direction, name the change, describe the hypothesis and how to evaluate it, and list
    the IDs of its parents. When continuing a measured direction, include the specified item
    as a direct parent. When starting from the baseline or a mature parent, give an unused
    path under the session's code directory for an independent working copy. To continue
    in place, give the checkout still owned by a measured, retired, unpublished direct parent.
    The new item reserves the path; prepare or edit its files only after approval.

    Write the baseline notes or detailed proposal in the returned Markdown record before ending
    the turn. The Checker reviews that same item. The workflow assigns its ID and task revision.
    """
    explorer.require_tool_submission(submit_exploration_item.__name__)
    exploration_pool = explorer.workflow.exploration_pool
    revision = explorer.workflow.task.current_task
    assert revision is not None
    if not item.code_workspace_path or not Path(item.code_workspace_path).is_absolute():
        raise ToolError("Supply an absolute code_workspace_path.")
    checkout = Path(item.code_workspace_path).resolve()

    if exploration_pool.is_empty():
        if same_directory(checkout, explorer.code_directory):
            raise ToolError("Use a baseline checkout, not the shared code directory itself.")
        if item.parent_exploration_ids:
            raise ToolError("The baseline must be the first item and have no parents.")
        require_populated_checkout(checkout)
        status = "mature"  # A stable reference; it has no measured result.
    else:
        required_parent_exploration_id = explorer.required_parent_exploration_id
        if (
            required_parent_exploration_id is not None
            and required_parent_exploration_id not in item.parent_exploration_ids
        ):
            raise ToolError(f"Include the measured item {required_parent_exploration_id} in parent_exploration_ids.")
        if not item.parent_exploration_ids:
            raise ToolError("Choose at least one parent for the proposed direction, such as the baseline.")
        check_workspace_claim(checkout, item.parent_exploration_ids, explorer)
        status = "pending_confirmation"

    # MCP calls run on the workflow event loop. No await separates checking ownership from
    # registering the claim, so another Explorer sees it before it can claim the same path.
    exploration_item = ExplorationItem(**(item.model_dump() | {"code_workspace_path": str(checkout)}), status=status)
    try:
        exploration_item_id = exploration_pool.add(exploration_item, task_revision_number=revision.revision_number)
    except ValueError as error:
        raise ToolError(str(error)) from error
    explorer.current_exploration_item_id = exploration_item_id
    exploration_record_path = exploration_pool.exploration_record_path(exploration_item_id, name=item.name)
    return {"exploration_id": exploration_item_id, "exploration_record_path": str(exploration_record_path)}


async def submit_exploration_update(
    experiment_commands: list[RequiredText], *, explorer: "ExplorerAgent"
) -> dict[str, str]:
    """Submit the current item's prepared checkout and ordered experiment commands to the Checker.

    Finish the implementation in the registered checkout and write the design, changes,
    comparison conditions and expected artifacts in the item's Markdown record first. Give
    commands that the Experimenter can execute in order. This tool does not run them.
    """
    explorer.require_tool_submission(submit_exploration_update.__name__)
    exploration_item_id = explorer.current_exploration_item_id
    assert exploration_item_id is not None
    exploration_pool = explorer.workflow.exploration_pool
    exploration_item = exploration_pool.get(exploration_item_id)
    if exploration_item.status != "exploring" or not exploration_item.parent_exploration_ids:
        raise ToolError("Only an active exploration item can submit work for review.")
    assert exploration_item.code_workspace_path is not None  # Registration claims the checkout before the first edit.
    checkout = Path(exploration_item.code_workspace_path)
    if checkout.resolve() != checkout:
        raise ToolError("Restore the registered checkout; its path now resolves elsewhere.")
    require_populated_checkout(checkout)
    if not experiment_commands:
        raise ToolError("Provide the commands needed to evaluate this item.")
    exploration_pool.update(exploration_item_id, experiment_commands=experiment_commands)
    return {"exploration_id": exploration_item_id}


async def submit_next_action(
    action: NextAction, reason: RequiredText, publish: bool, *, explorer: "ExplorerAgent"
) -> dict[str, str]:
    """Choose what to do after analyzing the current item's recorded experiment.

    Use continue_exploration for a new round that builds directly on this measured item,
    start_new_round to choose the next direction and parents freely, or finish to request
    Checker approval to stop. Explain the evidence for the choice. Set publish=true to
    preserve the measured checkout as a fixed starting point; children then need their own copy.
    """
    explorer.require_tool_submission(submit_next_action.__name__)
    explorer.next_action = action, reason, publish
    return {"action": action}


def check_workspace_claim(checkout: Path, parent_exploration_ids: list[str], explorer: "ExplorerAgent") -> None:
    """Reject a claim that would let a second exploration edit active or published code."""
    code_directory = explorer.code_directory
    existing = next(path for path in (checkout, *checkout.parents) if path.exists())
    if not existing.is_dir():
        raise ToolError(f"Cannot create a checkout at {checkout}: {existing} is not a directory.")
    if same_directory(checkout, code_directory) or inside_directory(code_directory, checkout):
        raise ToolError("Choose a checkout for this item, not the shared code directory or its parent.")
    managed = inside_directory(checkout, code_directory)
    previous_owner_id = None
    for existing_exploration_item in explorer.workflow.exploration_pool.list():
        if not existing_exploration_item.code_workspace_path:
            continue
        occupied = Path(existing_exploration_item.code_workspace_path).resolve()
        if same_directory(occupied, checkout):
            if (
                not existing_exploration_item.parent_exploration_ids
                or existing_exploration_item.status != "retired"
                or not existing_exploration_item.experiment_result
            ):
                raise ToolError(
                    f"Item {existing_exploration_item.exploration_id} still owns {checkout}. Choose an independent checkout."
                )
            previous_owner_id = existing_exploration_item.exploration_id
        elif inside_directory(checkout, occupied) or inside_directory(occupied, checkout):
            # The workflow's code directory can live inside the task's baseline repository.
            if not existing_exploration_item.parent_exploration_ids and managed and inside_directory(code_directory, occupied):
                continue
            raise ToolError(f"The checkout overlaps item {existing_exploration_item.exploration_id} at {occupied}.")
    if previous_owner_id is not None:
        if previous_owner_id not in parent_exploration_ids:
            raise ToolError(f"To reuse this checkout, include its current owner {previous_owner_id} as a direct parent.")
        require_populated_checkout(checkout)
    elif not managed:
        raise ToolError(f"Choose a new checkout under {code_directory} or reuse a measured unpublished parent's checkout.")
    elif checkout.is_dir() and any(checkout.iterdir()):
        raise ToolError("Choose an unused directory for the new checkout.")


def same_directory(left: Path, right: Path) -> bool:
    """Compare path reservations by spelling or, for existing directories, by filesystem identity."""
    if str(left) == str(right):
        return True
    try:
        return left.samefile(right)
    except FileNotFoundError:
        return False


def inside_directory(path: Path, directory: Path) -> bool:
    """Recognize an alias of an existing ancestor even when the proposed leaf does not exist yet."""
    return any(same_directory(parent, directory) for parent in path.parents)


def require_populated_checkout(checkout: Path) -> None:
    """Reject a missing or empty source tree before it becomes a baseline or an experiment input."""
    if not checkout.is_dir() or not any(path.name != ".git" for path in checkout.iterdir()):
        raise ToolError(f"Prepare the source files in {checkout} before submitting.")
