# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Keep one Watchdog on duty for scheduled progress reviews while its role is enabled."""

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

from ..agents.watchdog import WatchdogAgent

if TYPE_CHECKING:
    from fore_rsi.rsi_workflows.workflow_runtimes.task import TaskRevision

    from ..workflow import DefaultWorkflow


async def run_watchdog_subflow(workflow: "DefaultWorkflow", workspace_id: str) -> None:
    """Start a resident Watchdog when enabled and retire it at a review boundary.

    [role enabled] --> start Watchdog --> wait for review time or task revision
        +-- review due --> review_progress --> wait in the same session after the review
        +-- allocation still fits --> keep the same session and review time
        +-- role disabled or model removed --> retire member --> wait for an eligible allocation

    [inspect evidence] --> write report --> send any reminders to teammates --> submit report path
        +-- submitted --> report appears in the session's review history
        +-- missing, attempts remain --> finish and submit the same report
        +-- attempts exhausted --> log the missing submission
    """
    scheduler = workflow.agent_scheduler
    loop = asyncio.get_running_loop()
    last_review_at = loop.time()
    group = None
    try:
        while True:
            # Recheck after startup, each wakeup and each settled review before assigning another turn.
            revision_changed = workflow.task.revision_changed
            revision = task_for_review(workflow)
            if group is not None and group.agents and (revision is None or not scheduler.can_reuse_workgroup(group)):
                await group.close_members()
                continue
            if revision is None:
                await revision_changed.wait()
                last_review_at = loop.time()
                continue
            if group is None:
                group = await workflow.workgroups.create(workspace_id=workspace_id, workgroup_name="watchdog")
            if not group.agents:
                await group.start_members(workflow, (WatchdogAgent,), workspace_id=workspace_id)
                continue

            # A model replacement can wake the timer but must not postpone a scheduled inspection.
            interval = revision.task_submission.agent_team.watchdog_interval_seconds
            assert interval is not None  # Required when the Coordinator enables the Watchdog.
            next_review_at = last_review_at + interval
            if loop.time() < next_review_at:
                try:
                    async with asyncio.timeout_at(next_review_at):
                        await revision_changed.wait()
                except TimeoutError:
                    pass
                continue
            watchdog = group.member(WatchdogAgent)
            if not await watchdog.review_progress(revision):
                logger.warning("{} did not submit a report for task revision {}.", watchdog.agent_name,
                               revision.revision_number)
            last_review_at = loop.time()
    finally:
        if group is not None:
            await group.close_members()


def task_for_review(workflow: "DefaultWorkflow") -> "TaskRevision | None":
    """Return the current revision if it requests a Watchdog with a nonzero role quota."""
    revision = workflow.task.current_task
    if (
        revision is not None
        and revision.task_submission.agent_team.roles.get(WatchdogAgent.role_name)
        and workflow.agent_scheduler.max_concurrent_workgroups((WatchdogAgent,)) != 0
    ):
        return revision
    return None
