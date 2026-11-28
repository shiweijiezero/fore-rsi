# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Explorer conversations for preparing the baseline, implementing a direction and analyzing its results."""

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
    NextAction,
    submit_exploration_item,
    submit_exploration_update,
    submit_next_action,
)

if TYPE_CHECKING:
    from fore_rsi.rsi_workflows.custom_workflows.default.workflow import DefaultWorkflow


class ExplorerAgent(BaseAgent):
    """Own one Explorer conversation; the workflow and the pool own the resulting items."""

    role_name = "Explorer"
    prompts_dir = Path(__file__).resolve().parents[2] / "prompts"

    def __init__(
        self,
        agent_name: str,
        workgroup: Workgroup,
        agent_config: AgentConfig,
        *,
        workflow: "DefaultWorkflow",
    ) -> None:
        """Bind the role's MCP tools to this member, not to the seed or another workgroup."""
        self.workflow = workflow
        self.code_directory = (workflow.session_directory / "code").resolve()
        self.current_exploration_item_id: str | None = None
        self.required_parent_exploration_id: str | None = None
        self.next_action: tuple[NextAction, str, bool] | None = None
        tools = (
            submit_exploration_item,
            submit_exploration_update,
            submit_next_action,
        )
        super().__init__(
            agent_name,
            workgroup,
            agent_config,
            workflow=workflow,
            tools=[register_agent_tool(tool, explorer=self) for tool in tools],
        )
        self.system_prompt = merge_prompts(
            [
                render_prompt(self.prompts_dir / "common/system.j2"),
                render_prompt(
                    self.prompts_dir / "explorer/system.j2",
                    {
                        "exploration_database": workflow.exploration_pool.database_path.resolve(),
                    },
                ),
            ]
        )

    async def study_framework(self, task_file: Path) -> None:
        """Read the task and its framework in the seed conversation before preparing shared code."""
        prompt = merge_prompts(
            [
                render_prompt(self.prompts_dir / "common/user.j2"),
                render_prompt(self.prompts_dir / "explorer/study_framework.j2", {"task_file": task_file}),
            ]
        )
        await self.send_message(prompt)
        await self.wait_for_settle()

    async def prepare_baseline(self) -> None:
        """Register the team's read-only starting checkout and leave its record for the forked Explorers."""
        self.code_directory.mkdir(parents=True, exist_ok=True)
        if not await self.request_step("prepare_baseline", submit_exploration_item):
            raise RuntimeError(f"{self.agent_name} did not register the baseline.")
        assert self.current_exploration_item_id is not None
        exploration_record_path = self.workflow.exploration_pool.exploration_record_path(self.current_exploration_item_id)
        if not exploration_record_path.read_text(encoding="utf-8").strip():
            raise RuntimeError(f"The baseline has no source or configuration notes in {exploration_record_path}.")

    async def propose_direction(self, feedback: str | None, required_parent_exploration_id: str | None) -> str | None:
        """Submit a new item for review; a continuation must name the measured item as a direct parent."""
        self.current_exploration_item_id = None
        self.required_parent_exploration_id = required_parent_exploration_id
        if await self.request_step(
            "select_direction", submit_exploration_item, exploration_item_id=required_parent_exploration_id, feedback=feedback,
        ):
            return self.current_exploration_item_id
        return None

    async def explore_item(self, exploration_item_id: str, feedback: str | None) -> bool:
        """Implement or revise the item in its claimed checkout and submit its experiment commands for review."""
        self.current_exploration_item_id = exploration_item_id
        return await self.request_step(
            "exploration", submit_exploration_update, feedback=feedback, exploration_item_id=exploration_item_id
        )

    async def analyse_experiment_result(
        self, exploration_item_id: str, feedback: str | None
    ) -> tuple[NextAction, str, bool] | None:
        """Ask the Explorer to interpret the report and submit its next action in the same turn."""
        self.next_action = None
        if await self.request_step(
            "analyse_experiment_result", submit_next_action, exploration_item_id=exploration_item_id, feedback=feedback,
        ):
            return self.next_action
        return None

    async def request_step(
        self, step: str, tool: AgentTool, *, exploration_item_id: str | None = None, **context: object
    ) -> bool:
        """Give the current task and, on resumed work, the original item's record to this prompt."""
        revision = self.workflow.task.current_task
        assert revision is not None  # The Coordinator publishes a task before starting the team.
        name = tool.__name__
        context.update(task_file=revision.revision_file_path.resolve(), code_directory=self.code_directory, tool=name)
        if exploration_item_id is not None:
            exploration_pool = self.workflow.exploration_pool
            exploration_item = exploration_pool.get(exploration_item_id)
            context.update(
                exploration_item=exploration_item,
                exploration_record_path=exploration_pool.exploration_record_path(
                    exploration_item_id, name=exploration_item.name,
                ),
            )
        prompt = render_prompt(self.prompts_dir / "explorer" / f"{step}.j2", context)
        expected = ExpectedToolCalls(step=step, tools=frozenset({name}))
        return await self.request_submission(
            prompt, expected,
            retry_prompt=f"Continue the previous step. Submit with `{name}` and finish its requested working notes.",
        )
