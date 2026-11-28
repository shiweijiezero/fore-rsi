# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Inspect a workflow's evidence, message its members and submit a written review."""

from pathlib import Path
from typing import TYPE_CHECKING

from mcp.server.mcpserver.exceptions import ToolError

from fore_rsi.config import AgentConfig
from fore_rsi.rsi_workflows.agent_runtimes.tool_mcp import register_agent_tool
from fore_rsi.rsi_workflows.base_agent import BaseAgent, ExpectedToolCalls
from fore_rsi.rsi_workflows.workflow_runtimes.task import TaskRevision
from fore_rsi.rsi_workflows.workflow_runtimes.watchdog_reports import WatchdogReports
from fore_rsi.rsi_workflows.workflow_runtimes.workgroup import Workgroup
from fore_rsi.utils.prompt_renderer import merge_prompts, render_prompt

from .tools import submit_watchdog_report

if TYPE_CHECKING:
    from ...workflow import DefaultWorkflow


class WatchdogAgent(BaseAgent):
    """Review progress against the task and publish evidence without directing the workflow."""

    role_name = "Watchdog"
    prompts_dir = Path(__file__).resolve().parents[2] / "prompts"
    review_tools = ExpectedToolCalls("review_workflow", frozenset({submit_watchdog_report.__name__}))

    def __init__(
        self, agent_name: str, workgroup: Workgroup, agent_config: AgentConfig, *, workflow: "DefaultWorkflow",
    ) -> None:
        """Bind this member's publication tool to the session's report history."""
        self.workflow = workflow
        self.reports = WatchdogReports(workflow.session_directory)
        self.review_number = 0
        self.review_directory: Path
        self.review_revision: TaskRevision | None = None
        tool = register_agent_tool(submit_watchdog_report, watchdog=self)
        super().__init__(agent_name, workgroup, agent_config, workflow=workflow, tools=[tool])
        self.system_prompt = merge_prompts([
            render_prompt(self.prompts_dir / "common/system.j2"),
            render_prompt(self.prompts_dir / "watchdog/system.j2"),
        ])

    async def review_progress(self, revision: TaskRevision) -> bool:
        """Give the Watchdog the evidence paths and a fresh report directory; wait for its submission."""
        self.review_number += 1
        self.review_directory = self.reports.start_review(self.agent_name, self.review_number)
        prompt = render_prompt(self.prompts_dir / "watchdog/review.j2", {
            "revision": revision.revision_number, "task_file": revision.revision_file_path.resolve(),
            "pool": self.workflow.exploration_pool, "members": self.conversation_records(),
            "reports": self.reports.list(), "review_directory": self.review_directory, "tool": submit_watchdog_report.__name__,
        })
        self.review_revision = revision
        try:
            return await self.request_submission(
                prompt, self.review_tools,
                retry_prompt=f"Finish the Markdown report under `{self.review_directory}` and submit its absolute path with "
                             f"`{submit_watchdog_report.__name__}`. Do not resend reminders already delivered.",
            )
        finally:
            self.review_revision = None

    async def live_teammates(self) -> dict[str, BaseAgent]:
        """Resolve recipients without sending a reminder based on a superseded task revision."""
        revision = self.review_revision
        teammates = await super().live_teammates()
        if revision is not None and self.workflow.task.current_task is not revision:
            raise ToolError("The task changed during this review. Submit your report for the reviewed revision without reminders.")
        return teammates

    def conversation_records(self) -> dict[str, tuple[str, tuple[Path, ...]]]:
        """Index this workflow's native evidence by member name without loading any transcript content."""
        records = {}
        for group in self.workflow.workgroups.values():
            for member in group.agents.values():
                state = "fork seed" if group.is_fork_seed else member.state.value
                records[member.get_full_name()] = state, member.agent_runtime.conversation_files()
            for name, paths in group.retired_records.items():
                records[name] = "retired", tuple(path for path in paths if path.is_file())
        return records
