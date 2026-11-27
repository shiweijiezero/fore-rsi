# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Explorer research, implementation, feedback, and Workgroup lifecycle subflow."""

import asyncio
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from fore_rsi.rsi_workflows.workflow_runtimes.workgroup import Workgroup

from ..agents.checker import CheckerAgent
from ..agents.explorer import ExplorerAgent

if TYPE_CHECKING:
    from ..agents.checker.tools import ExplorationCheck, ExplorationCheckResult
    from ..workflow import DefaultWorkflow


async def run_exploration_subflow(workflow: "DefaultWorkflow", workspace_id: str) -> None:
    """Initialize the exploration workgroups and wait for them to finish.

    initialize_explorers --> run_exploration_steps (once per group, in parallel) --> END
    """
    workgroups = await initialize_explorers(workflow, workspace_id)

    async with asyncio.TaskGroup() as tasks:
        for workgroup in workgroups:
            tasks.create_task(run_exploration_steps(workflow, workspace_id, workgroup))


async def run_exploration_steps(workflow: "DefaultWorkflow", workspace_id: str, workgroup: Workgroup) -> None:
    """Run one exploration round and return its outcome to the subflow.

    [select_direction] --> [checking_direction]
        +-- rejected, attempts remain --> [select_direction]
        +-- rejected on last attempt  --> [retire]
        +-- confirmed                 --> [create_exploration_item] --> [exploration]

    [exploration] --> [checking]
        +-- continue_exploration   --> [exploration] with the Checker's feedback
        +-- approve_for_experiment --> [submit_to_experiment] --> [experiment]
        +-- retire_workgroup       --> [retire]

    [experiment] --> Experimenter records results on the current item
                 --> Explorer: [analyse_result] --> [update_exploration_item] --> [choose_next_action]

    [choose_next_action]
        +-- continue_exploration --> [exploration] on the current item
        +-- start_new_round      --> [select_direction]
        +-- finish               --> [checking_finish]

    [checking_finish]
        +-- approved --> END for this workgroup
        +-- rejected --> [choose_next_action] with the Checker's feedback

    A required tool submission that exhausts its attempts leads to [retire].
    """
    workgroup = progress.workgroup
    if progress.direction is None:
        progress.direction = await select_and_check_direction(workflow, workgroup)
        if progress.direction is None:
            return "retire_workgroup"
    attempt = await explore_direction(
        workflow, workgroup, progress.direction,
        previous_attempt=progress.previous_attempt, checker_feedback=progress.checker_feedback,
    )
    if attempt is None:
        return "retire_workgroup"
    review = await check_exploration(workflow, workgroup, attempt)
    if review is None:
        return "retire_workgroup"
    progress.previous_attempt = attempt
    progress.checker_feedback = review["reason"] if review["result"] == "continue_exploration" else None
    if review["result"] == "approve_for_experiment":
        await submit_to_experiment(workflow, attempt)
    return review["result"]


async def initialize_explorers(workflow: "DefaultWorkflow", workspace_id: str) -> list[Workgroup]:
    """Prepare the seed session and return the seed and forked groups for the planned explorations.

    workgroups.create (Explorer + Checker) --> study_framework --> fork_explorers
    """
    seed_workgroup = await workflow.workgroups.create(
        workspace_id=workspace_id,
        agents=[ExplorerAgent, CheckerAgent],
        task_revision=workflow.task.current_task,
    )
    await study_framework(workflow, seed_workgroup)
    quota = explorer_quota(workflow)
    limit = None if quota == "unlimited" else max(0, quota - 1)
    forks = await fork_explorers(workflow, workspace_id, seed_workgroup, limit=limit) if limit != 0 else []
    return [seed_workgroup, *forks]


async def study_framework(workflow: "DefaultWorkflow", seed_workgroup: Workgroup) -> None:
    """Prepare shared task and framework context in the seed Explorer's session before forking."""
    raise NotImplementedError("Shared framework study is not implemented.")


async def fork_explorers(
    workflow: "DefaultWorkflow", workspace_id: str, seed_workgroup: Workgroup, *, limit: int | None
) -> list[Workgroup]:
    """Fork additional planned work from the seed, with no running members or reserved slots.

    Return at most limit new workgroups, or all remaining planned forks when unlimited.
    """
    raise NotImplementedError("Forking exploration workgroups is not implemented.")


async def select_and_check_direction(workflow: "DefaultWorkflow", workgroup: Workgroup) -> str | None:
    """Return a confirmed direction ID, or None after exhausted proposals or tool submissions.

    [select_direction] --> wait_direction_quota --> exploration_direction (MCP)
        --> wait_for_settle --> tool_submission_status
            +--[submitted] -------> [checking_direction]
            +--[not_submitted] ---> exploration_direction
            +--[exceed_limit_try] -> [retire]

    [checking_direction] --> check_exploration_direction (MCP)
        --> wait_for_settle --> tool_submission_status
            +--[submitted] -------> direction_check_result
            +--[not_submitted] ---> check_exploration_direction
            +--[exceed_limit_try] -> [retire]

    direction_check_result
        +--[confirmed]                    --> update_exploration_pool --> [exploration]
        +--[rejected, attempts remain]    --> exploration_direction
        +--[rejected on the last attempt] --> [retire]
    """
    for _ in range(workflow.config.max_attempts):
        direction = await propose_direction(workflow, workgroup)
        if direction is None:
            return None
        confirmed = await check_direction(workflow, workgroup, direction)
        if confirmed is None:
            return None
        if confirmed:
            return direction
    return None


async def propose_direction(workflow: "DefaultWorkflow", workgroup: Workgroup) -> str | None:
    """Return the Explorer's proposed direction ID, or None if it exhausts its tool submission attempts."""
    raise NotImplementedError("Exploration direction submission is not implemented.")


async def check_direction(workflow: "DefaultWorkflow", workgroup: Workgroup, direction: str) -> bool | None:
    """Record confirmed directions in the pool; return False for rejection or None for exhausted tool attempts."""
    raise NotImplementedError("Exploration direction review is not implemented.")


async def explore_direction(
    workflow: "DefaultWorkflow",
    workgroup: Workgroup,
    direction: str,
    *,
    previous_attempt: str | None,
    checker_feedback: str | None,
) -> str | None:
    """Use the previous attempt's record and any Checker feedback to explore the direction.

    Return the new attempt ID, or None if the Explorer exhausts its submission attempts.

    [exploration] --> exploration (MCP, including update_exploration_pool)
        --> wait_for_settle --> tool_submission_status
            +--[submitted] -------> [checking]
            +--[not_submitted] ---> exploration
            +--[exceed_limit_try] -> [retire]
    """
    raise NotImplementedError("Exploring a confirmed direction is not implemented.")


async def check_exploration(
    workflow: "DefaultWorkflow", workgroup: Workgroup, attempt: str
) -> "ExplorationCheck | None":
    """Return the Checker's decision and reason for this attempt, or None after exhausted retries.

    [checking] --> check_exploration (MCP) --> wait_for_settle --> tool_submission_status
        +--[submitted] -------> [exploration] / [submit_to_experiment] / [retire]
        +--[not_submitted] ---> check_exploration
        +--[exceed_limit_try] -> [retire]
    """
    raise NotImplementedError("Exploration review is not implemented.")


async def submit_to_experiment(workflow: "DefaultWorkflow", attempt: str) -> None:
    """Mark the approved attempt ready for experiment in the shared exploration pool."""
    raise NotImplementedError("Experiment handoff is not implemented.")


async def wait_for_experiment_result(workflow: "DefaultWorkflow", attempt: str) -> None:
    """Wait until this attempt's exploration entry contains its experiment result."""
    raise NotImplementedError("Waiting for an experiment result on its exploration entry is not implemented.")
