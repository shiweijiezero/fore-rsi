# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Manage Codex workflow records and profile links."""

import json
import os
import re
from pathlib import Path
from uuid import UUID

ROLLOUT_DIRECTORIES = ("sessions", "archived_sessions")


def link_rollout_directory(link: Path, target: Path) -> None:
    """Expose workflow-owned rollouts through the member profile without replacing existing data."""
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    link.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except FileExistsError:
        if not link.is_symlink() or link.resolve() != target.resolve():
            raise RuntimeError(f"Codex profile directory is already in use: {link}") from None


def prepare_codex_profile(profile: Path, storage: Path) -> None:
    """Link Codex's workflow rollouts and user settings into this member's profile."""
    # Native paginated forks find inherited history by ID in the same rollout store.
    for name in ROLLOUT_DIRECTORIES:
        link_rollout_directory(profile / name, storage / name)

    origin = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser().resolve()
    origin.mkdir(mode=0o700, parents=True, exist_ok=True)
    profile.mkdir(mode=0o700, parents=True, exist_ok=True)
    if profile.resolve() == origin:
        return

    names = (
        "config.toml",
        "auth.json",
        "AGENTS.md",
        "AGENTS.override.md",
        "rules",
        "skills",
        "hooks.json",
        "hooks",
        "plugins",
        "agents",
        *(path.name for path in origin.glob("*.config.toml")),
    )
    for name in names:
        source, link = origin / name, profile / name
        if link.is_symlink():
            if link.resolve() != source.resolve():
                raise ValueError("This Codex conversation belongs to a different CODEX_HOME.")
        elif not link.exists() and (source.exists() or name == "auth.json"):
            # Codex can write a file-based login through this link without copying credentials.
            link.symlink_to(source, target_is_directory=source.is_dir())


def thread_record_files(thread_id: str, storage: Path) -> tuple[Path, ...]:
    """Locate active and archived rollout segments of one pinned Codex thread."""
    thread = str(UUID(thread_id))
    timestamp = r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}"
    filename = re.compile(rf"rollout-{timestamp}-{thread}(?:-[0-9a-f-]+)?\.jsonl(?:\.zst)?")
    return tuple(sorted(path.resolve() for name in ROLLOUT_DIRECTORIES
                        for path in (storage / name).rglob(f"rollout-*-{thread}*.jsonl*")
                        if filename.fullmatch(path.name) and path.is_file()))


def get_codex_thread(record: Path, storage: Path) -> str | None:
    """Find the member's persisted thread without selecting another member's rollout."""
    if record.exists():
        thread = str(UUID(record.read_text(encoding="utf-8").strip()))
        # Starting Codex pins its identity before the first prompt materializes a rollout.
        # Codex may append a separate rollout UUID after reverting a paginated thread.
        return thread if thread_record_files(thread, storage) else None

    # Older members discovered the root at shutdown and kept an isolated rollout directory.
    # Never search the entire shared tree for an unpinned thread.
    roots: set[str] = set()
    sessions = storage / "sessions" / record.stem
    for path in sorted(sessions.rglob("rollout-*.jsonl")):
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "session_meta":
                    continue
                metadata = entry.get("payload", {})
                if (
                    isinstance(metadata, dict)
                    and metadata.get("id")
                    and not metadata.get("forked_from_id")
                    and not metadata.get("parent_thread_id")
                ):
                    try:
                        roots.add(str(UUID(metadata["id"])))
                    except (TypeError, ValueError):
                        pass
                break

    if len(roots) > 1:
        raise RuntimeError(f"Cannot identify one root Codex conversation in {sessions}.")
    return roots.pop() if roots else None
