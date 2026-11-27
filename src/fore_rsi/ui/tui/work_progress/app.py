# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Display a session's exploration graph and selected exploration."""

import asyncio
import os
from pathlib import Path
from urllib.parse import quote

from rich.console import Console, Group
from rich.style import Style
from rich.table import Table
from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Static, Tab, Tabs

from fore_rsi.rsi_workflows.workflow_runtimes.exploration_pool import ExplorationItem, ExplorationPool
from .exploration_graph import COLORS, STATUS, ExplorationGraph


STATUS_LABELS = dict(zip(STATUS, ["待确认", "探索中", "待实验", "实验中", "已终止", "已成熟"], strict=True))
TRANSLATIONS = {
    "ForeRSI / 工作进展": "ForeRSI / Work progress",
    "探索演进图": "Exploration graph",
    "暂无可显示的探索节点": "No explorations to display",
    "概览": "Overview",
    "实验": "Experiments",
    "探索记录": "Exploration log",
    "父节点": "Parents",
    "实验结果": "Experiment result",
    "任务版本": "Task revision",
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
    **{label: status.replace("_", " ").capitalize() for status, label in STATUS_LABELS.items()},
}


class ProgressDivider(Static):
    """Capture the mouse while resizing the graph and detail panels."""

    ALLOW_SELECT = False

    def __init__(self) -> None:
        super().__init__(id="resize-handle")
        self.dragging = False

    def render(self) -> Text:
        corner = "└" if self.disabled else "├"
        return Text(corner + "─" * max(0, self.size.width - 1))

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
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [("f", "filter", "切换过滤"), ("d", "toggle_details", "收起/展开详情"),
                ("q", "quit", "退出"), Binding("escape", "quit", show=False)]

    CSS = """
    Screen { background: #090e11; color: #dbe3e5; }
    #masthead { height: 1; padding: 0 1; }
    #brand { width: 1fr; color: #ecf5f6; text-style: bold; }
    #toggle-language { height: 1; width: auto; min-width: 8; border: none; padding: 0 1; background: #10191e; color: #82e3e7; }
    #progress-panels { height: 1fr; }
    #lineage, #details { border: solid #475359; padding: 0 1; height: 1fr; }
    #lineage { border-bottom: none; }
    #details { border-top: none; }
    #panel-divider { height: 1; }
    #resize-handle { height: 1; width: 1fr; color: #475359; }
    #resize-handle:hover { color: #82e3e7; }
    #toggle-details { height: 1; width: 3; min-width: 3; border: none; padding: 0; background: #090e11; color: #82e3e7; }
    #divider-end { height: 1; width: 1; color: #475359; }
    .heading { height: 1; text-style: bold; color: #82e3e7; }
    #legend { height: auto; text-align: right; }
    #empty { height: 1fr; content-align: center middle; color: #98a6aa; }
    #detail-bar { height: 2; }
    #detail-tabs { height: 2; width: 1fr; }
    #detail-name { width: auto; max-width: 40%; height: 1; padding-right: 2; text-style: bold; text-overflow: ellipsis; text-wrap: nowrap; }
    #detail-parents { width: auto; max-width: 35%; height: 1; padding-left: 2; text-align: right; color: #98a6aa; text-overflow: ellipsis; text-wrap: nowrap; }
    Tab { height: 1; padding: 0 1; }
    Tab.-active { color: #72e2e8; text-style: bold; }
    #detail-tabs .underline--bar { color: #61dce5; background: #090e11; }
    Footer { background: #10191e; }
    """

    def __init__(self, session_directory: Path, *, embedded: bool = False) -> None:
        # Status colors remain meaningful even in a shell that sets NO_COLOR.
        no_color = os.environ.pop("NO_COLOR", None)
        try:
            super().__init__()
        finally:
            if no_color is not None:
                os.environ["NO_COLOR"] = no_color
        self.console = Console(
            color_system="truecolor", file=self.console.file, no_color=False,
            force_terminal=True, highlight=False, emoji=False, legacy_windows=False,
            safe_box=False, soft_wrap=False,
        )
        self.workspace = Path.cwd()
        self.pool = ExplorationPool(self.workspace)
        self.session_name = session_directory.name
        self.language = "zh"
        self.embedded = embedded
        self.last_filter = "retired"
        self.hidden_status = None
        self.items = None
        self.selected = None
        self.record = ""
        self.tab = "overview-tab"
        self.details_visible = True
        self.split_ratio = 0.5

    def tr(self, text: str) -> str:
        return TRANSLATIONS.get(text, text) if self.language == "en" else text

    def compose(self) -> ComposeResult:
        with Horizontal(id="masthead"):
            yield Static(self.tr("ForeRSI / 工作进展"), id="brand")
            yield Button("English", id="toggle-language", tooltip=self.tr("切换语言"))
        with ProgressPanels(id="progress-panels"):
            with Vertical(id="lineage"):
                yield Static("▎" + self.tr("探索演进图"), id="graph-heading", classes="heading")
                legend = Static(self.legend(), id="legend")
                # Keep click actions without automatic link colors and underlines.
                legend.auto_links = False
                yield legend
                yield Static(self.tr("暂无可显示的探索节点"), id="empty")
                yield ExplorationGraph()
            with Horizontal(id="panel-divider"):
                yield ProgressDivider()
                yield Button("─▼─", id="toggle-details", tooltip=self.tr("收起详情（D）"))
                yield Static("┤", id="divider-end")
            with Vertical(id="details"):
                with Horizontal(id="detail-bar"):
                    yield Static(id="detail-name", markup=False)
                    yield Tabs(Tab(self.tr("概览"), id="overview-tab"), Tab(self.tr("实验"), id="experiment"),
                               Tab(self.tr("探索记录"), id="record"), id="detail-tabs")
                    yield Static(id="detail-parents", markup=False)
                with VerticalScroll(id="detail-scroll"):
                    yield Static(id="body", markup=False)
        yield ProgressFooter()

    @on(Button.Pressed, "#toggle-language")
    def action_toggle_language(self) -> None:
        self.language = "en" if self.language == "zh" else "zh"
        button = self.query_one("#toggle-language", Button)
        button.label = "中文" if self.language == "en" else "English"
        button.tooltip = self.tr("切换语言")
        self.query_one("#brand", Static).update(self.tr("ForeRSI / 工作进展"))
        self.query_one("#graph-heading", Static).update("▎" + self.tr("探索演进图"))
        self.query_one("#empty", Static).update(self.tr("暂无可显示的探索节点"))
        for tab_id, label in (("overview-tab", "概览"), ("experiment", "实验"), ("record", "探索记录")):
            self.query_one(f"#{tab_id}", Tab).label = self.tr(label)
        self.query_one("#legend", Static).update(self.legend())
        self.query_one("#toggle-details", Button).tooltip = self.tr(
            "收起详情（D）" if self.details_visible else "展开详情（D）"
        )
        self.redraw()
        self.query_one(ProgressFooter).refresh(recompose=True)

    async def on_mount(self) -> None:
        self.graph = self.query_one(ExplorationGraph)
        await self.refresh_items()
        if self.items:
            self.graph.focus()
        self.set_interval(1, self.refresh_items)
        self.call_after_refresh(self.apply_split)

    def apply_split(self) -> None:
        panels = self.query_one("#progress-panels")
        available = max(0, panels.content_size.height - 1)
        if not available:
            return
        lineage = self.query_one("#lineage")
        details = self.query_one("#details")
        details.display = self.details_visible
        if self.details_visible:
            minimum = min(6, available // 2)
            upper = max(minimum, min(available - minimum, round(available * self.split_ratio)))
            lineage.styles.height = upper
            details.styles.height = available - upper
        else:
            lineage.styles.height = available

    def resize_panels(self, screen_y: int) -> None:
        if self.details_visible:
            panels = self.query_one("#progress-panels")
            available = max(1, panels.content_size.height - 1)
            minimum = min(6, available // 2)
            upper = max(minimum, min(available - minimum, screen_y - panels.content_region.y))
            self.split_ratio = upper / available
            self.apply_split()

    @on(Button.Pressed, "#toggle-details")
    def action_toggle_details(self) -> None:
        self.details_visible = not self.details_visible
        button = self.query_one("#toggle-details", Button)
        button.label = "─▼─" if self.details_visible else "─▲─"
        button.tooltip = self.tr("收起详情（D）" if self.details_visible else "展开详情（D）")
        self.query_one("#divider-end", Static).update("┤" if self.details_visible else "┘")
        self.query_one(ProgressDivider).disabled = not self.details_visible
        self.apply_split()
        if not self.details_visible:
            self.graph.focus()

    async def refresh_items(self) -> None:
        items = await asyncio.to_thread(self.pool.list)
        if items != self.items:
            self.items = items
            self.redraw()
        if self.tab == "record" and self.selected:
            await self.refresh_record()

    def legend(self) -> Text:
        legend = Text()
        for status, color in zip(STATUS, COLORS, strict=True):
            if legend:
                legend.append("  ")
            hidden = status == self.hidden_status
            click = {"@click": f"app.filter('{status}')"}
            legend.append("██", Style(color=color, bgcolor=color, meta=click))
            legend.append(" " + self.tr(STATUS_LABELS[status]), Style(color=color, dim=hidden, strike=hidden, meta=click))
        return legend

    def action_filter(self, status: str | None = None) -> None:
        self.last_filter = status or self.last_filter
        self.hidden_status = None if self.hidden_status == self.last_filter else self.last_filter
        self.query_one("#legend", Static).update(self.legend())
        self.redraw()

    def redraw(self) -> None:
        hidden = {i.exploration_id for i in self.items if i.status == self.hidden_status}
        visible = [i for i in self.items if i.exploration_id not in hidden]
        old_id = self.selected.exploration_id if self.selected else None
        self.selected = next((i for i in visible if i.exploration_id == old_id), next(iter(visible), None))
        selected_id = self.selected.exploration_id if self.selected else None
        self.graph.show_items(self.items, selected_id, hidden)
        self.graph.display = bool(visible)
        self.query_one("#empty").display = not visible
        self.render_details()

    async def on_exploration_graph_selected(self, event: ExplorationGraph.Selected) -> None:
        self.selected = event.item
        self.record = ""
        self.redraw()
        self.query_one("#detail-scroll", VerticalScroll).scroll_home(animate=False)
        if self.tab == "record":
            await self.refresh_record()

    def on_exploration_graph_inspect(self) -> None:
        if not self.details_visible:
            self.action_toggle_details()
        self.query_one("#detail-tabs", Tabs).focus()

    async def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        self.tab = event.tab.id
        self.query_one("#detail-scroll", VerticalScroll).scroll_home(animate=False)
        self.render_details()
        if self.tab == "record" and self.selected:
            await self.refresh_record()

    def record_path(self, item: ExplorationItem) -> Path:
        folder = quote(item.exploration_id, safe="").replace(".", "%2E")
        return self.pool.directory / folder / item.record_path

    async def refresh_record(self) -> None:
        item = self.selected
        text = await asyncio.to_thread(self.record_path(item).read_text, encoding="utf-8")
        if self.selected == item and self.tab == "record":
            self.record = text
            self.render_details()

    def render_details(self) -> None:
        item = self.selected
        self.query_one("#detail-name", Static).update(f"#{item.exploration_id}  {item.name}" if item else "")
        parents = self.tr("父节点") + " " + ", ".join("#" + p for p in item.parent_exploration_ids) if item and item.parent_exploration_ids else ""
        parent_label = self.query_one("#detail-parents", Static)
        parent_label.update(parents)
        parent_label.tooltip = parents or None
        body = self.query_one("#body", Static)
        if item is None:
            body.update("")
            return
        content = Text()
        if self.tab == "experiment":
            report = Table(expand=True, border_style="#536367", header_style="bold cyan")
            report.add_column(self.tr("实验结果"))
            report.add_column(self.tr("任务版本"), width=13 if self.language == "en" else 10)
            report.add_row(Text(item.experiment_result or self.tr("暂无实验结果")), f"v{item.task_revision_number}")
            commands = Text("\n".join("$ " + c for c in item.experiment_commands), style="#a6e5ad")
            body.update(Group(Text(item.description), report, commands))
            return
        if self.tab == "record":
            content.append(str(self.record_path(item).relative_to(self.workspace)), "cyan")
            content.append("\n\n" + (self.record.strip() or self.tr("暂无探索记录")))
        else:
            content.append(item.description)
            content.append(f"\n\n{self.tr('任务版本')}  v{item.task_revision_number}", "cyan")
        body.update(content)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if self.embedded and action in {"quit", "help_quit"}:
            return False
        return super().check_action(action, parameters)
