# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Default workflow Watchdog timer, observation, and feedback subflow."""

from typing import TYPE_CHECKING

from fore_rsi.rsi_workflows.workflow_runtimes.task import TaskRevision

if TYPE_CHECKING:
    from ..workflow import DefaultWorkflow


async def run_watchdog_subflow(
    workflow: "DefaultWorkflow",
    workspace_id: str,
    task_revision: TaskRevision,
) -> None:
    """Monitor agent progress until exploration and experiment finish or the workflow is cancelled.

    START --> create_watchdog
                  -> wait_for_watchdog_timer
                  --> collect_agent_sessions
                  --> collect_task_artifacts
                  --> review_workflow (MCP: inspect sessions and artifacts, submit review)
                  --> wait_for_settle_and_tool_subflow[A=watchdog_action,B=review_workflow,C=exit_node]
    watchdog_action --> send_reminders --> publish_watchdog_report
    --> publish_watchdog_knowledge --> wait_for_watchdog_timer
    exit_node --> END
    """
    raise NotImplementedError("The watchdog subflow is not implemented.")
