# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Default workflow Watchdog timer, observation, and feedback subflow."""

import asyncio
from dataclasses import replace
from typing import TYPE_CHECKING

from loguru import logger

from fore_rsi.rsi_workflows.workflow_runtimes.task import TaskRevision
from fore_rsi.utils.terminal import read_agent_session

from ..agents.watchdog import WatchdogAgent

if TYPE_CHECKING:
    from ..workflow import DefaultWorkflow


async def run_watchdog_subflow(workflow: "DefaultWorkflow", workspace_id: str) -> None:
    """Monitor agent progress until exploration and experiment finish or the workflow is cancelled.

    START --> create_watchdog
                  -> wait_for_watchdog_timer
                  --> collect_agent_sessions
                  --> collect_task_artifacts
                  --> review_workflow (MCP: inspect sessions and artifacts, submit review)
                  --> wait_for_settle --> tool_submission_status
                      +--[submitted] -------> watchdog_action
                      +--[not_submitted] ---> review_workflow
                      +--[exceed_limit_try] -> exit_node
    watchdog_action --> send_reminders --> publish_watchdog_report
    --> publish_watchdog_knowledge --> wait_for_watchdog_timer
    exit_node --> END
    """
    revision = workflow.task.task_revisions[-1]
    watchdog = await create_watchdog(workflow, workspace_id, revision)
    try:
        while True:
            team = workflow.task.task_revisions[-1].task_submission.agent_team
            await asyncio.sleep(team.watchdog_interval_seconds)
            sessions = await collect_agent_sessions(workflow)
            artifacts = collect_task_artifacts(workflow)

            status = "not_submitted"
            while status == "not_submitted":
                await watchdog.review_workflow(sessions, artifacts)
                await watchdog.wait_for_settle()
                status = watchdog.tool_submission_status(max_attempts=workflow.config.max_attempts)
            if status == "exceed_limit_try":
                logger.warning("{} exhausted its review submission attempts.", watchdog.get_full_name())
                return

            await send_reminders(workflow, watchdog.review)
            watchdog.publish_watchdog_report()
            watchdog.publish_watchdog_knowledge()
    finally:
        await watchdog.workgroup.discard_member(watchdog)


async def create_watchdog(
    workflow: "DefaultWorkflow", workspace_id: str, revision: TaskRevision,
) -> WatchdogAgent:
    config = workflow.default_agent_config
    if allocations := revision.task_submission.agent_team.roles.get(WatchdogAgent.role_name):
        config = replace(config, model=allocations[0].model, effort=allocations[0].effort)
    return await workflow.agent_scheduler.create_agent(
        agent_class=WatchdogAgent,
        workgroup=workflow.workgroups.global_workgroup,
        agent_config=config,
        workflow=workflow,
        workspace_id=workspace_id,
        is_entry_agent=False,
    )


async def collect_agent_sessions(workflow: "DefaultWorkflow") -> dict[str, dict[str, str] | None]:
    members = [agent for group in workflow.workgroups.values() for agent in group.agents.values()]
    sessions = {}
    for agent in members:
        runtime = agent.agent_runtime
        session = None
        if runtime.pane_id is not None:
            session = await read_agent_session(runtime.pane_id, runtime.terminal_session_name)
        sessions[agent.get_full_name()] = session
    return sessions


def collect_task_artifacts(workflow: "DefaultWorkflow") -> dict[str, str]:
    return {
        "task": str(workflow.task.task_revisions[-1].revision_file_path),
        "direction_pool": read_direction_pool(workflow),
    }


def read_direction_pool(workflow: "DefaultWorkflow") -> str:
    """Return a reference to the Explorers' shared direction pool."""
    raise NotImplementedError


async def send_reminders(workflow: "DefaultWorkflow", review: dict[str, object]) -> None:
    """Deliver each reminder, using the inbox for a sleeping recipient."""
    raise NotImplementedError
