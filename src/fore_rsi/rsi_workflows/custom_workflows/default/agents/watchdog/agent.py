# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Watchdog role for the default collaboration workflow."""

from pathlib import Path
from typing import TYPE_CHECKING

from fore_rsi.config import AgentConfig
from fore_rsi.rsi_workflows.agent_runtimes.tool_mcp import register_agent_tool
from fore_rsi.rsi_workflows.base_agent import BaseAgent, ExpectedToolCalls
from fore_rsi.rsi_workflows.workflow_runtimes.workgroup import Workgroup
from fore_rsi.utils.prompt_renderer import merge_prompts, render_prompt

from .tools import read_agent_session, read_task_artifact, submit_watchdog_review

if TYPE_CHECKING:
    from ...workflow import DefaultWorkflow


_PROMPTS = Path(__file__).resolve().parents[2] / "prompts"


class WatchdogAgent(BaseAgent):
    """Observe team progress and follow up on stalled or ineffective work."""

    role_name = "Watchdog"
    review_tools = ExpectedToolCalls(step="review_workflow", tools=frozenset({submit_watchdog_review.__name__}))

    def __init__(
        self,
        agent_name: str,
        workgroup: Workgroup,
        agent_config: AgentConfig,
        *,
        workflow: "DefaultWorkflow",
    ) -> None:
        self.review: dict[str, object] = {}
        self.review_recipients: set[str] = set()
        super().__init__(
            agent_name,
            workgroup,
            agent_config,
            workflow=workflow,
            tools=[
                read_agent_session,
                read_task_artifact,
                register_agent_tool(submit_watchdog_review, watchdog=self),
            ],
        )
        self.system_prompt = merge_prompts([
            render_prompt(_PROMPTS / "common/system.j2"),
            render_prompt(_PROMPTS / "watchdog/system.j2"),
        ])

    async def review_workflow(
        self, sessions: dict[str, dict[str, str] | None], artifacts: dict[str, str],
    ) -> None:
        """Prompt the Watchdog to inspect the listed members and submit its review."""
        self.review_recipients = set(sessions)
        prompt = merge_prompts([
            render_prompt(_PROMPTS / "common/user.j2"),
            render_prompt(
                _PROMPTS / "watchdog/user/inspect_progress.j2", {"sessions": sessions, "artifacts": artifacts}
            ),
        ])
        await self.send_message(prompt, expected_tool_calls=self.review_tools)

    def publish_watchdog_report(self) -> None:
        """Publish the findings and open follow-ups from this review."""
        raise NotImplementedError

    def publish_watchdog_knowledge(self) -> None:
        """Save the review's reusable lessons for later inspections."""
        raise NotImplementedError
