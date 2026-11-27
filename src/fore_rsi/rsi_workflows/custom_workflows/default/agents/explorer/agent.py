# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Explorer role and workflow stages for the default collaboration workflow."""

from asyncio import Queue
from pathlib import Path
from typing import TYPE_CHECKING, cast

from fore_rsi.config import AgentConfig
from fore_rsi.rsi_workflows.agent_runtimes.tool_mcp import register_agent_tool
from fore_rsi.rsi_workflows.base_agent import BaseAgent, ExpectedToolCalls
from fore_rsi.rsi_workflows.workflow_runtimes.workgroup import Workgroup
from fore_rsi.utils.prompt_renderer import merge_prompts, render_prompt

from .tools import ExplorationSubmission, submit_exploration

if TYPE_CHECKING:
    from fore_rsi.rsi_workflows.custom_workflows.default.workflow import DefaultWorkflow


class ExplorerAgent(BaseAgent):
    """Explore approaches for the default workflow's task."""

    role_name = "Explorer"
    exploration_tools = ExpectedToolCalls(
        step="exploration", tools=frozenset({submit_exploration.__name__})
    )
    common_system_prompt_path = (
        Path(__file__).resolve().parents[2]
        / "prompts" / "common" / "system.j2"
    )
    common_user_prompt_path = (
        Path(__file__).resolve().parents[2]
        / "prompts" / "common" / "user.j2"
    )
    system_prompt_path = (
        Path(__file__).resolve().parents[2]
        / "prompts" / "explorer" / "system.j2"
    )
    exploration_prompt_path = (
        Path(__file__).resolve().parents[2]
        / "prompts" / "explorer" / "exploration.j2"
    )


    def __init__(
        self,
        agent_name: str,
        workgroup: Workgroup,
        agent_config: AgentConfig,
        *,
        workflow: "DefaultWorkflow",
    ) -> None:
        """Bind the Explorer's tools and instructions to this workflow session."""
        self.exploration_submission_queue: Queue[tuple[str, ExplorationSubmission]] = Queue()
        submit_exploration_tool = register_agent_tool(
            submit_exploration, record_submission=self.record_exploration_submission
        )
        super().__init__(
            agent_name,
            workgroup,
            agent_config,
            workflow=workflow,
            tools=[submit_exploration_tool],
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

    def record_exploration_submission(
        self, attempt_id: str, submission: ExplorationSubmission
    ) -> None:
        """Keep the submitted attempt and artifacts for the subflow to consume."""
        self.exploration_submission_queue.put_nowait((attempt_id, submission))

    @staticmethod
    async def exploration(workflow_state: dict[str, object]) -> None:
        """Send the confirmed direction and feedback to the Explorer."""
        explorer = cast(ExplorerAgent, workflow_state["agent"])

        feedback = workflow_state.get("feedback_for_exploration")

        feedback_type = None
        feedback_content = None

        if feedback is not None:
            if not isinstance(feedback, dict):
                raise ValueError("feedback_for_exploration must be a dictionary.")

            feedback_type = feedback.get("type")
            feedback_content = feedback.get("content")

        prompt_context = {
            "feedback_type": feedback_type,
            "feedback_content": feedback_content,
        }

        user_prompt = merge_prompts(
            [
                render_prompt(ExplorerAgent.common_user_prompt_path),
                render_prompt(
                    ExplorerAgent.exploration_prompt_path,
                    prompt_context,
                ),
            ]
        )

        await explorer.send_message(
            user_prompt,
            expected_tool_calls=explorer.exploration_tools,
        )
