# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Run one workflow member in the Codex terminal lifecycle."""

import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Self

from fore_rsi.config import AgentConfig, ReasoningEffort
from fore_rsi.rsi_workflows.agent_runtimes.base_runtime import (
    AgentRuntime,
    MessageDeliveryMode,
)
from fore_rsi.rsi_workflows.agent_runtimes.codex.app_server import CodexAppServer
from fore_rsi.rsi_workflows.agent_runtimes.codex.record_file import (
    get_codex_thread,
    prepare_codex_profile,
    thread_record_files,
)
from fore_rsi.rsi_workflows.agent_runtimes.installation import get_or_install_cli
from fore_rsi.rsi_workflows.agent_runtimes.tool_mcp import AgentTool, ToolMcpHost
from fore_rsi.utils.paths import write_private_text
from fore_rsi.utils.terminal import PaneLocation


class CodexAgentRuntime(AgentRuntime):
    """Open Codex in a workflow pane and retain each member's thread separately."""

    harness_name = "codex"

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
        """Create a Codex runtime with serialized message delivery."""
        super().__init__(
            agent_config,
            workflow_directory,
            workgroup_name=workgroup_name,
            agent_name=agent_name,
            tool_mcp_host=tool_mcp_host,
            tools=tools,
        )
        self.app_server: CodexAppServer | None = None

    async def start(
        self, workspace_id: str, *, is_entry: bool = False,
        system_prompt: str | None = None, fork_source: Self | None = None,
    ) -> None:
        """Start the member-local app-server before opening its native TUI."""
        if self.app_server is not None:
            raise RuntimeError("This runtime already owns a Codex app-server.")
        profile = self.profile_directory()
        prepare_codex_profile(profile, self.harness_directory)
        server = CodexAppServer(profile)
        server.thread_id = self.codex_thread()
        self.app_server = server
        settings = ["-c", f"sqlite_home={json.dumps(str(profile))}"]
        if system_prompt is not None:
            settings.extend(["-c", f"developer_instructions={json.dumps(system_prompt)}"])
        if self.tool_mcp is not None:
            settings.extend(self.tool_mcp_args())
        try:
            await server.start(await self.ensure_installed(), settings)
            await super().start(
                workspace_id, is_entry=is_entry,
                system_prompt=system_prompt, fork_source=fork_source,
            )
        except BaseException:
            await server.close()
            self.app_server = None
            raise

    async def fork_from(self, seed: Self) -> None:
        """Fork the seed's saved thread on the child's app-server without taking over the seed's terminal."""
        if self.harness_directory.resolve() != seed.harness_directory.resolve():
            raise ValueError("Codex fork requires a seed in the same workflow rollout store.")
        if seed.app_server is not None and (not seed.retained_for_fork or seed.app_server.pending_inputs):
            raise RuntimeError("Finish the Codex seed's pending turns before forking its thread.")
        server = self.app_server
        assert server is not None  # start() opens the child's server before preparing its branch.
        if server.thread_id is not None or self.get_agent_file_path(".id").exists():
            raise FileExistsError(f"Codex member {self.workgroup_name}/{self.agent_name} already has a thread.")
        seed_thread_id = seed.codex_thread()
        if seed_thread_id is None:
            raise RuntimeError(f"Codex seed {seed.workgroup_name}/{seed.agent_name} has no saved conversation.")
        server.thread_id = await server.fork_member(
            seed_thread_id, model=self.agent_config.model, effort=self.agent_config.effort,
        )

    async def wait_for_agent_ready(self, pane: PaneLocation, agent: dict[str, object]) -> dict[str, object]:
        """Bind this pane's native UUID while the app-server knows which thread is visible."""
        agent = await super().wait_for_agent_ready(pane, agent)
        assert self.app_server is not None
        thread_id = await self.app_server.attach_member(self.session_display_name)
        write_private_text(self.get_agent_file_path(".id"), thread_id + "\n")
        return agent

    async def send_message(
        self,
        message: str,
        mode: MessageDeliveryMode = "queue",
    ) -> None:
        """Submit a Codex queue or steer message through the app-server control channel."""
        if mode not in {"queue", "steer"}:
            raise ValueError(f"Unsupported Codex message delivery mode: {mode!r}")
        server = self.app_server
        if server is None:
            raise RuntimeError("Start the Codex member before sending a message.")
        # An older turn can finish while this input waits for the lock or the pane check.
        async with server.register_input() as client_id, self.message_lock:
            if await self.get_agent() is None:
                raise RuntimeError("The Codex member is no longer running.")
            await server.submit_message(client_id, message, mode)

    async def wait_for_settle(self) -> None:
        """Wait for app-server to report completion of the member's submitted inputs."""
        if self.app_server is None:
            raise RuntimeError("Submit a Codex message before waiting for settle.")
        await self.app_server.wait_for_settle()

    async def close(self) -> None:
        """Stop Codex, release the pane, and retain the Codex thread UUID."""
        try:
            await super().close()
        finally:
            if self.app_server is not None:
                await self.app_server.close()
                self.app_server = None

    @classmethod
    async def ensure_installed(cls) -> Path:
        """Return Codex's launcher for startup callers, installing it when missing."""
        if "CODEX_INSTALL_DIR" in os.environ:
            bin_directory = Path(os.environ["CODEX_INSTALL_DIR"])
        elif os.name == "nt":
            bin_directory = (
                Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
                / "Programs"
                / "OpenAI"
                / "Codex"
                / "bin"
            )
        else:
            bin_directory = Path.home() / ".local" / "bin"
        return await get_or_install_cli(
            cls.harness_name,
            bin_directory / ("codex.exe" if os.name == "nt" else "codex"),
            (
                "https://chatgpt.com/codex/install.ps1"
                if os.name == "nt"
                else "https://chatgpt.com/codex/install.sh"
            ),
            environment={"CODEX_NON_INTERACTIVE": "1"},
        )

    def build_launch_command(
        self,
        executable: Path,
        arguments: Sequence[str] = (),
        *,
        system_prompt: str | None = None,
    ) -> list[str]:
        """Prepare Codex's profile, prompt, tools, and pinned resume command."""
        if self.app_server is None or self.app_server.url is None:
            raise RuntimeError("Start the Codex app-server before attaching the TUI.")
        thread = self.app_server.thread_id

        options: list[str] = []
        if self.agent_config.model is not None:
            options.extend(["--model", self.agent_config.model])
        if self.agent_config.effort is not None:
            options.extend(self.effort_args(self.agent_config.effort))
        command = [
            str(executable), "--remote", self.app_server.url,
            "--remote-auth-token-env", CodexAppServer.TOKEN_ENV,
        ]
        if thread is not None:
            # Remote resume retains the conversation's permissions; Codex rejects overrides.
            return [*command, "resume", thread, *arguments]
        return [
            *command, "--dangerously-bypass-approvals-and-sandbox", "--dangerously-bypass-hook-trust",
            *options, *arguments,
        ]

    def launch_environment(self) -> dict[str, str]:
        """Keep Codex's profile selection with the pane so restore uses the same state."""
        if self.app_server is None:
            raise RuntimeError("Start the Codex app-server before attaching the TUI.")
        return {"CODEX_HOME": str(self.profile_directory()), CodexAppServer.TOKEN_ENV: self.app_server.token}

    def profile_directory(self) -> Path:
        """Give this member a Codex home separate from other members and the user."""
        return self.harness_directory / "profiles" / self.get_agent_file_path("").name

    def effort_args(self, effort: ReasoningEffort) -> list[str]:
        """Override this invocation's reasoning effort without editing the profile."""
        return ["-c", f"model_reasoning_effort={json.dumps(effort)}"]

    def tool_mcp_args(self) -> list[str]:
        """Configure this member's stdio MCP client without editing the profile."""
        options: list[str] = []
        for key, value in self.tool_stdio_server().items():
            options.extend([
                "-c",
                f"mcp_servers.fore_rsi.{key}={json.dumps(value, ensure_ascii=False)}",
            ])
        return options

    def conversation_files(self) -> tuple[Path, ...]:
        """Return rollout files for this member's pinned thread, not other members in the shared store."""
        record = self.get_agent_file_path(".id")
        if not record.is_file():
            return ()
        return thread_record_files(record.read_text(encoding="utf-8").strip(), self.harness_directory)

    def codex_thread(self) -> str | None:
        """Return the member's saved native thread, if Codex materialized its rollout."""
        return get_codex_thread(self.get_agent_file_path(".id"), self.harness_directory)
