# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Read the native Pi session settings for a stopped member."""

import json
from pathlib import Path
from typing import TypedDict

from fore_rsi.config import ReasoningEffort


class PiSessionState(TypedDict):
    """Session settings returned by the running Pi extension or its record file."""

    record_file: str
    session_id: str | None
    model: str | None
    effort: ReasoningEffort | None


class PiLiveSessionState(PiSessionState):
    """Live Pi session settings, including the settle sequence."""

    settled_seq: int


def read_record_file_state(path: Path) -> PiSessionState:
    """Read the selected model and effort from a saved Pi record file."""
    state: PiSessionState = {
        "record_file": str(path),
        "session_id": None,
        "model": None,
        "effort": None,
    }
    try:
        stream = path.open("rb")
    except FileNotFoundError:
        return state
    with stream:
        if not (header := stream.readline()):
            return state
        state["session_id"] = json.loads(header)["id"]
        # Pi restores from the last entry's ancestor chain, not the last change anywhere in the file.
        selections: dict[str, tuple[str | None, ReasoningEffort | None]] = {}
        for line in stream:
            if not line.endswith(b"\n"):
                break
            entry = json.loads(line)
            model, effort = selections.get(entry["parentId"], (None, None))
            if entry["type"] == "model_change":
                model = f"{entry['provider']}/{entry['modelId']}"
            elif entry["type"] == "thinking_level_change":
                effort = entry["thinkingLevel"]
            selections[entry["id"]] = model, effort
            state["model"], state["effort"] = model, effort
    return state
