# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Workflow and display configuration for a ForeRSI run."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

from tyro.conf import arg


@dataclass
class WorkflowConfig:
    """Task and agent execution."""

    # Select a workflow.
    name: Annotated[str | None, arg(name="workflow", prefix_name=False)] = None
    # Markdown task file.
    task: Annotated[Path | None, arg(prefix_name=False)] = None
    # Select the workflow's agent execution backend.
    harness: Annotated[str | None, arg(prefix_name=False)] = None


@dataclass
class UIConfig:
    """Herdr display."""

    # Use or create a named Herdr session.
    session: Annotated[str | None, arg(prefix_name=False)] = None


@dataclass
class Config:
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    ui: UIConfig = field(default_factory=UIConfig)
