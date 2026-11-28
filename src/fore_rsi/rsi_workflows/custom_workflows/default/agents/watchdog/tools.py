# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Publish the report file written by the Watchdog for its current review."""

from pathlib import Path
from typing import TYPE_CHECKING

from mcp.server.mcpserver.exceptions import ToolError

from fore_rsi.rsi_workflows.types import RequiredText

if TYPE_CHECKING:
    from .agent import WatchdogAgent


async def submit_watchdog_report(report_path: RequiredText, *, watchdog: "WatchdogAgent") -> dict[str, str]:
    """Publish an existing Markdown report by absolute path and return its location.

    Write the report in the directory assigned to this review before calling the tool.
    Send any actionable reminders directly with send_team_message; they are not part of this submission.
    """
    watchdog.require_tool_submission(submit_watchdog_report.__name__)
    try:
        path = watchdog.reports.publish(Path(report_path), watchdog.review_directory)
    except (OSError, ValueError) as error:
        raise ToolError(str(error)) from error
    return {"report_path": str(path)}
