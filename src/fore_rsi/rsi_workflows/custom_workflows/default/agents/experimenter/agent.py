# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Prepare an Experimenter conversation and collect the evidence from its assigned measurement."""

from pathlib import Path
from subprocess import CalledProcessError
from typing import TYPE_CHECKING

import httpx2
from websockets.exceptions import ConnectionClosed

from fore_rsi.config import AgentConfig
from fore_rsi.rsi_workflows.agent_runtimes.tool_mcp import register_agent_tool
from fore_rsi.rsi_workflows.base_agent import AgentState, BaseAgent, ExpectedToolCalls
from fore_rsi.rsi_workflows.workflow_runtimes.task import TaskRevision
from fore_rsi.rsi_workflows.workflow_runtimes.workgroup import Workgroup
from fore_rsi.utils.prompt_renderer import merge_prompts, render_prompt

from .tools import set_experiment_resources, submit_experiment_report

if TYPE_CHECKING:
    from ...workflow import DefaultWorkflow


NATIVE_TURN_ERRORS = (RuntimeError, OSError, CalledProcessError, httpx2.HTTPError, ConnectionClosed)


class ExperimenterAgent(BaseAgent):
    """Run a checked measurement in its allocated environment and report the observed outcome."""

    role_name = "Experimenter"
    prompts_dir = Path(__file__).resolve().parents[2] / "prompts"
    resource_request_tools = ExpectedToolCalls(
        step="set_experiment_resources", tools=frozenset({set_experiment_resources.__name__}),
    )
    report_tools = ExpectedToolCalls(step="run_experiment", tools=frozenset({submit_experiment_report.__name__}))

    def __init__(
        self, agent_name: str, workgroup: Workgroup, agent_config: AgentConfig, *, workflow: "DefaultWorkflow",
    ) -> None:
        """Bind the member's reporting tool; the experiment subflow owns the allocation and publication."""
        self.workflow = workflow
        self.choosing_for: TaskRevision | None = None
        self.report: tuple[str, str, bool] | None = None
        tools = [register_agent_tool(tool, experimenter=self) for tool in (
            set_experiment_resources, submit_experiment_report,
        )]
        super().__init__(agent_name, workgroup, agent_config, workflow=workflow, tools=tools)
        self.system_prompt = merge_prompts([
            render_prompt(self.prompts_dir / "common/system.j2"),
            (
                "You are the Experimenter. Keep the candidate unchanged and measure only the exploration item "
                "assigned to you. Use the task's authorized environment and report what actually happened."
            ),
        ])

    async def study_framework(self, task_file: Path) -> None:
        """Study the task's deployment and measurement paths in the seed conversation before forking."""
        await self.send_message(render_prompt(self.prompts_dir / "experimenter/study_framework.j2", {
            "task_file": task_file,
        }))
        await self.wait_for_settle()

    async def choose_resources(self, revision: TaskRevision) -> str | None:
        """Choose this member's share of the total budget; only a settled choice admits measurements."""
        team = self.workflow.experiments
        self.choosing_for = revision
        try:
            prompt = render_prompt(self.prompts_dir / "experimenter/choose_resources.j2", {
                "task_file": revision.revision_file_path.resolve(), "inventory": team.resource_units,
                "allocations": team.resource_assignments(),
            })
            submitted = await self.request_submission(prompt, self.resource_request_tools,
                retry_prompt="Complete your choice using `set_experiment_resources`.")
            return None if submitted else "No resource allocation was submitted."
        except NATIVE_TURN_ERRORS as error:
            self.state = AgentState.FAILED
            return f"Resource selection interrupted: {error}"
        finally:
            self.choosing_for = None

    def on_reply_requested(self) -> None:
        """Wake dispatch so an idle Experimenter can answer in its own conversation."""
        self.workflow.experiments.dispatch_requested.set()

    async def reply_to_teammates(self) -> None:
        """Answer unread questions without starting a measurement."""
        try:
            await self.send_message(
                "Answer the pending teammate questions using `send_team_message`. Do not start an experiment. "
                "Coordinate resource changes with their owners; record your own full set with "
                "`set_experiment_resources` before confirming a release or using newly claimed units."
            )
            await self.wait_for_settle()
        except NATIVE_TURN_ERRORS:
            self.state = AgentState.FAILED

    async def run_experiment(self, exploration_item_id: str, resource_grant: str) -> tuple[str, str, bool]:
        """Return the report, its node label and whether the allocated resources are safe to reuse.

        [first prompt: execute approved commands] --> [wait_for_settle]
            +-- report submitted --> return evidence and cleanup status
            +-- report missing, attempts remain --> request existing evidence only --> [wait_for_settle]
            +-- attempts exhausted or turn interrupted --> return with cleanup unconfirmed
        """
        self.report = None
        tool = submit_experiment_report.__name__
        revision = self.workflow.task.current_task
        assert revision is not None
        exploration_pool = self.workflow.exploration_pool
        exploration_item = exploration_pool.get(exploration_item_id)
        prompt = render_prompt(self.prompts_dir / "experimenter/run_experiment.j2", {
            "task_file": revision.revision_file_path.resolve(), "exploration_item": exploration_item,
            "exploration_record_path": exploration_pool.exploration_record_path(exploration_item_id, name=exploration_item.name),
            "resource_grant": resource_grant, "allocations": self.workflow.experiments.resource_assignments(), "tool": tool,
        })

        # A missing report does not mean the measurement never ran. Only the first turn may start it.
        report_only = (
            f"Call `{tool}` for item {exploration_item_id} with the detailed report and one short experiment_summary. "
            "Do not start or repeat the measurement. Inspect the existing job or artifacts; if the outcome "
            "or cleanup is unknown, say so. Set resources_released only if reuse is confirmed safe."
        )
        try:
            submitted = await self.request_submission(prompt, self.report_tools, retry_prompt=report_only)
        except NATIVE_TURN_ERRORS as error:
            # The command may have reached the environment. Preserve any report already received.
            self.state = AgentState.FAILED
            return self.unsettled_report(f"Native turn did not settle: {error}")
        if submitted:
            assert self.report is not None
            return self.report
        return self.unsettled_report("Report submission attempts exhausted.")

    def unsettled_report(self, reason: str) -> tuple[str, str, bool]:
        """Keep submitted evidence even if its native turn was interrupted before cleanup settled."""
        report, experiment_summary, _ = self.report or ("No experiment report was received.", "No report", False)
        return f"{report}\n\n{reason}\nResource cleanup is unconfirmed.", experiment_summary, False
