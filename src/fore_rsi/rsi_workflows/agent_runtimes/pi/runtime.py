# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Run one workflow member in the Pi terminal with its own record file and tools."""

import asyncio
import json
import os
import secrets
import socket
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NotRequired, Self, TypedDict
from uuid import uuid4

import httpx2

from fore_rsi.config import AgentConfig
from fore_rsi.rsi_workflows.agent_runtimes.base_runtime import (
    AgentRuntime,
    MessageDeliveryMode,
)
from fore_rsi.rsi_workflows.agent_runtimes.installation import get_or_install_cli
from fore_rsi.rsi_workflows.agent_runtimes.pi.record_file import (
    PiLiveSessionState,
    PiSessionState,
    read_record_file_state,
)
from fore_rsi.rsi_workflows.agent_runtimes.tool_mcp import AgentTool, ToolMcpHost
from fore_rsi.utils.paths import write_private_text
from fore_rsi.utils.terminal import PaneLocation, terminal_executable


class IpcEndpoint(TypedDict):
    """Address and private capability for a running member's local IPC listener."""

    token: str
    socket_path: NotRequired[str]
    port: NotRequired[int]


class PiAgentRuntime(AgentRuntime):
    """Runtime contract for Pi's CLI."""

    harness_name = "pi"
    readiness_timeout_seconds = 30  # Bounds native startup/acknowledgement, not execution time.

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
        """Create a Pi runtime with an in-memory IPC address shared with its extension."""
        super().__init__(
            agent_config,
            workflow_directory,
            workgroup_name=workgroup_name,
            agent_name=agent_name,
            tool_mcp_host=tool_mcp_host,
            tools=tools,
        )
        self.ipc_endpoint = self.create_ipc_endpoint()
        self.pending_settled_seq: int | None = None
        self.binding_file = self.get_agent_file_path("").resolve() / "fork.json"
        self.branch: dict[str, str] | None = (
            json.loads(self.binding_file.read_bytes()) if self.binding_file.is_file() else None
        )

    def conversation_files(self) -> tuple[Path, ...]:
        """Locate this Pi member's own bound JSONL, never its fork source."""
        if self.branch is not None and "record_file" not in self.branch:
            return ()
        path = self.record_file
        return (path.resolve(),) if path.is_file() else ()

    async def fork_from(self, seed: Self) -> None:
        """Reserve a fresh member directory and tell Pi which seed transcript to fork on launch."""
        if self.branch is not None or self.get_agent_file_path(".jsonl").exists():
            raise FileExistsError(f"Pi member {self.workgroup_name}/{self.agent_name} already has a session.")
        branch = {"id": str(uuid4()), "seed": str(seed.record_file.resolve(strict=True))}
        self.binding_file.parent.mkdir(parents=True, mode=0o700, exist_ok=False)
        write_private_text(self.binding_file, json.dumps(branch))
        self.branch = branch

    @property
    def record_file(self) -> Path:
        """Locate the member's saved transcript for inspection or as the parent of another fork."""
        if self.branch is None:
            return self.get_agent_file_path(".jsonl")
        if "record_file" not in self.branch:
            raise RuntimeError(f"Pi has not reported a transcript for {self.agent_name}.")
        return self.binding_file.parent / self.branch["record_file"]

    def create_ipc_endpoint(self) -> IpcEndpoint:
        """Use a workflow-local Unix socket when it fits, otherwise connect over authenticated loopback."""
        endpoint: IpcEndpoint = {"token": secrets.token_urlsafe(32)}
        path = str(self.get_agent_file_path(".ipc.sock"))
        # macOS sockaddr_un has 104 bytes including the terminating NUL.
        if os.name != "nt" and len(os.fsencode(path)) < 104:
            endpoint["socket_path"] = path
        else:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                endpoint["port"] = listener.getsockname()[1]
        return endpoint

    @classmethod
    async def ensure_installed(cls) -> Path:
        """Return Pi's launcher for startup callers, using the official installer when missing."""
        agent_directory = Path(os.environ.get("PI_CODING_AGENT_DIR", Path.home() / ".pi" / "agent"))
        return await get_or_install_cli(
            cls.harness_name,
            agent_directory / "bin" / ("pi.cmd" if os.name == "nt" else "pi"),
            "https://pi.dev/install.ps1" if os.name == "nt" else "https://pi.dev/install.sh",
        )

    def build_launch_command(
        self,
        executable: Path,
        arguments: Sequence[str] = (),
        *,
        system_prompt: str | None = None,
    ) -> list[str]:
        """Open this member's record file with Pi's lifecycle hook, role instructions and tools."""
        self.harness_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Pi deduplicates extensions by path. Reuse the terminal hook if the user already installed it.
        profile = Path(os.environ.get("PI_CODING_AGENT_DIR") or Path.home() / ".pi" / "agent").expanduser()
        hook = profile / "extensions" / "herdr-agent-state.ts"
        integrations = Path(__file__).resolve().parent
        if not hook.is_file():
            hook = terminal_executable().with_name(hook.name)
        launch_arguments = ["--approve", "--name", self.session_display_name, "--extension", str(integrations / "ipc.ts")]
        if "socket_path" in self.ipc_endpoint:
            launch_arguments.extend(["--fore-rsi-ipc-socket", self.ipc_endpoint["socket_path"]])
        else:
            launch_arguments.extend(["--fore-rsi-ipc-port", str(self.ipc_endpoint["port"])])
        launch_arguments.extend(["--fore-rsi-ipc-token", self.ipc_endpoint["token"], "--extension", str(hook)])
        launcher = []
        if self.branch is None:
            launch_arguments.extend(["--session-dir", str(self.harness_directory), "--session", str(self.record_file)])
        else:
            # The pane replays this argv verbatim. Select fork or resume when it actually launches.
            launcher = [sys.executable, "-I", "-S", str(integrations / "pi_fork.py"), str(self.binding_file)]
        if self.agent_config.model is not None:
            launch_arguments.extend(["--model", self.agent_config.model])
        if self.agent_config.effort is not None:
            launch_arguments.extend(["--thinking", self.agent_config.effort])
        instructions = self.get_agent_file_path(".instructions.md")
        if system_prompt is not None:
            write_private_text(instructions, system_prompt)
        if instructions.is_file():
            launch_arguments.extend(["--append-system-prompt", str(instructions)])
        return [*launcher, *super().build_launch_command(executable, [*launch_arguments, *arguments])]

    async def close(self) -> None:
        """Stop Pi and remove a private Unix socket left by an interrupted agent process."""
        try:
            await super().close()
        finally:
            socket_path = self.ipc_endpoint.get("socket_path")
            if socket_path:
                Path(socket_path).unlink(missing_ok=True)

    async def send_message(
        self,
        message: str,
        mode: MessageDeliveryMode = "queue",
    ) -> None:
        """Deliver a user message through Pi's steer or follow-up queue."""
        if mode not in {"queue", "steer"}:
            raise ValueError(f"Unsupported Pi message delivery mode: {mode!r}")
        async with self.message_lock:
            agent = await self.get_agent()
            if agent is None:
                raise RuntimeError("Start the Pi member before sending a message.")
            await self.live_session_state(agent)
            async with self.ipc_client() as client:
                response = await client.post("/message", json={"message": message, "mode": mode})
                response.raise_for_status()
                self.pending_settled_seq = response.json()["after"]

    async def wait_for_settle(self) -> None:
        """Wait for Pi's agent_settled event after the last submitted message."""
        if self.pending_settled_seq is None:
            raise RuntimeError("Submit a Pi message before waiting for settle.")
        async with self.ipc_client() as client:
            # Pi sends headers when a turn is running and the body when it settles. Only the
            # acknowledgement has a deadline; a slow measurement is not a disconnected session.
            timeout = httpx2.Timeout(**(client.timeout.as_dict() | {"read": None}))
            while (after := self.pending_settled_seq) is not None:
                request = client.build_request("GET", "/settled", params={"after": after}, timeout=timeout)
                async with asyncio.timeout(self.readiness_timeout_seconds):
                    response = await client.send(request, stream=True)
                try:
                    response.raise_for_status()
                    await response.aread()
                    aborted = response.json()["aborted"]
                finally:
                    await response.aclose()
                async with self.message_lock:
                    if self.pending_settled_seq == after:
                        self.pending_settled_seq = None
                        if aborted:
                            raise RuntimeError("Pi's workflow turn was aborted.")
                        return

    def ipc_client(self, *, connect_retries: int = 0) -> httpx2.AsyncClient:
        """Connect to the member's private endpoint; only startup waits for a listener to appear."""
        socket_path = self.ipc_endpoint.get("socket_path")
        transport = httpx2.AsyncHTTPTransport(uds=socket_path, retries=connect_retries, trust_env=False)
        base_url = "http://pi" if socket_path else f"http://127.0.0.1:{self.ipc_endpoint['port']}"
        return httpx2.AsyncClient(
            base_url=base_url,
            transport=transport,
            trust_env=False,
            headers={"Authorization": f"Bearer {self.ipc_endpoint['token']}"},
        )

    async def live_session_state(self, agent: dict[str, object], *, connect_retries: int = 0) -> PiLiveSessionState:
        """Confirm that the terminal and IPC refer to the member's session before accepting its state."""
        async with self.ipc_client(connect_retries=connect_retries) as client:
            response = await client.get("/state")
            response.raise_for_status()
            state: PiLiveSessionState = response.json()
        record = Path(state["record_file"]).resolve()
        session = agent.get("agent_session")
        if (not isinstance(session, dict) or session.get("kind") != "path"
                or Path(session["value"]).resolve() != record):
            raise RuntimeError("Pi's terminal and IPC did not report the same transcript.")

        # Pi chooses the fork filename. Bind it only after the new ID and private directory match.
        if self.branch is not None:
            if state["session_id"] != self.branch["id"] or record.parent != self.binding_file.parent:
                raise RuntimeError(f"Pi did not open the requested branch for {self.agent_name}.")
            if "record_file" not in self.branch:
                binding = {**self.branch, "record_file": record.name}
                write_private_text(self.binding_file, json.dumps(binding))
                self.branch = binding
        if record != self.record_file.resolve():
            raise RuntimeError(f"Pi is using another member's transcript: {record}")
        return state

    async def session_state(self) -> tuple[PiSessionState | PiLiveSessionState, str]:
        """Read the member's current settings from IPC while running or its own transcript when stopped."""
        agent = await self.get_agent()
        if agent is None:
            return await asyncio.to_thread(read_record_file_state, self.record_file), "stopped"
        return await self.live_session_state(agent), agent["agent_status"]

    async def wait_for_agent_ready(self, pane: PaneLocation, agent: dict[str, object]) -> dict[str, object]:
        """Bind the native transcript before the workflow can send its first message."""
        agent = await super().wait_for_agent_ready(pane, agent)
        # The terminal can recognize Pi before its session_start extensions finish opening IPC.
        # Retry connection establishment for this read only; prompts are never replayed.
        async with asyncio.timeout(self.readiness_timeout_seconds):
            await self.live_session_state(agent, connect_retries=7)
        return agent

    def tool_mcp_args(self) -> list[str]:
        """Pass the discovery file, not a host-specific capability, in the replayable argv."""
        extension = Path(__file__).resolve().with_name("tool_mcp.ts")
        return ["--extension", str(extension), "--fore-rsi-mcp-file", str(self.get_agent_file_path(".mcp-url"))]
