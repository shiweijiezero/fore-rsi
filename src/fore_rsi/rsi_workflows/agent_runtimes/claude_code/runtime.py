# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Control the foreground conversation in a member's Claude Code terminal."""

import asyncio
import json
import os
import sys
from collections import deque
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from fore_rsi.config import AgentConfig, ReasoningEffort
from fore_rsi.rsi_workflows.agent_runtimes.base_runtime import (
    AgentRuntime,
    MessageDeliveryMode,
)
from fore_rsi.rsi_workflows.agent_runtimes.claude_code.record_file import (
    bind_session_transcript,
    fork_claude_session,
    get_claude_project_link,
    prepare_claude_session,
    remove_project_link,
    session_directory,
)
from fore_rsi.rsi_workflows.agent_runtimes.installation import get_or_install_cli
from fore_rsi.rsi_workflows.agent_runtimes.tool_mcp import (
    AgentTool,
    ToolMcpHost,
    create_tool_mcp,
)
from fore_rsi.utils.paths import write_private_text
from fore_rsi.utils.terminal import PaneLocation


class ClaudeCodeAgentRuntime(AgentRuntime):
    """Deliver workflow input to one visible Claude session without editing its prompt box."""

    harness_name = "claude"

    def __init__(
        self,
        agent_config: AgentConfig,
        workflow_directory: Path,
        *,
        workgroup_name: str,
        agent_name: str,
        tool_mcp_host: ToolMcpHost,
        tools: Sequence[AgentTool] = (),
    ) -> None:
        """Bind the member's input stream and native turn notifications to its private route."""
        super().__init__(
            agent_config,
            workflow_directory,
            workgroup_name=workgroup_name,
            agent_name=agent_name,
            tool_mcp_host=tool_mcp_host,
            tools=tools,
        )
        if self.tool_mcp is None:
            self.tool_mcp = create_tool_mcp(())
        self.tool_mcp.custom_route("/inputs", methods=["GET"])(self.open_inputs)
        self.tool_mcp.custom_route("/turn", methods=["POST"])(self.on_turn_event)
        self.profile_environment: dict[str, str] = {}
        self.conversation_id: str | None = None
        self.changed = asyncio.Condition()
        self.connected = False
        self.queue: deque[str] = deque()
        self.steers: deque[str] = deque()
        self.awaiting_start = False
        self.active_turn: str | None = None
        self.workflow_turn: str | None = None
        self.failure: str | None = None

    def conversation_files(self) -> tuple[Path, ...]:
        """Locate the transcript under the member's workflow-owned Claude project."""
        if self.conversation_id is None:
            return ()
        path = session_directory(self.get_agent_file_path("")) / f"{self.conversation_id}.jsonl"
        return (path.resolve(),) if path.is_file() else ()

    async def fork_from(self, seed: AgentRuntime) -> None:
        """Prepare the child TUI to fork the seed's transcript with its own UUID and tool endpoint."""
        fork_claude_session(seed.get_agent_file_path(""), self.get_agent_file_path(""))

    async def wait_for_agent_ready(self, pane: PaneLocation, agent: dict[str, object]) -> dict[str, object]:
        """Require both the visible TUI and its input channel before publishing readiness."""
        agent = await super().wait_for_agent_ready(pane, agent)
        try:
            async with asyncio.timeout(30), self.changed:
                await self.changed.wait_for(lambda: self.connected or self.failure is not None)
        except TimeoutError as error:
            raise RuntimeError(
                "Claude Code did not connect its ForeRSI turn plugin. Check the member terminal."
            ) from error
        if not self.connected:
            raise RuntimeError(self.failure)
        return agent

    async def send_message(self, message: str, mode: MessageDeliveryMode = "queue") -> None:
        """Accept one input without waiting for its turn. Steers precede ordinary queued work."""
        if mode not in {"queue", "steer"} or not message.strip():
            raise ValueError("Claude Code requires a nonempty queue or steer message.")
        async with self.changed:
            if not self.connected or self.terminal_id is None:
                raise RuntimeError("Claude Code's input channel is not connected.")
            (self.steers if mode == "steer" else self.queue).append(message)
            self.changed.notify_all()

    async def open_inputs(self, request: Request) -> Response:
        """Stream input to this member's mod; ordinary prompts stay queued until the foreground is idle."""
        if self.connected:
            return Response(status_code=409)
        self.connected = True

        async def inputs() -> AsyncIterator[bytes]:
            try:
                async with self.changed:
                    self.changed.notify_all()
                while self.connected:
                    async with self.changed:
                        await self.changed.wait_for(
                            lambda: (
                                not self.connected
                                or (
                                    not self.awaiting_start
                                    and (self.steers or (self.active_turn is None and self.queue))
                                )
                            )
                        )
                        if not self.connected:
                            return
                        mode, messages = ("steer", self.steers) if self.steers else ("queue", self.queue)
                        self.awaiting_start = True
                        line = json.dumps({"mode": mode, "text": messages.popleft()}) + "\n"
                    yield line.encode()
            finally:
                await self.disconnect()

        return StreamingResponse(inputs(), media_type="application/x-ndjson")

    async def on_turn_event(self, request: Request) -> Response:
        """Associate the dispatched prompt with its native turn; a manual turn owns only the foreground."""
        event = await request.json()
        if event["session_id"] != self.conversation_id:
            return Response(status_code=409)
        async with self.changed:
            kind = event.get("event")
            if kind == "session":
                bind_session_transcript(self.get_agent_file_path(""), Path(event["transcript"]))
            elif kind == "start":
                self.active_turn = event["turnId"]
                if event["workflow"]:
                    self.workflow_turn = self.active_turn
                    self.awaiting_start = False
            elif kind == "complete":
                turn = event["turnId"]
                if self.active_turn == turn:
                    self.active_turn = None
                if self.workflow_turn == turn:
                    self.workflow_turn = None
                    if event["reason"] not in {"answer", "steered"}:
                        self.failure = f"Claude Code turn ended: {event['reason']}"
            elif kind == "failed":
                self.failure = event["error"]
                self.awaiting_start = False
            elif event.get("hook_event_name") == "PermissionRequest" and not event.get("agent_id"):
                self.failure = "Claude Code is waiting for permission in the member terminal."
            self.changed.notify_all()
        return Response(status_code=200)

    async def wait_for_settle(self) -> None:
        """Wait for all accepted inputs, including steers arriving during an earlier turn."""
        async with self.changed:
            await self.changed.wait_for(
                lambda: (
                    self.failure is not None
                    or not self.connected
                    or (not self.steers and not self.queue and not self.awaiting_start and self.workflow_turn is None)
                )
            )
            if self.failure is not None:
                failure, self.failure = self.failure, None
                raise RuntimeError(failure)
            if not self.connected:
                raise RuntimeError("Claude Code's input channel closed.")

    async def disconnect(self) -> None:
        """Release waiters and discard undelivered inputs when their owning session disconnects."""
        async with self.changed:
            self.connected = False
            self.queue.clear()
            self.steers.clear()
            self.awaiting_start = False
            self.active_turn = self.workflow_turn = None
            self.changed.notify_all()

    async def close(self) -> None:
        """Close the input stream before stopping the member; keep its native conversation."""
        await self.disconnect()
        await super().close()
        self.failure = None

    @classmethod
    async def ensure_installed(cls) -> Path:
        """Return Claude Code's launcher for startup callers, installing it when missing."""
        return await get_or_install_cli(
            cls.harness_name,
            Path.home() / ".local" / "bin" / ("claude.exe" if os.name == "nt" else "claude"),
            "https://claude.ai/install.ps1" if os.name == "nt" else "https://claude.ai/install.sh",
            shell="bash",
        )

    def build_launch_command(
        self,
        executable: Path,
        arguments: Sequence[str] = (),
        *,
        system_prompt: str | None = None,
    ) -> list[str]:
        """Bind the session, its turn plugin and role tools without replacing the user's Claude profile."""
        profile = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser().resolve()
        self.profile_environment, session_arguments, self.conversation_id = prepare_claude_session(
            self.get_agent_file_path(""), profile
        )
        url = self.tool_mcp_host.tool_endpoints[self.tool_mcp].url.rsplit("/", 1)[0] + "/turn"
        hooks = {"PermissionRequest": [{"hooks": [{"type": "http", "url": url}]}]}
        options = [
            *session_arguments,
            "--name", self.session_display_name,
            "--plugin-dir",
            str(Path(__file__).with_name("turn_events")),
            "--settings",
            json.dumps({"hooks": hooks}),
        ]
        if self.agent_config.model is not None:
            options.extend(["--model", self.agent_config.model])
        if self.agent_config.effort is not None:
            options.extend(self.effort_args(self.agent_config.effort))
        if system_prompt is not None:
            instructions = self.get_agent_file_path(".instructions.md")
            write_private_text(instructions, system_prompt)
            options.extend(["--append-system-prompt-file", str(instructions)])
        return super().build_launch_command(executable, [*options, *arguments], system_prompt=system_prompt)

    def launch_environment(self) -> dict[str, str]:
        """Pass the stable discovery file to this pane, including when the session is resumed."""
        env = {
            "FORE_RSI_MCP_ADDRESS_FILE": str(self.get_agent_file_path(".mcp-url")),
            "FORE_RSI_PYTHON": sys.executable,
        }
        if "CLAUDE_CONFIG_DIR" in os.environ:
            env["CLAUDE_CONFIG_DIR"] = os.environ["CLAUDE_CONFIG_DIR"]
        return env | self.profile_environment

    def effort_args(self, effort: ReasoningEffort) -> list[str]:
        """Set the reasoning level for this Claude Code invocation."""
        return ["--effort", effort]

    def tool_mcp_args(self) -> list[str]:
        """Add the role's tool client without replacing other configured MCP servers."""
        if not self.tools:
            return []
        config = {"mcpServers": {"fore_rsi": self.tool_stdio_server()}}
        return [f"--mcp-config={json.dumps(config, ensure_ascii=False)}"]

    @classmethod
    def remove_workflow_storage(cls, workflow_directory: Path) -> None:
        """Remove only Claude project links still pointing to this workflow."""
        claude_directory = workflow_directory / "harnesses" / "claude"
        for record in claude_directory.glob("member-*.session"):
            binding = json.loads(record.read_bytes())
            conversation = str(binding["id"])
            project_directory = session_directory(record)
            if "native_profile" not in binding:
                profile = Path(binding.get("profile") or binding["home"])
                remove_project_link(get_claude_project_link(profile, conversation), project_directory)
            if "transcript_link" in binding:
                remove_project_link(Path(binding["transcript_link"]), project_directory / f"{conversation}.jsonl")
