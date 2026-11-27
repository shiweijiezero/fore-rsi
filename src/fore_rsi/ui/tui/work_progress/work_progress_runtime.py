# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Prepare the session-local Python entry point for a detached macOS progress pane."""

import json
import sys
from importlib.metadata import distribution
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

import fore_rsi
from fore_rsi.utils.terminal import run_terminal


async def prepare_progress_runtime(session_name: str) -> None:
    """Publish the viewer's bootstrap before the terminal can restore a saved progress pane."""
    if sys.platform != "darwin":
        return
    result = await run_terminal(["session", "info", "--json"], session_name, capture_output=True)
    session = json.loads(result.stdout)
    target = Path(session["session_dir"]) / "work-progress.pyz"
    if session["running"] and target.is_file():
        # Keep the archive of an already-running viewer intact until the next cold start.
        return

    origin = distribution("fore-rsi").read_text("direct_url.json")
    editable = origin and json.loads(origin).get("dir_info", {}).get("editable")
    bootstrap = "import sys\n"
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with NamedTemporaryFile(dir=target.parent, delete_on_close=False) as staged:
        with ZipFile(staged, "w") as archive:
            if editable:
                package = Path(fore_rsi.__file__).resolve().parent
                # A missing optional module also makes Python scan editable .pth entries.
                # Use this copy for application imports and keep the installed dependencies.
                roots = tuple(p for p in sys.path if p and Path(p).resolve() == package.parent)
                bootstrap += f"sys.path[:] = [p for p in sys.path if p not in {roots!r}]\n"
                for source in package.rglob("*.py"):
                    archive.write(source, source.relative_to(package.parent))
            archive.writestr("__main__.py", bootstrap + "from fore_rsi.__main__ import cli\nraise SystemExit(cli())\n")
        staged.close()
        Path(staged.name).replace(target)
