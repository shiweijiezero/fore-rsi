# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Keep the publication order of a session's agent-authored Watchdog reports."""

from __future__ import annotations

import json
import re
from pathlib import Path

from fore_rsi.utils.paths import write_private_text


class WatchdogReports:
    """Index report paths for the progress viewer without copying or rewriting their contents."""

    def __init__(self, session_directory: Path) -> None:
        """Bind the session directory without creating files when only viewing history."""
        self.directory = session_directory.resolve() / "watchdog_reports"
        self.index = self.directory / "published.json"

    def start_review(self, member_name: str, number: int) -> Path:
        """Give the author a new working directory without exposing its draft in the report chain."""
        directory = self.directory / f"{member_name}-review-{number}"
        if directory.resolve() != directory or directory.parent != self.directory:
            raise ValueError(f"Invalid Watchdog review directory: {directory}")
        directory.mkdir(mode=0o700, parents=True)
        if not self.index.exists():
            # Import previously published flat files before the first new draft can be written.
            self.write_index(self.published_names())
        return directory

    def list(self) -> list[Path]:
        """Return readable, published Markdown files in submission order, excluding drafts."""
        paths = (self.directory / name for name in self.published_names())
        return [path for path in paths if path.is_relative_to(self.directory) and path.resolve() == path
                and path.suffix.lower() == ".md" and path.is_file()]

    def publish(self, report_path: Path, review_directory: Path) -> Path:
        """Register the current review's completed file and return its absolute path to the author."""
        if not report_path.is_absolute():
            raise ValueError("Submit the absolute path of the report you wrote.")
        path = report_path.resolve()
        if not (path.is_relative_to(review_directory) and path.is_relative_to(self.directory)
                and path.suffix.lower() == ".md" and path.is_file()):
            raise ValueError(f"Write a Markdown report under {review_directory} before submitting its path.")
        if not path.read_text(encoding="utf-8").strip():
            raise ValueError("Write the review findings before submitting an empty report.")

        # One Watchdog is on duty per workflow. Its synchronous submission publishes the index
        # only after the report is readable; concurrent viewers see either complete version.
        names = self.published_names()
        name = path.relative_to(self.directory).as_posix()
        if name in names:
            raise ValueError("This report has already been published.")
        self.write_index([*names, name])
        return path

    def write_index(self, names: list[str]) -> None:
        """Expose one complete publication list to viewers refreshing concurrently."""
        write_private_text(self.index, json.dumps(names, ensure_ascii=False, indent=2) + "\n")

    def published_names(self) -> list[str]:
        """Read the index, or recover the order of reports published under the earlier flat naming scheme."""
        if self.index.resolve().parent != self.directory:
            raise ValueError("The report index must belong to this session's watchdog_reports directory.")
        try:
            return json.loads(self.index.read_text(encoding="utf-8"))
        except FileNotFoundError:
            numbered = []
            for path in self.directory.glob("watchdog-*-review-*.md"):
                if match := re.fullmatch(r"watchdog-(\d+)-review-(\d+)\.md", path.name):
                    numbered.append((int(match[1]), int(match[2]), path.name))
            return [name for _, _, name in sorted(numbered)]
