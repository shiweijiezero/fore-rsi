# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Parse ForeRSI options. Workflow execution is not connected yet.

Examples:

    fore-rsi --task task.md --workflow workflow_name --harness harness_name

    fore-rsi --session session_name --detach
"""

from pathlib import Path
from typing import Annotated

import typer

from config import Config, DetachConfig, HarnessConfig, SessionConfig, TaskConfig, WorkflowConfig
from config_validator import validate_config

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


def parse_args(
    task: Path | None = None,
    workflow: str | None = None,
    harness: str | None = None,
    session: str | None = None,
    detach: bool = False,
) -> list[Config]:
    """Convert supplied options into their corresponding configurations."""
    configs: list[Config] = []
    if task is not None:
        configs.append(TaskConfig(path=task))
    if workflow is not None:
        configs.append(WorkflowConfig(name=workflow))
    if harness is not None:
        configs.append(HarnessConfig(name=harness))
    if session is not None:
        configs.append(SessionConfig(session_id=session))
    if detach is not False:
        configs.append(DetachConfig(enabled=detach))
    for config in configs:
        validate_config(config)
    return configs


@app.command(help=__doc__)
def cli(
    task: Annotated[Path | None, typer.Option("--task", help="Markdown task file")] = None,
    workflow: Annotated[str | None, typer.Option("--workflow", help="Workflow selection")] = None,
    harness: Annotated[str | None, typer.Option("--harness", help="Harness selection")] = None,
    session: Annotated[str | None, typer.Option("--session", help="Session identifier")] = None,
    detach: Annotated[bool, typer.Option("--detach", help="Request detached operation")] = False,
    version: Annotated[bool, typer.Option("--version", help="Show version and exit")] = False,
) -> None:
    """Parse options and dispatch each configuration to its handler."""
    if version:
        typer.echo("fore-rsi 0.0.1")
        raise typer.Exit()
    for config in parse_args(task, workflow, harness, session, detach):
        config.handle()


def main() -> None:
    try:
        app(prog_name="fore-rsi")
    except (NotImplementedError, TypeError, ValueError) as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()
