# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Workflow runner lifecycle: startup, execution, cancellation, and cleanup."""

import asyncio
import json
import math
import os
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

import psutil

from fore_rsi.config import AgentConfig, Config, WorkflowConfig
from fore_rsi.rsi_workflows.workflow_runtimes.run_state import WorkflowState

if TYPE_CHECKING:
    from fore_rsi.rsi_workflows.base_workflow import BaseWorkflow


class WorkflowRunner:
    """Manage the execution lifecycle of one workflow."""

    def __init__(
        self,
        workflow_class: type["BaseWorkflow"],
        workflow_config: WorkflowConfig,
        session_name: str | None,
        cache_dir: Path,
    ) -> None:
        """Resolve session storage and construct the selected workflow without starting execution."""
        self.session_name = session_name if session_name is not None else Config.DEFAULT_SESSION_NAME
        self._record_path = self._session_record_path(
            cache_dir / WorkflowConfig.SESSIONS_DIR_NAME, self.session_name
        )
        if self._record_path.exists():
            raise ValueError(
                f"Session {self.session_name!r} already exists. "
                "Workflow resume is not supported yet; choose a new session name."
            )
        self.harness = workflow_config.harness_or_default
        self.workflow = workflow_class(
            replace(workflow_config, harness=self.harness), session_directory=self._record_path.parent
        )

    async def run(self, workspace_id: str) -> None:
        """Run in the prepared workspace and record the outcome after workflow cleanup."""
        # Keep one process identity across all state updates for this invocation.
        process = psutil.Process()
        self._write_session_record(WorkflowState.RUNNING, process)
        try:
            await self.workflow.run(workspace_id)
        except asyncio.CancelledError:
            self._write_session_record(WorkflowState.STOPPED, process)
            raise
        except BaseException:
            self._write_session_record(WorkflowState.FAILED, process)
            raise
        else:
            self._write_session_record(WorkflowState.COMPLETED, process)

    @staticmethod
    def list_workflow_sessions(cache_dir: Path) -> list[dict[str, str]]:
        """Return workflow identities and observed states, without modifying their saved records."""
        try:
            session_dirs = sorted((cache_dir / WorkflowConfig.SESSIONS_DIR_NAME).iterdir())
        except FileNotFoundError:
            return []

        sessions = []
        for session_dir in session_dirs:
            if not session_dir.is_dir():
                continue
            try:
                content = (session_dir / WorkflowConfig.SESSION_RECORD_NAME).read_text(encoding="utf-8")
            except FileNotFoundError:
                continue
            record = json.loads(content)
            session = {
                "session_name": record["session_name"],
                "workflow_name": record["workflow_name"],
            }
            if "state" in record:
                session["state"] = WorkflowRunner._observe_workflow_state(
                    WorkflowState(record["state"]),
                    record.get("pid"),
                    record.get("process_created_at"),
                ).value
            sessions.append(session)
        return sessions

    @staticmethod
    async def stop_workflow_session(session_name: str, cache_dir: Path) -> WorkflowState | None:
        """Request a recorded workflow host's shutdown and return its final observed state.

        Session-management callers retain the record and all workflow data. A
        missing record returns None; finished runs are left alone. Active hosts
        use POSIX termination signals, and cancellation stops only the wait.
        A failed or interrupted shutdown raises an error and retains its record.
        """
        record_path = WorkflowRunner._session_record_path(
            cache_dir / WorkflowConfig.SESSIONS_DIR_NAME, session_name
        )
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        if record["session_name"] != session_name:
            raise ValueError(f"Workflow record does not belong to session {session_name!r}.")

        state = WorkflowState(record.get("state", WorkflowState.UNKNOWN))
        if state == WorkflowState.UNKNOWN:
            raise ValueError(f"Workflow session {session_name!r} has no known execution state.")
        if state != WorkflowState.RUNNING:
            return state
        pid = record.get("pid")
        created_at = record.get("process_created_at")
        if (
            type(pid) is not int
            or pid <= 0
            or type(created_at) not in (int, float)
            or not math.isfinite(created_at)
        ):
            raise ValueError(f"Workflow session {session_name!r} has no valid host identity.")

        process = WorkflowRunner._matching_workflow_process(pid, created_at)
        if process is not None:
            if pid == os.getpid():
                raise RuntimeError("Cancel the local runner task instead of stopping its own host.")
            if os.name == "nt":
                raise NotImplementedError("Graceful workflow-host shutdown requires POSIX signals.")
            try:
                process.terminate()
            except psutil.NoSuchProcess:
                pass
            # Keep waiting cancellable without leaving a blocking process waiter
            # behind. A zombie or reused PID no longer represents the running host.
            while WorkflowRunner._matching_workflow_process(pid, created_at) is not None:
                await asyncio.sleep(WorkflowConfig.STOP_POLL_INTERVAL_SECONDS)

        final_record = json.loads(record_path.read_text(encoding="utf-8"))
        if (
            final_record["session_name"] != session_name
            or final_record.get("pid") != pid
            or final_record.get("process_created_at") != created_at
        ):
            raise RuntimeError(f"Workflow session {session_name!r} changed while stopping.")
        final_state = WorkflowRunner._observe_workflow_state(
            WorkflowState(final_record["state"]), pid, created_at
        )
        if process is not None and final_state not in (WorkflowState.STOPPED, WorkflowState.COMPLETED):
            raise RuntimeError(
                f"Workflow session {session_name!r} ended as {final_state.value!r} during shutdown."
            )
        return final_state

    @staticmethod
    async def delete_workflow_session(session_name: str, cache_dir: Path) -> None:
        """Stop a registered workflow and remove only its session directory; missing records are unchanged."""
        if await WorkflowRunner.stop_workflow_session(session_name, cache_dir) is None:
            return
        record_path = WorkflowRunner._session_record_path(
            cache_dir / WorkflowConfig.SESSIONS_DIR_NAME, session_name
        )
        record = json.loads(record_path.read_text(encoding="utf-8"))
        harness = record.get("harness", AgentConfig.harness)
        if not isinstance(harness, str):
            raise TypeError(f"Workflow session {session_name!r} has an invalid harness.")
        from fore_rsi.rsi_workflows.agent_runtimes import get_agent_runtime_class

        get_agent_runtime_class(harness).remove_workflow_storage(record_path.parent)
        try:
            shutil.rmtree(record_path.parent)
        except FileNotFoundError:
            pass

    @staticmethod
    def _observe_workflow_state(
        state: WorkflowState, pid: int | None, process_created_at: float | None
    ) -> WorkflowState:
        """Check a recorded running state's local host while preserving final outcomes."""
        if state != WorkflowState.RUNNING:
            return state
        if pid is None or process_created_at is None:
            return WorkflowState.UNKNOWN
        try:
            process = WorkflowRunner._matching_workflow_process(pid, process_created_at)
        except psutil.AccessDenied:
            return WorkflowState.UNKNOWN
        return WorkflowState.RUNNING if process is not None else WorkflowState.INTERRUPTED

    @staticmethod
    def _matching_workflow_process(pid: int, process_created_at: float) -> psutil.Process | None:
        """Resolve a live recorded host for observation or shutdown; access errors propagate."""
        try:
            process = psutil.Process(pid)
            if (
                process.create_time() == process_created_at
                and process.is_running()
                and process.status() not in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD)
            ):
                return process
        except psutil.NoSuchProcess:
            pass
        return None

    @staticmethod
    def _session_record_path(sessions_dir: Path, session_name: str) -> Path:
        """Locate a workflow record without allowing a session name to leave its directory."""
        if session_name in {"", ".", ".."} or Path(session_name).name != session_name:
            raise ValueError("Workflow session name must be a single directory name.")
        return sessions_dir / session_name / WorkflowConfig.SESSION_RECORD_NAME

    def _write_session_record(self, state: WorkflowState, process: psutil.Process) -> None:
        """Publish the workflow identity, host process, and state as one complete session record."""
        record_path = self._record_path
        session_dir = record_path.parent
        session_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "session_name": self.session_name,
            "workflow_name": self.workflow.workflow_name,
            "harness": self.harness,
            "state": state,
            "pid": process.pid,
            "process_created_at": process.create_time(),
        }
        # Publish only after the temporary file is closed, so readers see a
        # complete snapshot and Windows can replace the destination.
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=session_dir, delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                json.dump(record, temporary, indent=2)
                temporary.write("\n")
            temporary_path.replace(record_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
