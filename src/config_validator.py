# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Validate command parameters independently of the CLI."""

from pathlib import Path

from config import Config, DetachConfig, HarnessConfig, SessionConfig, TaskConfig, WorkflowConfig


def validate_config(config: Config) -> None:
    """Check field types, including configurations constructed from Python."""
    if isinstance(config, TaskConfig):
        if not isinstance(config.path, Path):
            raise TypeError("TaskConfig.path must be a pathlib.Path.")
    elif isinstance(config, (WorkflowConfig, HarnessConfig)):
        if not isinstance(config.name, str):
            raise TypeError(f"{type(config).__name__}.name must be a string.")
    elif isinstance(config, SessionConfig):
        if not isinstance(config.session_id, str):
            raise TypeError("SessionConfig.session_id must be a string.")
    elif isinstance(config, DetachConfig):
        if not isinstance(config.enabled, bool):
            raise TypeError("DetachConfig.enabled must be a bool.")
    else:
        raise TypeError("Unsupported configuration type.")
