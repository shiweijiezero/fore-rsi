# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Store the exploration graph in SQLite and publish each item's progress beside its working notes."""

import json
import re
import sqlite3
from collections.abc import Generator, Iterator, Mapping
from contextlib import ExitStack, closing, contextmanager
from os.path import samestat
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

from fore_rsi.rsi_workflows.types import RequiredText, SingleLineText
from fore_rsi.utils.paths import write_private_text

EXPLORATION_RECORD_FILENAME = "exploration_record.md"
PROGRESS_FILENAME = "progress.md"

ExplorationItemStatus = Literal[
    "pending_confirmation",
    "approved",
    "rejected",
    "exploring",
    "queued_for_experiment",
    "experimenting",
    "retired",
    "mature",
]


class ExplorationSubmission(BaseModel):
    """The proposed direction, parent references and experiment instructions an Explorer can submit."""

    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)
    name: RequiredText = Field(
        description="A short name identifying the starting point or proposed direction."
    )
    description: RequiredText = Field(
        description="The baseline revision and configuration, or the proposed change and its purpose."
    )
    parent_exploration_ids: list[RequiredText] = Field(
        default_factory=list,
        description="Parent exploration IDs, including IDs absent from this pool.",
    )
    code_workspace_path: RequiredText | None = Field(
        default=None,
        description="Absolute path of the source checkout, if one has been prepared.",
    )
    experiment_commands: list[RequiredText] = Field(
        default_factory=list,
        description="Commands for the Experimenter, in execution order.",
    )


class ExplorationItem(ExplorationSubmission):
    """An exploration with the identity and progress fields maintained by the workflow."""

    exploration_id: RequiredText | None = Field(
        default=None,
        description="Assigned by the exploration pool on registration, starting at '0'.",
    )
    task_revision_number: int | None = Field(
        default=None, ge=1, description="Task revision current at registration."
    )
    exploration_record_path: Literal["exploration_record.md"] = Field(
        default=EXPLORATION_RECORD_FILENAME,
        description="Path within the item's directory to its Markdown plan, design notes, experiments and conclusions.",
    )
    status: ExplorationItemStatus = "pending_confirmation"
    experiment_result: RequiredText | None = Field(
        default=None, description="The Experimenter's report for this command sequence."
    )
    experiment_summary: SingleLineText | None = Field(
        default=None, description="Short outcome label submitted with the experiment report."
    )


def progress_markdown(item: ExplorationItem) -> str:
    """Render the current pool entry for someone opening the item's directory."""
    parents = ", ".join(f"#{parent}" for parent in item.parent_exploration_ids) or "None"
    checkout = f"`{item.code_workspace_path}`" if item.code_workspace_path else "Not assigned"
    summary = f"- Experiment: {item.experiment_summary}\n" if item.experiment_summary else ""
    return (
        f"# Exploration {item.exploration_id}: {item.name}\n\n{item.description}\n\n"
        f"- Status: `{item.status}`\n- Task revision: {item.task_revision_number}\n"
        f"- Parents: {parents}\n- Recorded checkout: {checkout}\n{summary}\n"
        f"[Detailed exploration record]({EXPLORATION_RECORD_FILENAME})\n"
    )


def row_values(item: ExplorationItem) -> dict[str, object]:
    """Bind one validated item to SQL; the two lists retain their order and external parent IDs."""
    return {
        "exploration_id": item.exploration_id,
        "task_revision_number": item.task_revision_number,
        "name": item.name,
        "description": item.description,
        "status": item.status,
        "parent_exploration_ids": json.dumps(
            item.parent_exploration_ids, ensure_ascii=False
        ),
        "code_workspace_path": item.code_workspace_path,
        "experiment_commands": json.dumps(item.experiment_commands, ensure_ascii=False),
        "experiment_result": item.experiment_result,
        "experiment_summary": item.experiment_summary,
    }


def item_from_row(row: sqlite3.Row) -> ExplorationItem:
    """Return the typed exploration consumed by the workflow and progress viewer."""
    fields = dict(row)
    for key in ("parent_exploration_ids", "experiment_commands"):
        fields[key] = json.loads(fields[key])
    return ExplorationItem.model_validate(fields)


def validate_parent_links(
    db: sqlite3.Connection, exploration_id: str, parents: list[str]
) -> None:
    """Reject an edge back to this node; ancestors outside the pool are valid leaves."""
    if not parents:
        return
    cycle = db.execute(
        """WITH RECURSIVE ancestors(id) AS (
               SELECT value FROM json_each(:parents)
               UNION
               SELECT parent.value FROM ancestors
               JOIN explorations AS item ON item.exploration_id = ancestors.id
               CROSS JOIN json_each(item.parent_exploration_ids) AS parent
           )
           SELECT 1 FROM ancestors WHERE id = :id LIMIT 1""",
        {"parents": json.dumps(parents), "id": exploration_id},
    ).fetchone()
    if cycle is not None:
        raise ValueError(f"Exploration {exploration_id!r} cannot be its own ancestor.")


class ExplorationPool:
    """Own structured exploration state and resolve each item's editable Markdown record."""

    def __init__(self, workspace: Path, *, read_only: bool = False) -> None:
        """Prepare a workflow's database, or bind a viewer without creating session data."""
        self.directory = workspace / "exploration_pool"
        self.database_path = self.directory / "exploration_status.sqlite3"
        self.read_only = read_only
        if not read_only:
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            with self.connection() as db, db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("""CREATE TABLE IF NOT EXISTS explorations (
                    exploration_id TEXT PRIMARY KEY NOT NULL,
                    task_revision_number INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL,
                    parent_exploration_ids TEXT NOT NULL,
                    code_workspace_path TEXT,
                    experiment_commands TEXT NOT NULL,
                    experiment_result TEXT,
                    experiment_summary TEXT
                )""")
                columns = {row["name"] for row in db.execute("PRAGMA table_info(explorations)")}
                if "experiment_summary" not in columns:
                    db.execute("ALTER TABLE explorations ADD COLUMN experiment_summary TEXT")
                # Numeric IDs are strings; ordering the significant digits also handles explicit IDs
                # beyond SQLite's integer range. This index keeps allocation from scanning the graph.
                db.execute("""CREATE INDEX IF NOT EXISTS numeric_exploration_ids ON explorations
                    (length(ltrim(exploration_id, '0')), ltrim(exploration_id, '0'))
                    WHERE exploration_id NOT GLOB '*[^0-9]*'""")
                # Restore generated summaries for older pools or an interrupted file/SQL update.
                # A read-only viewer never changes a saved session.
                for row in db.execute("SELECT * FROM explorations"):
                    path = self.item_directory(row["exploration_id"], row["name"]) / PROGRESS_FILENAME
                    text = progress_markdown(item_from_row(row))
                    if not path.exists() or path.read_text(encoding="utf-8") != text:
                        write_private_text(path, text)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Scope a connection to the operation and thread that opened it."""
        mode = "ro" if self.read_only else "rwc"
        uri = f"{self.database_path.resolve().as_uri()}?mode={mode}"
        try:
            connection = sqlite3.connect(uri, uri=True)
        except sqlite3.OperationalError as error:
            if self.read_only and not self.database_path.exists():
                raise FileNotFoundError(self.database_path) from error
            raise
        with closing(connection) as db:
            db.row_factory = sqlite3.Row
            yield db

    @contextmanager
    def write_transaction(self) -> Iterator[tuple[sqlite3.Connection, ExitStack]]:
        """Hold the writer lock and undo record-file changes if the operation or its commit fails."""
        with self.connection() as db, ExitStack() as undo:
            db.execute("BEGIN IMMEDIATE")
            yield db, undo
            db.commit()
            undo.pop_all()

    def add(self, exploration: ExplorationItem, *, task_revision_number: int) -> str:
        """Register one node with its progress summary and working record, then return its stable ID."""
        with self.write_transaction() as (db, undo):
            exploration_id = exploration.exploration_id
            if exploration_id is None:
                last = db.execute("""SELECT exploration_id FROM explorations
                    WHERE exploration_id NOT GLOB '*[^0-9]*'
                    ORDER BY length(ltrim(exploration_id, '0')) DESC, ltrim(exploration_id, '0') DESC
                    LIMIT 1""").fetchone()
                exploration_id = str(int(last[0]) + 1) if last else "0"
            elif db.execute(
                "SELECT 1 FROM explorations WHERE exploration_id = ?", (exploration_id,)
            ).fetchone():
                raise FileExistsError(f"Exploration {exploration_id!r} already exists.")

            validate_parent_links(
                db, exploration_id, exploration.parent_exploration_ids
            )
            item = exploration.model_copy(update={"exploration_id": exploration_id})
            item.task_revision_number = task_revision_number
            db.execute(
                """INSERT INTO explorations
                   (exploration_id, task_revision_number, name, description, status,
                    parent_exploration_ids, code_workspace_path, experiment_commands, experiment_result, experiment_summary)
                   VALUES (:exploration_id, :task_revision_number, :name, :description, :status,
                           :parent_exploration_ids, :code_workspace_path, :experiment_commands, :experiment_result, :experiment_summary)""",
                row_values(item),
            )
            directory = self.item_directory(exploration_id, item.name)
            directory.mkdir(mode=0o700)
            undo.callback(directory.rmdir)
            record = directory / EXPLORATION_RECORD_FILENAME
            record.touch(mode=0o600, exist_ok=False)
            undo.callback(record.unlink)
            progress = directory / PROGRESS_FILENAME
            write_private_text(progress, progress_markdown(item))
            undo.callback(progress.unlink)

        exploration.exploration_id = exploration_id
        exploration.task_revision_number = task_revision_number
        return exploration_id

    def update(
        self,
        exploration_id: str,
        changes: Mapping[str, object] | None = None,
        **fields: object,
    ) -> ExplorationItem:
        """Update one node by ID, moving its record and artifacts if its directory name changes."""
        if not changes and not fields:
            return self.get(exploration_id)
        with self.write_transaction() as (db, undo):
            item = self.fetch_item(db, exploration_id)
            updated = ExplorationItem.model_validate(
                {
                    **item.model_dump(),
                    **(changes or {}),
                    **fields,
                    "exploration_id": exploration_id,
                }
            )
            if updated.parent_exploration_ids != item.parent_exploration_ids:
                validate_parent_links(
                    db, exploration_id, updated.parent_exploration_ids
                )
            db.execute(
                """UPDATE explorations SET name=:name, description=:description, status=:status,
                   task_revision_number=:task_revision_number, parent_exploration_ids=:parent_exploration_ids,
                   code_workspace_path=:code_workspace_path, experiment_commands=:experiment_commands,
                   experiment_result=:experiment_result, experiment_summary=:experiment_summary
                   WHERE exploration_id=:exploration_id""",
                row_values(updated),
            )
            previous = self.item_directory(exploration_id, item.name)
            directory = self.item_directory(exploration_id, updated.name)
            if directory != previous:
                previous.rename(directory)
                undo.callback(directory.rename, previous)
            progress = directory / PROGRESS_FILENAME
            before, after = progress_markdown(item), progress_markdown(updated)
            if before != after:
                write_private_text(progress, after)
                undo.callback(write_private_text, progress, before)
        return updated

    def item_directory(self, exploration_id: str, name: str) -> Path:
        """Locate an item's notes using a path-safe ID and readable name."""
        key = quote(exploration_id, safe="").replace(".", "%2E").replace("-", "%2D")
        label = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]|[ .]+$', "-", name)
        return self.directory / f"{key}-{label}"

    def exploration_record_path(
        self, exploration_id: str, *, name: str | None = None
    ) -> Path:
        """Locate the Markdown record using a known item name or the latest name in the pool."""
        if name is None:
            name = self.get(exploration_id).name
        return (
            self.item_directory(exploration_id, name) / EXPLORATION_RECORD_FILENAME
        ).resolve()

    def append_record(self, exploration_id: str, record_entry: str) -> None:
        """Append working notes without changing the graph."""
        if self.read_only:
            raise PermissionError(
                "Cannot append notes through a read-only exploration pool."
            )
        with self.exploration_record_path(exploration_id).open(
            "a", encoding="utf-8"
        ) as record:
            record.write(record_entry.rstrip("\n") + "\n")

    def fetch_item(
        self, db: sqlite3.Connection, exploration_id: str
    ) -> ExplorationItem:
        """Read one node within the caller's transaction."""
        row = db.execute(
            "SELECT * FROM explorations WHERE exploration_id = ?", (exploration_id,)
        ).fetchone()
        if row is None:
            raise FileNotFoundError(
                f"Exploration {exploration_id!r} not found in {self.directory}"
            )
        return item_from_row(row)

    def get(self, exploration_id: str) -> ExplorationItem:
        """Read one registered exploration by its stable ID."""
        with self.connection() as db:
            return self.fetch_item(db, exploration_id)

    def is_empty(self) -> bool:
        """Tell the submitting workflow whether a baseline has been registered."""
        with self.connection() as db:
            return db.execute("SELECT 1 FROM explorations LIMIT 1").fetchone() is None

    def list(self, task_revision_number: int | None = None) -> list[ExplorationItem]:
        """Read a snapshot in numeric-then-text ID order, optionally for one task revision."""
        query = "SELECT * FROM explorations"
        params = () if task_revision_number is None else (task_revision_number,)
        if params:
            query += " WHERE task_revision_number = ?"
        query += """ ORDER BY exploration_id GLOB '*[^0-9]*',
            CASE WHEN exploration_id NOT GLOB '*[^0-9]*' THEN length(ltrim(exploration_id, '0')) END,
            CASE WHEN exploration_id NOT GLOB '*[^0-9]*' THEN ltrim(exploration_id, '0') END, exploration_id"""
        try:
            with self.connection() as db:
                return [item_from_row(row) for row in db.execute(query, params)]
        except FileNotFoundError:
            return []

    def changes(self) -> Generator[bool]:
        """Yield whether the viewer should reload on each poll; close the iterator when the viewer exits."""
        previous = None
        while True:
            try:
                identity = self.database_path.stat()
                # data_version is connection-local. Reconnect if a session of the same name replaces it.
                with self.connection() as db:
                    previous = None
                    while samestat(identity, self.database_path.stat()):
                        version = db.execute("PRAGMA data_version").fetchone()[0]
                        changed = version != previous
                        previous = version
                        yield changed
            except FileNotFoundError:
                changed = previous is not None
                previous = None
                yield changed
