# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Review proposed directions, experiment handoffs and requests to finish a workgroup."""

from pathlib import Path
from typing import TYPE_CHECKING

from fore_rsi.config import AgentConfig
from fore_rsi.rsi_workflows.agent_runtimes.tool_mcp import (
    AgentTool,
    register_agent_tool,
)
from fore_rsi.rsi_workflows.base_agent import BaseAgent, ExpectedToolCalls
from fore_rsi.rsi_workflows.workflow_runtimes.workgroup import Workgroup
from fore_rsi.utils.prompt_renderer import merge_prompts, render_prompt

from .tools import (
    ExplorationCheck,
    submit_direction_check,
    submit_exploration_check,
    submit_finish_check,
)

if TYPE_CHECKING:
    from fore_rsi.rsi_workflows.custom_workflows.default.workflow import DefaultWorkflow


class CheckerAgent(BaseAgent):
    """Return a decision and its evidence to the exploration step that requested the review."""

    role_name = "Checker"
    prompts_dir = Path(__file__).resolve().parents[2] / "prompts"

    def __init__(
        self,
        agent_name: str,
        workgroup: Workgroup,
        agent_config: AgentConfig,
        *,
        workflow: "DefaultWorkflow",
    ) -> None:
        """Bind the review tools and give this Checker read access to the exploration records."""
        self.workflow = workflow
        self.proposed_exploration_item_id: str
        self.approval: tuple[bool, str] | None = None
        self.exploration_check: ExplorationCheck | None = None
        tools = [register_agent_tool(tool, checker=self) for tool in (
            submit_direction_check, submit_exploration_check, submit_finish_check,
        )]
        super().__init__(agent_name, workgroup, agent_config, workflow=workflow, tools=tools)
        self.system_prompt = merge_prompts([
            render_prompt(self.prompts_dir / "common" / "system.j2"),
            render_prompt(self.prompts_dir / "checker" / "system.j2", {
                "workgroup_name": workgroup.workgroup_name,
                "exploration_database": workflow.exploration_pool.database_path.resolve(),
            }),
        ])

    async def review_direction(self, exploration_item_id: str) -> tuple[bool, str] | None:
        """Review the pending item's proposal and bind the decision tool to that same ID."""
        self.proposed_exploration_item_id = exploration_item_id
        if await self.request_review("check_direction", submit_direction_check, exploration_item_id):
            return self.approval
        return None

    async def review_exploration(self, exploration_item_id: str) -> ExplorationCheck | None:
        """Decide whether the current item needs more work, is ready for experiment, or should retire."""
        submitted = await self.request_review("check_exploration", submit_exploration_check, exploration_item_id)
        return self.exploration_check if submitted else None

    async def review_finish(self, exploration_item_id: str, reason: str, *, attempts_left: int) -> tuple[bool, str, int] | None:
        """Return the decision, reason and prompts used from this group's finish-review budget."""
        submitted = await self.request_review(
            "check_finish", submit_finish_check, exploration_item_id, reason=reason, attempts_left=attempts_left,
        )
        if not submitted:
            return None
        assert self.approval is not None and self.step_tool_calls is not None
        approved, feedback = self.approval
        return approved, feedback, self.step_tool_calls.attempt_number

    async def request_review(
        self, step: str, tool: AgentTool, exploration_item_id: str, *, attempts_left: int | None = None, **context: object,
    ) -> bool:
        """Present the current task, item and record together, then collect the decision for this review."""
        revision = self.workflow.task.current_task
        assert revision is not None  # The workflow starts exploration after the first task submission.
        exploration_pool = self.workflow.exploration_pool
        exploration_item = exploration_pool.get(exploration_item_id)
        name = tool.__name__
        context.update(
            exploration_item=exploration_item.model_dump_json(indent=2),
            exploration_record_path=exploration_pool.exploration_record_path(exploration_item_id, name=exploration_item.name),
            tool=name,
        )
        prompt = merge_prompts([
            render_prompt(self.prompts_dir / "common/user.j2"),
            f"Current task: {revision.revision_file_path.resolve()}",
            render_prompt(self.prompts_dir / "checker" / f"{step}.j2", context),
        ])
        expected = ExpectedToolCalls(step=step, tools=frozenset({name}))
        return await self.request_submission(
            prompt, expected, max_attempts=attempts_left,
            retry_prompt=f"Continue the same review and submit your decision with `{name}` using the evidence gathered.",
        )
