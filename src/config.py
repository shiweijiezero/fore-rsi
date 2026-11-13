# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Each configuration owns its parameters and handling logic."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class TaskConfig:
    path: Path

    def handle(self) -> None:
        """TODO: implement task input handling here."""
        raise NotImplementedError("Task handling is not implemented yet.")


@dataclass
class WorkflowConfig:
    name: str

    def handle(self) -> None:
        """TODO: implement workflow selection here."""
        raise NotImplementedError("Workflow selection is not implemented yet.")


@dataclass
class HarnessConfig:
    name: str

    def handle(self) -> None:
        """TODO: implement harness selection here."""
        raise NotImplementedError("Harness selection is not implemented yet.")


@dataclass
class SessionConfig:
    session_id: str

    def handle(self) -> None:
        """TODO: implement session handling here."""
        raise NotImplementedError("Session handling is not implemented yet.")


@dataclass
class DetachConfig:
    enabled: bool = True

    def handle(self) -> None:
        """TODO: implement detached operation here."""
        raise NotImplementedError("Detached operation is not implemented yet.")


Config = TaskConfig | WorkflowConfig | HarnessConfig | SessionConfig | DetachConfig
