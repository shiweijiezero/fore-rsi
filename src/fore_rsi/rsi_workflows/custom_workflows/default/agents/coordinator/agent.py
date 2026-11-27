# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Coordinator role for the default collaboration workflow."""

from pathlib import Path
from typing import TYPE_CHECKING

from fore_rsi.config import AgentConfig
from fore_rsi.rsi_workflows.agent_runtimes.tool_mcp import register_agent_tool
from fore_rsi.rsi_workflows.base_agent import BaseAgent, ExpectedToolCalls
from fore_rsi.rsi_workflows.custom_workflows.default.agents.coordinator.tools import (
    submit_task,
)
from fore_rsi.rsi_workflows.workgroup import Workgroup
from fore_rsi.utils.prompt_renderer import merge_prompts, render_prompt

if TYPE_CHECKING:
    from fore_rsi.rsi_workflows.custom_workflows.default.workflow import DefaultWorkflow


class CoordinatorAgent(BaseAgent):
    """Handle user requests and coordinate the default workflow's team."""

    role_name = "Coordinator"
    common_system_prompt_path = (
        Path(__file__).resolve().parents[2] / "prompts" / "common" / "system.j2"
    )
    common_user_prompt_path = (
        Path(__file__).resolve().parents[2] / "prompts" / "common" / "user.j2"
    )
    system_prompt_path = (
        Path(__file__).resolve().parents[2] / "prompts" / "coordinator" / "system.j2"
    )
    parse_task_prompt_path = (
        Path(__file__).resolve().parents[2] / "prompts" / "coordinator" / "parse_task.j2"
    )
    parse_task_tools = ExpectedToolCalls(step="parse_task", tools=frozenset({submit_task.__name__}))

    def __init__(
        self,
        agent_name: str,
        workgroup: Workgroup,
        agent_config: AgentConfig,
        *,
        workflow: "DefaultWorkflow",
    ) -> None:
        """Bind the Coordinator's tools and instructions to this workflow session."""
        submit_task_tool = register_agent_tool(
            submit_task,
            accept_task=workflow.accept_task,
        )
        super().__init__(
            agent_name,
            workgroup,
            agent_config,
            workflow=workflow,
            tools=[submit_task_tool],
        )
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

    async def parse_task(self, task_file: Path) -> None:
        """Prompt the Coordinator to read the task file and deliver its declaration through submit_task."""
        user_prompt = merge_prompts(
            [
                render_prompt(self.common_user_prompt_path),
                render_prompt(self.parse_task_prompt_path, {"startup_task_file": str(task_file)}),
            ]
        )
        await self.send_message(user_prompt, expected_tool_calls=self.parse_task_tools)
