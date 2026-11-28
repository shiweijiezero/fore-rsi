# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Application settings and command-line configuration for ForeRSI."""

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Annotated, ClassVar, Literal

from platformdirs import user_state_path
from tyro.conf import Positional, arg


type ReasoningEffort = Literal["off", "minimal", "low", "medium", "high", "xhigh", "max"]


@dataclass
class AgentConfig:
    """Execution settings supplied by workflows when constructing an agent runtime."""

    # Select the native execution backend.
    harness: str = "pi"
    # Omitted settings keep the native conversation's choices.
    model: str | None = None
    effort: ReasoningEffort | None = None


@dataclass
class WorkflowConfig:
    """Task and agent execution."""

    GLOBAL_WORKGROUP_NAME: ClassVar[str] = "global"
    SESSIONS_DIR_NAME: ClassVar[str] = "workflows"
    SESSION_RECORD_NAME: ClassVar[str] = "workflow.json"
    # Interval between host-exit checks while stopping a workflow.
    STOP_POLL_INTERVAL_SECONDS: ClassVar[float] = 0.1

    # Select a built-in or project workflow by its declared name.
    workflow_name: Annotated[str, arg(name="workflow", prefix_name=False)] = "default"
    # Markdown task file.
    task: Annotated[Path | None, arg(prefix_name=False)] = None
    # Select the native backend for this new workflow session.
    harness: Annotated[str | None, arg(prefix_name=False, help_behavior_hint="")] = None
    # Select the entry agent's model. Omit to keep the backend's model selection.
    entry_model: Annotated[str | None, arg(name="model", prefix_name=False, help_behavior_hint="")] = None
    # Set reasoning effort for the workflow's entry agent only. Omit to keep the backend's setting.
    entry_effort: Annotated[ReasoningEffort | None, arg(name="effort", prefix_name=False, help_behavior_hint="")] = None

    # Attempt limit for required tool submissions and direction selection. Each group shares this limit across its finish reviews.
    max_attempts: Annotated[int, arg(prefix_name=False)] = 3

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("--max-attempts must be at least 1.")

    @property
    def harness_or_default(self) -> str:
        """Resolve the backend for a new workflow session."""
        return AgentConfig.harness if self.harness is None else self.harness


@dataclass
class LoggingConfig:
    """Python diagnostic logging."""

    # Minimum diagnostic level.
    level: Annotated[
        Literal["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"],
        arg(name="log-level", prefix_name=False),
    ] = "INFO"
    # Append diagnostics to this file as well as stderr.
    file: Annotated[Path | None, arg(name="log-file", prefix_name=False)] = None
    # Diagnostic output format for stderr and the optional file.
    format: Annotated[Literal["text", "json"], arg(name="log-format", prefix_name=False)] = "text"


@dataclass
class Config:
    """User inputs and internal settings for ForeRSI session commands."""

    TERMINAL_EXECUTABLE_NAME: ClassVar[str] = "_terminal.exe" if os.name == "nt" else "_terminal"
    DEFAULT_SESSION_NAME: ClassVar[str] = "default"
    WORK_PROGRESS_PANE_KEY: ClassVar[str] = "fore-rsi.work-progress"
    WORK_PROGRESS_LABEL: ClassVar[str] = "Work progress"
    SESSION_INDEX_PATH: ClassVar[Path] = (
        user_state_path("fore-rsi", appauthor=False) / "sessions.sqlite3"
    )

    # Run a new workflow, list, stop, delete a session, or open its work-progress page.
    session_action: Positional[Literal["run", "list", "stop", "delete", "workprogress"]] = "run"
    # Select the ForeRSI session shared by its workflow and interface.
    session: Annotated[str | None, arg(prefix_name=False)] = None
    # Initial workflow storage, relative to the project Git root or startup directory outside Git.
    # Existing sessions reuse their saved location.
    cache_dir: Annotated[Path, arg(name="cache-dir", prefix_name=False)] = Path("./cache")

    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
