# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Launch a Pi branch or reopen it when the terminal replays the same member command."""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path


def session_arguments(binding_file: Path) -> list[str]:
    """Select the first native fork or the child's existing session from its private directory."""
    binding = json.loads(binding_file.read_bytes())
    directory = binding_file.parent
    if "record_file" in binding:
        record = (directory / binding["record_file"]).resolve(strict=True)
        selection = ["--session", str(record)]
    elif any(directory.glob("*.jsonl")):
        # Pi wrote the fork, but the previous launcher stopped before reporting its path.
        selection = ["--session", binding["id"]]
    else:
        selection = ["--fork", binding["seed"], "--session-id", binding["id"]]
    return ["--session-dir", str(directory), *selection]


if __name__ == "__main__":
    binding, executable, *options = sys.argv[1:]
    argv = [executable, *session_arguments(Path(binding)), *options]
    if os.name == "nt":
        # Windows' npm launcher can be a .cmd file. Let Pi handle Ctrl+C in the shared console.
        signal.signal(signal.SIGINT, lambda *_: None)
        sys.exit(subprocess.call(argv))
    os.execv(executable, argv)
