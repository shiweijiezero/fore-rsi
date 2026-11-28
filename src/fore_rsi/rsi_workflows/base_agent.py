# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Common role interface for workflow agents backed by native harnesses."""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from functools import wraps
from typing import TYPE_CHECKING, ClassVar, Literal, TypedDict

from mcp.server.mcpserver.exceptions import ToolError

from fore_rsi.config import AgentConfig
from fore_rsi.rsi_workflows.agent_runtimes import AgentTool, create_agent_runtime
from fore_rsi.rsi_workflows.agent_runtimes.base_runtime import MessageDeliveryMode
from fore_rsi.rsi_workflows.types import RequiredText
from fore_rsi.rsi_workflows.workflow_runtimes.workgroup import Workgroup
from fore_rsi.utils.terminal import run_terminal

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


class InboxMessage(TypedDict):
    """One unread message, with the sender bound by the workflow rather than supplied in the text."""

    sender: str
    received_at: str
    message: str
    request_reply: bool


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
        self.workflow_config = workflow.config
        self.system_prompt: str | None = None
        self.state = AgentState.READY
        self.inbox: list[InboxMessage] = []
        self.step_tool_calls: StepToolCalls | None = None
        self.agent_runtime = create_agent_runtime(
            agent_config, workflow_directory=workflow.session_directory,
            workgroup_name=workgroup.workgroup_name, agent_name=agent_name,
            tool_mcp_host=workflow.tool_mcp_host,
            tools=[
                self.list_team_members, self.send_team_message, self.read_team_messages,
                *(self.observe_tool_submission(tool) for tool in tools),
            ],
        )

    async def retain_as_fork_source(self) -> None:
        """Keep this settled member in its group for forks and shutdown, without holding an execution slot."""
        if self.state != AgentState.SLEEPING:
            raise RuntimeError("Wait for the seed's final turn to settle before retaining it.")
        await self.agent_scheduler.release(self)
        self.agent_runtime.retained_for_fork = True
        self.inbox.clear()

    async def close(self) -> None:
        """Retire the agent and release its scheduler slot even if its runtime fails to close."""
        self.step_tool_calls = None  # Disarm any unfinished submission before closing the tool endpoint.
        self.state = AgentState.RETIRED
        try:
            await self.agent_runtime.close()
        finally:
            await self.agent_scheduler.release(self)

    async def list_team_members(self) -> dict[str, object]:
        """List reachable teammates in this workflow and return your own name. Address messages by exact name."""
        teammates = await self.live_teammates()
        return {
            "your_name": self.get_full_name(),
            "members": [
                {"name": name, "session_name": member.agent_runtime.session_display_name,
                 "role": member.role_name, "state": member.state.value}
                for name, member in teammates.items()
            ],
        }

    async def send_team_message(
        self, recipient: RequiredText, message: RequiredText, request_reply: bool = False,
    ) -> dict[str, str]:
        """Queue a note for the exact teammate from list_team_members. Set request_reply only for a needed answer.

        Queued does not mean read. The recipient can read the note this turn or on its next workflow prompt.
        A peer message does not start a measurement or grant access to resources.
        """
        teammates = await self.live_teammates()
        member = teammates.get(recipient)
        if member is None:
            raise ToolError(f"No reachable teammate named {recipient!r}. Use list_team_members for current names.")
        member.add_to_inbox(message, sender=self, request_reply=request_reply)
        return {"queued_for": recipient}

    async def read_team_messages(self) -> dict[str, list[InboxMessage]]:
        """Take unread messages from your own inbox now, including workflow notices. An empty inbox returns immediately."""
        if not self.accepts_team_messages:
            raise ToolError("This session is not an active team member.")
        return {"messages": self.take_inbox()}

    @property
    def accepts_team_messages(self) -> bool:
        """Whether this member still owns a working session rather than a seed or retired conversation."""
        return (self in self.agent_scheduler.active_agents and not self.workgroup.is_fork_seed
                and self.state in (AgentState.READY, AgentState.RUNNING, AgentState.SLEEPING))

    async def live_teammates(self) -> dict[str, "BaseAgent"]:
        """Resolve scheduler membership against the live native panes for this workflow's terminal session."""
        result = await run_terminal(["agent", "list"], self.agent_runtime.terminal_session_name, capture_output=True)
        live = {
            (native["terminal_id"], native.get("agent")) for native in json.loads(result.stdout)["result"]["agents"]
            if native.get("interactive_ready") and native.get("name") == native["terminal_id"]
        }
        # Querying the terminal yielded. Recheck the sender and recipients before returning any addresses.
        if not self.accepts_team_messages:
            raise ToolError("This session is not an active team member.")
        return {
            member.get_full_name(): member for member in self.agent_scheduler.active_agents
            if member is not self and member.accepts_team_messages
            and (member.agent_runtime.terminal_id, member.agent_runtime.harness_name) in live
        }

    def add_to_inbox(self, message: str, *, sender: "BaseAgent | None" = None, request_reply: bool = False) -> None:
        """Queue a workflow notice or an attributed peer message without interrupting the recipient's turn."""
        self.inbox.append({
            "sender": "workflow" if sender is None else sender.get_full_name(),
            "received_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "message": message,
            "request_reply": request_reply,
        })
        if request_reply:
            self.on_reply_requested()

    @property
    def has_reply_request(self) -> bool:
        """Tell the role's scheduler whether a request for a reply is still unread."""
        return any(entry["request_reply"] for entry in self.inbox)

    def on_reply_requested(self) -> None:
        """A role may notify its scheduler of unread questions; the scheduler decides when it can take a turn."""

    def take_inbox(self) -> list[InboxMessage]:
        """Claim the current batch for a tool call or prompt before another message can arrive."""
        pending, self.inbox = self.inbox, []
        return pending

    async def send_message(
        self,
        message: str,
        mode: MessageDeliveryMode = "queue",
        *,
        expected_tool_calls: ExpectedToolCalls | None = None,
    ) -> None:
        """Dispatch the prompt with pending inbox messages and bind its expected tool calls."""
        if self.state in (AgentState.RETIRED, AgentState.FAILED):
            raise RuntimeError(f"{self.agent_name} is {self.state.value} and cannot receive workflow prompts.")
        if self.agent_runtime.retained_for_fork:
            raise RuntimeError(f"{self.agent_name} is retained for forks and cannot receive workflow prompts.")
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
        pending = self.take_inbox()
        try:
            if pending:
                now = datetime.now(UTC).astimezone().isoformat(sep=" ", timespec="seconds")
                message = f"Unread messages:\n{json.dumps(pending, ensure_ascii=False)}\n\n[Current time: {now}]\n{message}"
            await self.agent_runtime.send_message(message, mode=mode)
        except BaseException:
            # Restore this batch ahead of any messages that arrived during the send.
            self.inbox[:0] = pending
            if any(entry["request_reply"] for entry in pending):
                self.on_reply_requested()
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

    async def request_submission(
        self, prompt: str, expected: ExpectedToolCalls, *, max_attempts: int | None = None, retry_prompt: str | None = None,
    ) -> bool:
        """Wait for the required MCP calls, retrying only a settled turn with a missing submission.

        A step can cap the workflow's attempt limit or supply a report-only prompt when its work must not be repeated.
        """
        limit = self.workflow_config.max_attempts
        if max_attempts is not None:
            limit = min(limit, max_attempts)
        if limit <= 0:
            return False

        status: ToolSubmissionStatus = "not_submitted"
        while status == "not_submitted":
            try:
                await self.send_message(prompt, expected_tool_calls=expected)
                await self.wait_for_settle()
            except BaseException:
                # The native turn may outlive cancellation. Disarm its tools before the caller
                # releases a direction, checkout or measurement assignment.
                if self.step_tool_calls is not None and self.step_tool_calls.expected is expected:
                    self.step_tool_calls = None
                raise
            status = self.tool_submission_status(max_attempts=limit)
            if retry_prompt is not None:
                prompt = retry_prompt
        return status == "submitted"

    def require_tool_submission(self, tool_name: str) -> None:
        """Reject a role tool called outside its requested step or after its submission was accepted."""
        calls = self.step_tool_calls
        if calls is None or calls.outcome is not None or tool_name not in calls.expected.tools:
            raise ToolError(f"The current step is not requesting {tool_name}.")
        if tool_name in calls.successful_tools or calls.has_expected_tool_calls():
            raise ToolError("The submission for this step has already been accepted.")

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
