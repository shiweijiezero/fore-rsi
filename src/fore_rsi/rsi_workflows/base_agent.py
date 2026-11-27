# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Common role interface for workflow agents backed by native harnesses."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from functools import wraps
from typing import TYPE_CHECKING, ClassVar, Literal

from fore_rsi.config import AgentConfig
from fore_rsi.rsi_workflows.agent_runtimes import AgentTool, create_agent_runtime
from fore_rsi.rsi_workflows.agent_runtimes.base_runtime import MessageDeliveryMode
from fore_rsi.rsi_workflows.workflow_runtimes.workgroup import Workgroup

if TYPE_CHECKING:
    from fore_rsi.rsi_workflows.base_workflow import BaseWorkflow


class AgentState(StrEnum):
    """Lifecycle states shared by agents and workflow scheduling."""

    READY = "ready"  # Runnable and eligible for scheduling.
    QUEUED = "queued"  # Enqueued for an execution slot.
    RUNNING = "running"  # A workflow prompt was dispatched and has not yet settled.
    SLEEPING = "sleeping"  # No runnable work until a message or dependency result arrives.
    PAUSING = "pausing"  # Settling native execution before releasing its slot.
    PAUSED = "paused"  # Scheduling disabled until the user or workflow explicitly resumes it.
    RETIRED = "retired"
    FAILED = "failed"


@dataclass(frozen=True)
class ExpectedToolCalls:
    """MCP tools a step must call successfully; set require_all=False for alternatives."""

    step: str
    tools: frozenset[str]
    require_all: bool = True

    def __post_init__(self) -> None:
        if not self.tools:
            raise ValueError(f"Step {self.step!r} must name at least one expected tool.")


type ToolSubmissionStatus = Literal["submitted", "not_submitted", "exceed_limit_try"]


@dataclass
class StepToolCalls:
    """Track one agent's successful expected tools for the current prompt in a workflow step."""

    expected: ExpectedToolCalls
    attempt_number: int
    successful_tools: set[str] = field(default_factory=set)
    outcome: ToolSubmissionStatus | None = None

    def has_expected_tool_calls(self) -> bool:
        """Tell the settle subflow whether the successful tool calls satisfy this step."""
        if self.expected.require_all:
            return self.expected.tools <= self.successful_tools
        return not self.expected.tools.isdisjoint(self.successful_tools)


class BaseAgent:
    """Base class for role-specific agents with a bound execution runtime."""

    role_name: ClassVar[str]

    def __init__(
        self,
        agent_name: str,
        workgroup: Workgroup,
        agent_config: AgentConfig,
        *,
        workflow: "BaseWorkflow",
        tools: Sequence[AgentTool] = (),
    ) -> None:
        """Create the member's unstarted runtime with the tools selected by its role."""
        self.agent_name = agent_name
        self.workgroup = workgroup
        self.agent_scheduler = workflow.agent_scheduler
        self.system_prompt: str | None = None
        self.state = AgentState.READY
        self.inbox: list[tuple[datetime, str]] = []
        self.step_tool_calls: StepToolCalls | None = None
        self.agent_runtime = create_agent_runtime(
            agent_config, workflow_directory=workflow.session_directory,
            workgroup_name=workgroup.workgroup_name, agent_name=agent_name,
            tool_mcp_host=workflow.tool_mcp_host,
            tools=[self.observe_tool_submission(tool) for tool in tools],
        )

    async def close(self) -> None:
        """Retire the agent and release its scheduler slot even if its runtime fails to close."""
        self.state = AgentState.RETIRED
        try:
            await self.agent_runtime.close()
        finally:
            await self.agent_scheduler.release(self)

    def add_to_inbox(self, message: str) -> None:
        """Timestamp an incoming message for the next prompt without starting a turn."""
        self.inbox.append((datetime.now(UTC), message))

    async def send_message(
        self,
        message: str,
        mode: MessageDeliveryMode = "queue",
        *,
        expected_tool_calls: ExpectedToolCalls | None = None,
    ) -> None:
        """Dispatch the prompt with pending inbox messages and bind its expected tool calls."""
        previous_step_tool_calls = self.step_tool_calls
        if expected_tool_calls is not None:
            attempt_number = 1
            if (
                previous_step_tool_calls is not None
                and previous_step_tool_calls.outcome == "not_submitted"
                and previous_step_tool_calls.expected == expected_tool_calls
            ):
                attempt_number = previous_step_tool_calls.attempt_number + 1
            self.step_tool_calls = StepToolCalls(expected_tool_calls, attempt_number)
        elif (
            mode == "queue"
            and previous_step_tool_calls is not None
            and previous_step_tool_calls.outcome is not None
        ):
            # Discard a finished step's result without disarming a still-running turn.
            self.step_tool_calls = None
        # Claim this batch before yielding so later mail stays in the inbox.
        pending = self.inbox.copy()
        self.inbox.clear()
        try:
            if pending:
                entries = [
                    f"[Received at {received_at.astimezone().isoformat(sep=' ', timespec='seconds')}]\n{text}"
                    for received_at, text in pending
                ]
                now = datetime.now(UTC).astimezone().isoformat(sep=" ", timespec="seconds")
                message = "\n\n".join([*entries, f"[Current time: {now}]\n{message}"])
            await self.agent_runtime.send_message(message, mode=mode)
        except BaseException:
            # Restore this batch ahead of any messages that arrived during the send.
            self.inbox[:0] = pending
            raise
        if mode == "queue" and self.state in (AgentState.READY, AgentState.QUEUED, AgentState.SLEEPING):
            self.state = AgentState.RUNNING

    async def wait_for_settle(self) -> None:
        """Wait for the workflow turn to finish, leaving paused or retired members in their state."""
        await self.agent_runtime.wait_for_settle()
        if self.state == AgentState.RUNNING:
            self.state = AgentState.SLEEPING

    def tool_submission_status(self, *, max_attempts: int) -> ToolSubmissionStatus:
        """Resolve the settled turn's expected tool calls once, counting the initial prompt as an attempt."""
        calls = self.step_tool_calls
        if calls is None:
            raise RuntimeError("The settled step did not declare its expected tool calls.")
        if calls.outcome is None:
            if calls.has_expected_tool_calls():
                calls.outcome = "submitted"
            elif calls.attempt_number >= max_attempts:
                calls.outcome = "exceed_limit_try"
            else:
                calls.outcome = "not_submitted"
        return calls.outcome

    def observe_tool_submission(self, tool: AgentTool) -> AgentTool:
        """Leave the payload with its owner and record successful expected calls for this member."""

        @wraps(tool)
        async def observed(*args: object, **kwargs: object) -> dict[str, object]:
            # A tool finishing late belongs to the prompt that started the call.
            step_tool_calls = self.step_tool_calls
            result = await tool(*args, **kwargs)
            if (
                step_tool_calls is not None
                and step_tool_calls.outcome is None
                and tool.__name__ in step_tool_calls.expected.tools
            ):
                step_tool_calls.successful_tools.add(tool.__name__)
            return result

        return observed

    def get_full_name(self) -> str:
        """Return the agent's workgroup-qualified name within its workflow."""
        return f"{self.workgroup.workgroup_name}/{self.agent_name}"
