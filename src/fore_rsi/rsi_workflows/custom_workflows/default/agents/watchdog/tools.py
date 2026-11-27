# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""MCP tools exposed to the Watchdog during an inspection."""

from typing import TYPE_CHECKING, Literal

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from .agent import WatchdogAgent


class Reminder(BaseModel):
    """An action requested from a workflow member based on inspection evidence."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, str_min_length=1)

    recipient: str
    reason: Literal["stalled", "duplicate_work", "handoff_gap", "unresolved_followup"]
    evidence: str
    requested_action: str


class WatchdogReview(BaseModel):
    """The result of one inspection, including any reminders to deliver."""

    model_config = ConfigDict(extra="forbid")

    findings: list[str]
    reminders: list[Reminder]
    follow_ups: list[str]
    lessons: list[str]


async def read_agent_session(member: str) -> dict[str, object]:
    """Read a conversation using the member's full name from the inspection brief."""
    raise NotImplementedError


async def read_task_artifact(artifact: str) -> dict[str, object]:
    """Read a task artifact listed in the inspection brief."""
    raise NotImplementedError


async def submit_watchdog_review(review: WatchdogReview, *, watchdog: "WatchdogAgent") -> dict[str, object]:
    """Submit the Watchdog's review at the end of every inspection.

    Include findings, open follow-ups, and reusable lessons. Add a reminder when
    evidence from a session or task artifact shows that a member needs to act.
    Use the member's full name from the session list, choose the matching reason,
    cite the evidence, and state the next action. Use an empty reminders list
    when no action is needed.

    On success, the workflow has recorded the review. The send_reminders step
    handles delivery.
    """
    for reminder in review.reminders:
        if reminder.recipient not in watchdog.review_recipients:
            raise ToolError(
                f"Unknown reminder recipient {reminder.recipient!r}. "
                "Use a full member name from this round's session list."
            )
    watchdog.review = review.model_dump()
    return {"submitted": True}
