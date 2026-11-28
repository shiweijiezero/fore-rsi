# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Explore a session’s exploration lineage and the publication history of its Watchdog reports."""

import asyncio
import os
from pathlib import Path
from typing import ClassVar

from rich.style import Style
from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, OptionList, Static, Tab, Tabs
from textual.widgets.option_list import Option

from fore_rsi.rsi_workflows.workflow_runtimes.exploration_pool import (
    ExplorationItem,
    ExplorationPool,
)
from fore_rsi.rsi_workflows.workflow_runtimes.watchdog_reports import WatchdogReports

from .details import ProgressDetails
from .exploration_graph import STATUS_STYLES, ExplorationGraph

TRANSLATIONS = {
    "ForeRSI / 工作进展": "ForeRSI / Work progress",
    "暂无可显示的探索节点": "No explorations to display",
    "探索图": "Explorations",
    "巡查报告": "Watchdog reports",
    "无法读取文件": "Cannot read file",
    "正在读取报告…": "Loading report…",
    "概览": "Overview",
    "实验": "Experiments",
    "探索记录": "Exploration log",
    "父节点": "Parents",
    "实验结果": "Experiment result",
    "任务版本": "Task revision",
    "代码工作区": "Code workspace",
    "暂无实验结果": "No experiment result yet",
    "暂无探索记录": "No exploration log yet",
    "外部引用": "External reference",
    "收起详情（D）": "Collapse details (D)",
    "展开详情（D）": "Expand details (D)",
    "切换语言": "Switch language",
    "切换过滤": "Toggle filter",
    "收起/展开详情": "Toggle details",
    "查看详情": "View details",
    "退出": "Quit",
    **{
        label: status.replace("_", " ").capitalize()
        for status, (label, _) in STATUS_STYLES.items()
    },
}


class ProgressDivider(Static):
    """Capture the mouse while resizing the graph and detail panels."""

    ALLOW_SELECT = False

    def __init__(self) -> None:
        super().__init__(id="resize-handle")
        self.dragging = False

    def render(self) -> Text:
        return Text("─" * self.size.width)

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 1:
            self.dragging = True
            self.capture_mouse()
            event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self.dragging:
            self.app.resize_panels(event.screen_offset.y)
            event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self.dragging:
            self.dragging = False
            self.app.resize_panels(event.screen_offset.y)
            self.release_mouse()
            event.stop()


class ProgressPanels(Vertical):
    def on_resize(self) -> None:
        self.app.apply_split()


class ProgressFooter(Footer):
    def compose(self) -> ComposeResult:
        for key in super().compose():
            key.description = self.app.tr(key.description)
            if key.tooltip:
                key.tooltip = self.app.tr(str(key.tooltip))
            yield key


class WorkProgressApp(App[None]):
    """Select a node in either graph to read its session-local evidence."""

    ENABLE_COMMAND_PALETTE = False
    BINDINGS: ClassVar[list[BindingType]] = [
        ("f", "filter", "切换过滤"),
        ("d", "toggle_details", "收起/展开详情"),
        ("q", "quit", "退出"),
        Binding("escape", "quit", show=False),
    ]

    CSS = """
    Screen { background: $background; color: $text; }
    #masthead { height: 1; padding: 0 1; }
    #brand { width: 1fr; text-style: bold; }
    #toggle-language, #toggle-details { height: 1; border: none; background: $background; color: $primary; }
    #toggle-language { width: auto; min-width: 8; padding: 0 1; }
    #toggle-details { width: 3; min-width: 3; padding: 0; }
    #progress-panels { height: 1fr; }
    #graphs, #details { height: 1fr; }
    #lineage { width: 2fr; padding: 0 1; }
    #report-history { width: 1fr; padding: 0 1; border-left: solid $panel; }
    #report-chain { height: 1fr; background: $background; }
    #reports-title, #explorations-title { height: 1; text-style: bold; }
    #details { padding: 0 1; }
    #panel-divider { height: 1; }
    #resize-handle { height: 1; width: 1fr; color: $text-muted; }
    #resize-handle:hover { color: $primary; }
    #divider-end { height: 1; width: 1; color: $text-muted; }
    #legend { height: auto; }
    #empty { height: 1fr; content-align: center middle; color: $text-muted; }
    #detail-bar { height: 2; }
    #details.-report #detail-bar { height: 1; }
    #details.-report #detail-name { max-width: 100%; }
    #detail-tabs { height: 2; width: 1fr; }
    #detail-name { width: auto; max-width: 40%; height: 1; padding-right: 2; text-style: bold; text-overflow: ellipsis; text-wrap: nowrap; }
    #detail-parents { width: auto; max-width: 35%; height: 1; padding-left: 2; text-align: right; color: $text-muted; text-overflow: ellipsis; text-wrap: nowrap; }
    Tab { height: 1; padding: 0 1; }
    Tab.-active { color: $primary; text-style: bold; }
    #detail-tabs .underline--bar { color: $primary; background: $background; }
    """

    def __init__(self, session_directory: Path, *, embedded: bool = False) -> None:
        # ANSI surfaces use the terminal's actual foreground and background in both light and dark profiles.
        super().__init__(
            ansi_color=True if not os.environ.get("TEXTUAL_THEME") else None
        )
        if not os.environ.get("TEXTUAL_THEME"):
            self.theme = "ansi-dark"
        self.pool = ExplorationPool(session_directory, read_only=True)
        self.pool_changes = self.pool.changes()
        self.watchdog_reports = WatchdogReports(session_directory)
        self.report_paths: list[Path] = []
        self.language = "zh"
        self.embedded = embedded
        self.last_filter = "retired"
        self.hidden_status = None
        self.items: list[ExplorationItem] = []
        self.selected: ExplorationItem | Path | None = None
        self.details_visible = True
        self.split_ratio = 0.5

    def tr(self, text: str) -> str:
        return TRANSLATIONS.get(text, text) if self.language == "en" else text

    def compose(self) -> ComposeResult:
        with Horizontal(id="masthead"):
            yield Static(self.tr("ForeRSI / 工作进展"), id="brand")
            yield Button("English", id="toggle-language", tooltip=self.tr("切换语言"))
        with ProgressPanels(id="progress-panels"):
            with Horizontal(id="graphs"):
                with Vertical(id="lineage"):
                    yield Static(self.tr("探索图"), id="explorations-title")
                    legend = Static(self.legend(), id="legend")
                    # Preserve the status filter actions without automatic link styling.
                    legend.auto_links = False
                    yield legend
                    yield Static(self.tr("暂无可显示的探索节点"), id="empty")
                    yield ExplorationGraph()
                with Vertical(id="report-history"):
                    yield Static(self.tr("巡查报告"), id="reports-title")
                    yield OptionList(id="report-chain", compact=True)
            with Horizontal(id="panel-divider"):
                yield ProgressDivider()
                yield Button(
                    "─▼─", id="toggle-details", tooltip=self.tr("收起详情（D）")
                )
                yield Static("┤", id="divider-end")
            yield ProgressDetails()
        yield ProgressFooter()

    @on(Button.Pressed, "#toggle-language")
    def action_toggle_language(self) -> None:
        self.language = "en" if self.language == "zh" else "zh"
        button = self.query_one("#toggle-language", Button)
        button.label = "中文" if self.language == "en" else "English"
        button.tooltip = self.tr("切换语言")
        self.query_one("#brand", Static).update(self.tr("ForeRSI / 工作进展"))
        self.query_one("#explorations-title", Static).update(self.tr("探索图"))
        self.query_one("#reports-title", Static).update(self.tr("巡查报告"))
        self.query_one("#empty", Static).update(self.tr("暂无可显示的探索节点"))
        for tab_id, label in (
            ("overview-tab", "概览"),
            ("experiment", "实验"),
            ("record", "探索记录"),
        ):
            self.query_one(f"#{tab_id}", Tab).label = self.tr(label)
        self.query_one("#toggle-details", Button).tooltip = self.tr(
            "收起详情（D）" if self.details_visible else "展开详情（D）"
        )
        self.redraw()
        self.query_one(ProgressFooter).refresh(recompose=True)

    async def on_mount(self) -> None:
        self.graph = self.query_one(ExplorationGraph)
        self.report_chain = self.query_one("#report-chain", OptionList)
        self.details = self.query_one(ProgressDetails)
        await self.refresh_items()
        if self.selected is not None:
            (
                self.report_chain if isinstance(self.selected, Path) else self.graph
            ).focus()
        self.set_interval(3, self.refresh_items)
        self.call_after_refresh(self.apply_split)

    def on_unmount(self) -> None:
        """Release the viewer's SQLite change observer."""
        self.pool_changes.close()

    def apply_split(self) -> None:
        panels = self.query_one("#progress-panels")
        has_selection = self.selected is not None
        self.query_one("#panel-divider").display = has_selection
        details = self.query_one("#details")
        details.display = has_selection and self.details_visible
        available = max(0, panels.content_size.height - int(has_selection))
        if not available:
            return
        graphs = self.query_one("#graphs")
        if details.display:
            minimum = min(6, available // 2)
            upper = max(
                minimum, min(available - minimum, round(available * self.split_ratio))
            )
            graphs.styles.height = upper
            details.styles.height = available - upper
        else:
            graphs.styles.height = available

    def resize_panels(self, screen_y: int) -> None:
        if self.details_visible:
            panels = self.query_one("#progress-panels")
            available = max(1, panels.content_size.height - 1)
            minimum = min(6, available // 2)
            upper = max(
                minimum, min(available - minimum, screen_y - panels.content_region.y)
            )
            self.split_ratio = upper / available
            self.apply_split()

    @on(Button.Pressed, "#toggle-details")
    async def action_toggle_details(self) -> None:
        """Reopen the selected node with its latest notes, or return focus to its graph."""
        self.details_visible = not self.details_visible
        button = self.query_one("#toggle-details", Button)
        button.label = "─▼─" if self.details_visible else "─▲─"
        button.tooltip = self.tr(
            "收起详情（D）" if self.details_visible else "展开详情（D）"
        )
        self.query_one("#divider-end", Static).update(
            "┤" if self.details_visible else "┘"
        )
        self.query_one(ProgressDivider).disabled = not self.details_visible
        self.apply_split()
        if self.details_visible:
            await self.details.refresh_file()
        else:
            (
                self.report_chain if isinstance(self.selected, Path) else self.graph
            ).focus()

    async def refresh_items(self) -> None:
        """Refresh both histories independently; new reports must not steal the current selection."""
        changed = next(self.pool_changes)
        if changed:
            self.items = await asyncio.to_thread(self.pool.list)
        paths = await asyncio.to_thread(self.watchdog_reports.list)
        if paths != self.report_paths:
            # Textual provides cursor navigation, hit testing and scrolling. Each option is a node;
            # a fixed arrow before every node except the root connects them in publication order.
            start = len(self.report_paths)
            if paths[:start] != self.report_paths:
                self.report_chain.clear_options()
                start = 0
            self.report_chain.add_options(
                Option(
                    Text(
                        ("↓\n" if i else "") + f"● #{i + 1}  {path.name}",
                        no_wrap=True,
                        overflow="ellipsis",
                    ),
                    id=str(path),
                )
                for i, path in enumerate(paths[start:], start)
            )
            self.report_paths = paths
            changed = True
        if changed or self.selected is None:
            self.redraw()
        if self.details_visible:
            await self.details.refresh_file()

    def legend(self) -> Text:
        legend = Text()
        present = {item.status for item in self.items or ()}
        for status, (label, color) in STATUS_STYLES.items():
            if status not in present:
                continue
            if legend:
                legend.append("  ")
            hidden = status == self.hidden_status
            click = {"@click": f"app.filter('{status}')"}
            legend.append("○" if hidden else "●", Style(color=color, meta=click))
            legend.append(
                " " + self.tr(label), Style(dim=hidden, strike=hidden, meta=click)
            )
        return legend

    async def action_filter(self, status: str | None = None) -> None:
        self.last_filter = status or self.last_filter
        self.hidden_status = (
            None if self.hidden_status == self.last_filter else self.last_filter
        )
        self.redraw()
        await self.details.refresh_file()

    def redraw(self, selection: ExplorationItem | Path | None = None) -> None:
        """Keep the selected node by ID or published path across filters, updates and translation."""
        hidden = {
            i.exploration_id for i in self.items if i.status == self.hidden_status
        }
        visible = [i for i in self.items if i.exploration_id not in hidden]
        if selection is None:
            selection = self.selected
        if not isinstance(selection, Path) or selection not in self.report_paths:
            old_id = (
                selection.exploration_id
                if isinstance(selection, ExplorationItem)
                else None
            )
            selection = next((i for i in visible if i.exploration_id == old_id), None)
            if selection is None:
                selection = (
                    visible[0] if visible else next(iter(self.report_paths), None)
                )
        if selection != self.selected:
            self.details.file = None
            self.details.read_error = ""
        self.selected = selection
        selected_id = (
            selection.exploration_id if isinstance(selection, ExplorationItem) else None
        )
        self.graph.show_items(self.items, selected_id, hidden)
        self.graph.display = bool(visible)
        self.query_one("#empty").display = not visible
        self.query_one("#lineage").display = bool(self.items) or not self.report_paths
        self.query_one("#explorations-title").display = bool(self.report_paths)
        self.query_one("#report-history").display = bool(self.report_paths)
        with self.report_chain.prevent(OptionList.OptionHighlighted):
            self.report_chain.highlighted = (
                self.report_paths.index(selection)
                if isinstance(selection, Path)
                else None
            )
        legend = self.query_one("#legend", Static)
        legend.display = bool(self.items)
        legend.update(self.legend())
        self.apply_split()
        self.details.show_selection()

    async def on_exploration_graph_selected(
        self, event: ExplorationGraph.Selected
    ) -> None:
        """Open the selected exploration in the shared detail pane."""
        await self.select_node(event.item)

    @on(OptionList.OptionHighlighted, "#report-chain")
    @on(OptionList.OptionSelected, "#report-chain")
    async def select_report(self, event: OptionList.OptionMessage) -> None:
        """Show a report on click, Enter or keyboard cursor movement."""
        if (
            event.option_id is not None
            and (path := Path(event.option_id)) in self.report_paths
        ):
            await self.select_node(path)

    @on(events.DescendantFocus, "#report-chain")
    def focus_report_chain(self) -> None:
        """Let keyboard users enter the report chain at its first node."""
        if self.report_chain.highlighted is None:
            self.report_chain.action_first()

    async def select_node(self, selection: ExplorationItem | Path) -> None:
        """Reveal and read a user's choice without allowing a background refresh to move their cursor."""
        changed = selection != self.selected
        if changed:
            self.redraw(selection)
            self.query_one("#detail-scroll", VerticalScroll).scroll_home(animate=False)
        if not self.details_visible:
            await self.action_toggle_details()
        elif changed:
            await self.details.refresh_file()

    async def on_exploration_graph_inspect(self) -> None:
        """Enter the exploration tabs, including when arriving from the report chain by keyboard."""
        if not isinstance(self.selected, ExplorationItem):
            if not self.graph.node_regions:
                return
            await self.select_node(next(iter(self.graph.node_regions.values())))
        if not self.details_visible:
            await self.action_toggle_details()
        self.query_one("#detail-tabs", Tabs).focus()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if self.embedded and action in {"quit", "help_quit"}:
            return False
        return super().check_action(action, parameters)
