# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Control the Codex app-server shared by one member's TUI and workflow."""

import asyncio
import json
import os
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager, suppress
from hashlib import sha256
from pathlib import Path
from secrets import token_urlsafe
from typing import Any, Literal
from uuid import uuid4

from loguru import logger
from websockets.asyncio.client import ClientConnection, connect


class CodexAppServerError(RuntimeError):
    """Report an app-server transport or protocol failure."""


class CodexAppServer:
    """Own one authenticated loopback server and subscribe to its visible member thread."""

    TOKEN_ENV = "FORE_RSI_CODEX_REMOTE_TOKEN"

    def __init__(self, profile: Path) -> None:
        self.profile = profile
        self.token = token_urlsafe(32)
        self.url: str | None = None
        self.process: asyncio.subprocess.Process | None = None
        self.connection: ClientConnection | None = None
        self.reader: asyncio.Task[None] | None = None
        self.diagnostics: asyncio.Task[None] | None = None
        self.requests: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self.request_number = 0
        self.thread_id: str | None = None
        self.pending_inputs: dict[str, str | None] = {}  # Client message ID → consuming turn ID.
        self.settled = asyncio.Condition()
        self.turn_failure: CodexAppServerError | None = None

    async def start(self, executable: Path, settings: Sequence[str]) -> None:
        """Start the member's foreground app-server and establish its control connection."""
        self.process = await asyncio.create_subprocess_exec(
            str(executable), "app-server", *settings, "--listen", "ws://127.0.0.1:0",
            "--ws-auth", "capability-token", "--ws-token-sha256", sha256(self.token.encode()).hexdigest(),
            env={**os.environ, "CODEX_HOME": str(self.profile)},
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
        )
        # Port zero lets the kernel bind a free port atomically. Only the startup
        # address is read here; message acceptance and completion are protocol events.
        stderr = self.process.stderr
        assert stderr is not None
        try:
            await stderr.readuntil(b"  listening on: ws://127.0.0.1:")
        except asyncio.IncompleteReadError as error:
            detail = error.partial.decode(errors="replace").strip()
            raise CodexAppServerError(f"Codex app-server exited before binding: {detail}") from error
        port = int(await stderr.readline())
        self.url = f"ws://127.0.0.1:{port}"
        self.diagnostics = asyncio.create_task(self.read_diagnostics(stderr))
        self.connection = await connect(
            self.url, additional_headers={"Authorization": f"Bearer {self.token}"}, proxy=None, max_size=None,
        )
        self.reader = asyncio.create_task(self.read_messages(self.connection))
        await self.request("initialize", {
            "clientInfo": {"name": "fore-rsi", "title": "ForeRSI", "version": "0.0.1"},
            "capabilities": {"experimentalApi": True},
        })
        await self.connection.send(json.dumps({"method": "initialized", "params": {}}))

    async def fork_member(
        self, seed_thread_id: str, *, model: str | None, effort: str | None,
    ) -> str:
        """Materialize the child thread in the shared rollout store without starting a turn."""
        seed = (await self.request("thread/read", {"threadId": seed_thread_id}))["thread"]
        if seed.get("historyMode") == "paginated" and seed["path"] is not None:
            # Codex materializes a compressed source in place when creating a paginated
            # history reference. Do not let a fork rewrite the seed's rollout storage.
            plain = Path(seed["path"].removesuffix(".zst"))
            if not plain.is_file() and plain.with_suffix(".jsonl.zst").is_file():
                raise CodexAppServerError(f"Cannot fork compressed Codex seed {seed_thread_id} without modifying it.")
        result = await self.request("thread/fork", {
            "threadId": seed_thread_id,
            "cwd": str(Path.cwd()),
            "model": model,
            "config": {"model_reasoning_effort": effort} if effort is not None else None,
            "excludeTurns": True,
        })
        return result["thread"]["id"]

    async def attach_member(self, member_name: str) -> str:
        """Subscribe to the selected thread, or bind the only fresh thread on this member's server."""
        thread_id = self.thread_id
        if thread_id is None:
            # The shared rollout store contains other members, but the fresh server
            # has exactly one loaded thread: the TUI's new root.
            loaded = await self.request("thread/loaded/list", {})
            if len(loaded["data"]) != 1:
                raise CodexAppServerError(f"Expected one new Codex thread for {member_name}.")
            thread_id = loaded["data"][0]
        await self.request("thread/resume", {"threadId": thread_id, "excludeTurns": True})
        await self.request("thread/name/set", {"threadId": thread_id, "name": member_name})
        self.thread_id = thread_id
        return thread_id

    @asynccontextmanager
    async def register_input(self) -> AsyncIterator[str]:
        """Count a dispatch before the runtime waits its turn; release rejected inputs immediately."""
        client_id = str(uuid4())
        self.pending_inputs[client_id] = None
        try:
            yield client_id
        except BaseException:
            async with self.settled:
                self.pending_inputs.pop(client_id, None)
                self.settled.notify_all()
            raise

    async def submit_message(self, client_id: str, message: str, mode: Literal["queue", "steer"]) -> None:
        """Submit a registered input once: turn/start steers the active turn or starts one when idle."""
        params = {
            "threadId": self.thread_id,
            "clientUserMessageId": client_id,
            "input": [{"type": "text", "text": message}],
        }
        if mode == "queue":
            await self.request("thread/queue/add", params)
        else:
            response = await self.request("turn/start", params)
            # The reader may have consumed item/started and turn/completed before this reply.
            if client_id in self.pending_inputs:
                self.pending_inputs[client_id] = response["turn"]["id"]

    async def wait_for_settle(self) -> None:
        """Wait for native completion of the turns that consumed this member's inputs."""
        async with self.settled:
            await self.settled.wait_for(lambda: not self.pending_inputs or self.turn_failure is not None)
            if self.turn_failure is not None:
                failure, self.turn_failure = self.turn_failure, None
                raise failure

    async def record_event(self, method: str, params: dict[str, Any]) -> None:
        """Bind our inputs to their actual turns and release all inputs sharing one completed turn."""
        if params.get("threadId") != self.thread_id:
            return
        if method == "item/started":
            item = params["item"]
            client_id = item.get("clientId")
            if item["type"] == "userMessage" and client_id in self.pending_inputs:
                self.pending_inputs[client_id] = params["turnId"]
            return
        if method == "turn/completed":
            turn = params["turn"]
            turn_id = turn["id"]
            error = None if turn["status"] == "completed" else f"{turn['status']}: {turn.get('error')}"
        elif method == "error" and not params["willRetry"]:
            turn_id = params["turnId"]
            error = params["error"]["message"]
        else:
            return
        completed = [client for client, target in self.pending_inputs.items() if target == turn_id]
        if completed:
            async with self.settled:
                for client in completed:
                    del self.pending_inputs[client]
                if error is not None:
                    self.turn_failure = CodexAppServerError(f"Codex turn {turn_id}: {error}")
                self.settled.notify_all()

    async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send one JSON-RPC request; only its matching response completes it."""
        if self.connection is None:
            raise CodexAppServerError("Codex app-server is not connected.")
        self.request_number += 1
        request_id = self.request_number
        response: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self.requests[request_id] = response
        try:
            await self.connection.send(json.dumps({"id": request_id, "method": method, "params": params}))
            return await response
        finally:
            self.requests.pop(request_id, None)

    async def read_messages(self, connection: ClientConnection) -> None:
        """Dispatch RPC responses and turn notifications until the native connection closes."""
        failure = CodexAppServerError("Codex app-server disconnected.")
        try:
            async for raw in connection:
                message = json.loads(raw)
                if "method" in message:
                    if "id" not in message:
                        await self.record_event(message["method"], message.get("params", {}))
                    else:
                        await connection.send(json.dumps({
                            "id": message["id"], "error": {"code": -32601, "message": f"Unsupported: {message['method']}"},
                        }))
                elif "id" in message:
                    response = self.requests.pop(message["id"], None)
                    if response is not None and not response.done():
                        if "error" in message:
                            response.set_exception(CodexAppServerError(message["error"]["message"]))
                        else:
                            response.set_result(message["result"])
        except Exception as error:
            failure = CodexAppServerError(str(error))
        finally:
            self.connection = None
            for response in self.requests.values():
                if not response.done():
                    response.set_exception(failure)
            self.requests.clear()
            async with self.settled:
                if self.pending_inputs:
                    self.pending_inputs.clear()
                    self.turn_failure = failure
                self.settled.notify_all()

    @staticmethod
    async def read_diagnostics(stream: asyncio.StreamReader) -> None:
        """Drain native diagnostics without mixing them into the JSON-RPC channel."""
        async for line in stream:
            logger.debug("Codex app-server: {}", line.decode(errors="replace").rstrip())

    async def close(self) -> None:
        """Close the workflow connection and stop only the server started for this member."""
        if self.connection is not None:
            await self.connection.close()
        if self.reader is not None:
            await self.reader
        if self.process is not None:
            if self.process.returncode is None:
                with suppress(ProcessLookupError):
                    self.process.terminate()
            await self.process.wait()
        if self.diagnostics is not None:
            await self.diagnostics
