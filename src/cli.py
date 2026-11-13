# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""ForeRSI command-line entry point."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from importlib.metadata import version
from typing import Annotated

import tyro

from config import Config


@dataclass
class _CommandLine:
    # Show the installed ForeRSI version and exit.
    version: Annotated[bool, tyro.conf.arg(help_behavior_hint="")] = False
    options: Annotated[Config, tyro.conf.arg(name="")] = field(default_factory=Config)


def parse_args(args: Sequence[str] | None = None) -> Config:
    """Build a run configuration from command-line arguments."""
    command = tyro.cli(
        _CommandLine,
        prog="fore-rsi",
        description="Run agent teams with feedback-driven workflows.",
        args=args,
        config=(tyro.conf.DisallowNone, tyro.conf.FlagCreatePairsOff),
    )
    if command.version:
        print(f"fore-rsi {version('fore-rsi')}")
        raise SystemExit(0)
    return command.options


def main(args: Sequence[str] | None = None) -> None:
    parse_args(args)
    raise SystemExit("Workflow execution is not implemented.")


if __name__ == "__main__":
    main()
