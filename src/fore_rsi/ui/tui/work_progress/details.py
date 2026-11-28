# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Show the selected exploration or published Watchdog report in the shared detail pane."""

import asyncio
from pathlib import Path

from rich.console import Group
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, Tab, Tabs


class ProgressDetails(Vertical):
    """Keep exploration tabs independent of the report currently being read."""

    def __init__(self) -> None:
        super().__init__(id="details")
        self.tab = "overview-tab"
        self.file: tuple[Path, str] | None = None
        self.read_error = ""

    def compose(self) -> ComposeResult:
        """Mount one scrollable reading area shared by both graphs."""
        with Horizontal(id="detail-bar"):
            yield Static(id="detail-name", markup=False)
            yield Tabs(
                Tab(self.app.tr("概览"), id="overview-tab"),
                Tab(self.app.tr("实验"), id="experiment"),
                Tab(self.app.tr("探索记录"), id="record"),
                id="detail-tabs",
            )
            yield Static(id="detail-parents", markup=False)
        with VerticalScroll(id="detail-scroll"):
            yield Static(id="body", markup=False)

    async def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        """Show the chosen exploration tab, loading its editable notes only when needed."""
        self.tab = event.tab.id
        self.query_one(VerticalScroll).scroll_home(animate=False)
        self.show_selection()
        await self.refresh_file()

    def show_selection(self) -> None:
        """Render the current graph selection from the last snapshot; do not read files here."""
        selected = self.app.selected
        is_report = isinstance(selected, Path)
        self.set_class(is_report, "-report")
        self.query_one(Tabs).display = not is_report
        parents = self.query_one("#detail-parents", Static)
        parents.display = not is_report
        title = self.query_one("#detail-name", Static)
        body = self.query_one("#body", Static)
        if is_report:
            number = self.app.report_paths.index(selected) + 1
            title.update(f"{self.app.tr('巡查报告')} #{number}")
            content = Text(self.app.tr("正在读取报告…"))
            if self.read_error:
                content = Text(f"{self.app.tr('无法读取文件')}: {self.read_error}")
            elif self.file and self.file[0] == selected:
                content = Markdown(self.file[1])
            path = selected.relative_to(self.app.watchdog_reports.directory.parent)
            body.update(Group(Text(str(path), style="dim"), Text(), content))
            return

        item = selected
        title.update(f"#{item.exploration_id}  {item.name}" if item else "")
        parent_text = ""
        if item and item.parent_exploration_ids:
            parent_text = (
                self.app.tr("父节点")
                + " "
                + ", ".join("#" + p for p in item.parent_exploration_ids)
            )
        parents.update(parent_text)
        parents.tooltip = parent_text or None
        if item is None:
            body.update("")
            return
        revision = (
            f"v{item.task_revision_number}"
            if item.task_revision_number is not None
            else "—"
        )
        if self.tab == "experiment":
            report = Table(expand=True, border_style="dim", header_style="bold")
            report.add_column(self.app.tr("实验结果"))
            report.add_column(
                self.app.tr("任务版本"), width=13 if self.app.language == "en" else 10
            )
            result = Text()
            if item.experiment_summary:
                result.append(item.experiment_summary + "\n", style="bold")
            result.append(item.experiment_result or self.app.tr("暂无实验结果"))
            report.add_row(result, revision)
            commands = Text("\n".join("$ " + c for c in item.experiment_commands))
            body.update(Group(Text(item.description), report, commands))
        elif self.tab == "record":
            content = Text()
            if self.read_error:
                content.append(f"{self.app.tr('无法读取文件')}: {self.read_error}")
            elif self.file:
                path, text = self.file
                content.append(str(path), "bold")
                content.append(
                    "\n\n" + (text if text.strip() else self.app.tr("暂无探索记录"))
                )
            body.update(content)
        else:
            content = Text(item.description)
            content.append(f"\n\n{self.app.tr('任务版本')}  {revision}")
            if item.code_workspace_path:
                content.append(
                    f"\n{self.app.tr('代码工作区')}  {item.code_workspace_path}"
                )
            body.update(content)

    async def refresh_file(self) -> None:
        """Read the selected document off the UI thread and discard reads for obsolete selections."""
        selected = self.app.selected
        if isinstance(selected, Path):
            path = selected
            directory = self.app.watchdog_reports.directory
        elif selected and self.tab == "record":
            path = self.app.pool.exploration_record_path(
                selected.exploration_id, name=selected.name
            )
            directory = None
        else:
            return
        try:
            text = await asyncio.to_thread(read_document, path, directory)
            record, error = (path, text), ""
        except (OSError, UnicodeError) as exc:
            # An exploration can be renamed, or a previously published report removed.
            record, error = None, str(exc)
        if self.app.selected != selected or (
            not isinstance(selected, Path) and self.tab != "record"
        ):
            return
        if (self.file, self.read_error) != (record, error):
            self.file, self.read_error = record, error
            self.show_selection()


def read_document(path: Path, report_directory: Path | None) -> str:
    """Read notes or recheck a report's location in case its published path was replaced."""
    if report_directory is not None and (
        path.resolve(strict=True) != path or not path.is_relative_to(report_directory)
    ):
        raise PermissionError("Report is no longer at its published location.")
    return path.read_text(encoding="utf-8")
