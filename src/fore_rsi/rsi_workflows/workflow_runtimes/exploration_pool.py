# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Persist and query explorations for one default workflow session."""

from collections.abc import Mapping
from pathlib import Path
from typing import Literal
from urllib.parse import quote, unquote

from pydantic import BaseModel, ConfigDict, Field

from fore_rsi.rsi_workflows.types import RequiredText
from fore_rsi.utils.paths import write_private_text


ExplorationItemStatus = Literal[
    "pending_confirmation",
    "exploring",
    "ready_for_experiment",
    "retired",
    "mature"
]


class ExplorationItem(BaseModel):
    """One exploration tied to a task revision, its notes, and an optional code space."""

    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)
    exploration_id: RequiredText | None = Field(
        default=None,
        description="Assigned by the exploration pool on registration, starting at '0'.",
    )
    task_revision_number: int = Field(
        ge=1,
        description="The TaskRevision under which this exploration was registered.",
    )
    parent_exploration_ids: list[RequiredText] = Field(
        default_factory=list, description="Parent exploration IDs, including IDs absent from this pool."
    )
    name: RequiredText
    description: RequiredText = Field(
        description="The problem, proposed approach, and expected benefit.",
    )
    status: ExplorationItemStatus = "pending_confirmation"
    record_path: Literal["record.md"] = "record.md"
    code_workspace_path: RequiredText | None = Field(
        default=None,
        description="Assigned code space, or None before a workspace is allocated.",
    )
    experiment_commands: list[RequiredText] = Field(
        default_factory=list, description="Commands for the Experimenter, in execution order."
    )
    experiment_result: RequiredText | None = Field(
        default=None, description="The Experimenter's report for this command sequence."
    )


class ExplorationPool:
    """Read exploration records from disk so they survive pool and workflow recreation."""

    def __init__(self, workspace: Path) -> None:
        """Locate the exploration records in the agents' workspace."""
        self.directory = workspace / "explorations"

    def add(self, exploration: ExplorationItem) -> str:
        """Save an exploration and return the ID also assigned to the caller's item."""
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if exploration.exploration_id is None:
            numbers = (int(p.name) for p in self.directory.iterdir() if p.is_dir() and p.name.isdecimal())
            exploration.exploration_id = str(max(numbers, default=-1) + 1)

        name = quote(exploration.exploration_id, safe="").replace(".", "%2E")
        path = self.directory / name / f"{name}.json"
        path.parent.mkdir()
        (path.parent / exploration.record_path).touch()
        write_private_text(path, exploration.model_dump_json(indent=2) + "\n")
        return exploration.exploration_id

    def update(
        self, exploration_id: str, changes: Mapping[str, object] | None = None, **fields: object
    ) -> ExplorationItem:
        """Apply a field mapping and keyword overrides to the stored item."""
        exploration = self.get(exploration_id)
        if changes or fields:
            exploration = ExplorationItem.model_validate(
                {**exploration.model_dump(), **(changes or {}), **fields, "exploration_id": exploration_id}
            )
            name = quote(exploration_id, safe="").replace(".", "%2E")
            path = self.directory / name / f"{name}.json"
            write_private_text(path, exploration.model_dump_json(indent=2) + "\n")
        return exploration

    def append_record(self, exploration_id: str, record_entry: str) -> None:
        """Append exploration notes without changing the item's fields."""
        exploration = self.get(exploration_id)
        name = quote(exploration_id, safe="").replace(".", "%2E")
        record_path = self.directory / name / exploration.record_path
        with record_path.open("a", encoding="utf-8") as record:
            record.write(record_entry.rstrip("\n") + "\n")

    def get(self, exploration_id: str) -> ExplorationItem:
        name = quote(exploration_id, safe="").replace(".", "%2E")
        content = (self.directory / name / f"{name}.json").read_text(encoding="utf-8")
        return ExplorationItem.model_validate_json(content)

    def list(
        self, task_revision_number: int | None = None
    ) -> list[ExplorationItem]:
        """Read explorations in ID order, optionally filtering by task revision."""
        ids = sorted(
            (unquote(path.stem) for path in self.directory.glob("*/*.json") if path.stem == path.parent.name),
            key=lambda key: (0, int(key)) if key.isdecimal() else (1, key),
        )
        explorations = (self.get(key) for key in ids)
        return [
            exploration for exploration in explorations
            if task_revision_number is None or exploration.task_revision_number == task_revision_number
        ]
