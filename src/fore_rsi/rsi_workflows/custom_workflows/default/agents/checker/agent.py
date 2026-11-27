# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Checker role for the default collaboration workflow."""

from asyncio import Queue
from pathlib import Path
from typing import TYPE_CHECKING, cast

from fore_rsi.config import AgentConfig
from fore_rsi.rsi_workflows.agent_runtimes.tool_mcp import register_agent_tool
from fore_rsi.rsi_workflows.base_agent import BaseAgent, ExpectedToolCalls
from fore_rsi.rsi_workflows.workgroup import Workgroup
from fore_rsi.utils.prompt_renderer import merge_prompts, render_prompt

from .tools import ExplorationCheck, submit_exploration_check

if TYPE_CHECKING:
    from fore_rsi.rsi_workflows.custom_workflows.default.workflow import DefaultWorkflow


class CheckerAgent(BaseAgent):
    """Review plans, work, and conclusions during team collaboration."""

    role_name = "Checker"
    check_exploration_tools = ExpectedToolCalls(
        step="check_exploration", tools=frozenset({submit_exploration_check.__name__})
    )
    common_system_prompt_path = (
        Path(__file__).resolve().parents[2] / "prompts" / "common" / "system.j2"
    )
    common_user_prompt_path = (
        Path(__file__).resolve().parents[2] / "prompts" / "common" / "user.j2"
    )
    system_prompt_path = (
        Path(__file__).resolve().parents[2] / "prompts" / "checker" / "system.j2"
    )
    check_exploration_prompt_path = (
        Path(__file__).resolve().parents[2] / "prompts" / "checker" / "check_exploration.j2"
    )

    def __init__(
        self,
        agent_name: str,
        workgroup: Workgroup,
        agent_config: AgentConfig,
        *,
        workflow: "DefaultWorkflow",
    ) -> None:
        self.exploration_check_queue: Queue[ExplorationCheck] = Queue()
        submit_check_tool = register_agent_tool(
            submit_exploration_check, submit_check_operation=self.exploration_check_queue.put
        )
        super().__init__(agent_name, workgroup, agent_config, workflow=workflow, tools=[submit_check_tool])
        prompt_context = {
            "role_name": self.role_name,
            "agent_name": self.agent_name,
            "workgroup_name": self.workgroup.workgroup_name,
        }
        self.system_prompt = merge_prompts(
            [
                render_prompt(self.common_system_prompt_path),
                render_prompt(self.system_prompt_path, prompt_context),
            ]
        )

    @staticmethod
    async def check_exploration(workflow_state: dict[str, object]) -> None:
        """Review candidate/code_path and an explicit parent_node (None for a baseline).

        The caller may also supply parent_code_path, evidence (a list of references
        or observations), and the Explorer's review_question.
        """
        checker_agent = cast(CheckerAgent, workflow_state["agent"])
        prompt_context = {
            "candidate": workflow_state["candidate"],
            "code_path": workflow_state["code_path"],
            "parent_node": workflow_state["parent_node"],
            "parent_code_path": workflow_state.get("parent_code_path"),
        }
        user_prompt = merge_prompts(
            [
                render_prompt(checker_agent.common_user_prompt_path),
                render_prompt(checker_agent.check_exploration_prompt_path, prompt_context),
            ]
        )
        await checker_agent.send_message(user_prompt, expected_tool_calls=checker_agent.check_exploration_tools)
