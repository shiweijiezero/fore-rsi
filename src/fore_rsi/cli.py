# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Parse ForeRSI options and hand the terminal over to Pi."""

import argparse
import os
import sys


def main() -> None:
    """Forward prompts, task files and native Pi options without changing the cwd."""
    parser = argparse.ArgumentParser(
        prog="fore-rsi",
        description="Open Pi with a prompt or a Markdown task file.",
        allow_abbrev=False,
        epilog="Other arguments go to Pi. Use 'fore-rsi -- --help' for Pi help.",
    )
    parser.add_argument("--task", metavar="FILE", help="Submit a Markdown task file to Pi")
    parser.add_argument("--version", action="version", version="%(prog)s 0.0.1")

    # Everything after -- belongs to Pi, even --help or a literal --task.
    arguments = sys.argv[1:]
    separator = arguments.index("--") if "--" in arguments else len(arguments)
    options, pi_args = parser.parse_known_args(arguments[:separator])
    for argument in pi_args:
        if argument.split("=", 1)[0] in {"--workflow", "--harness"}:
            parser.error("Workflow and harness selection were removed from this minimal entry point.")
    pi_args.extend(arguments[separator + 1 :])
    if options.task is not None:
        pi_args.insert(0, f"@{options.task}")

    # Replacing this process lets Pi own the terminal, signals and exit status.
    try:
        os.execvp("pi", ["pi", *pi_args])
    except FileNotFoundError:
        parser.exit(127, "Pi was not found on PATH. Install it with:\n"
                    "  npm install -g @earendil-works/pi-coding-agent@1.5.2\n")
    except OSError as error:
        parser.exit(126, f"Could not start Pi: {error}\n")


if __name__ == "__main__":
    main()
