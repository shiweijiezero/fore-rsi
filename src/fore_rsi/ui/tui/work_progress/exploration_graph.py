# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Draw the exploration lineage in terminal cells, one generation per column."""

from collections import defaultdict
from graphlib import TopologicalSorter
from typing import get_args

from rich.text import Text
from textual import events
from textual.containers import ScrollableContainer
from textual.geometry import Region
from textual.message import Message
from textual.widgets import Static

from fore_rsi.rsi_workflows.workflow_runtimes.exploration_pool import (
    ExplorationItem,
    ExplorationItemStatus,
)


BOX_WIDTH = 18
COLUMN_STEP = BOX_WIDTH + 6
STATUS = get_args(ExplorationItemStatus)
# Colors follow the order declared by ExplorationItemStatus.
COLORS = ["#9ba6ac", "#efca61", "#81bde0", "#c79df2", "#f17b72", "#91d987"]


def layout(items, hidden):
    parents = {item.exploration_id: list(dict.fromkeys(item.parent_exploration_ids)) for item in items}
    if hidden:
        # Resolve hidden chains before placing the remaining nodes into columns.
        for key in TopologicalSorter(parents).static_order():
            if key in parents:
                parents[key] = list(dict.fromkeys(
                    ancestor
                    for parent in parents[key]
                    for ancestor in (parents[parent] if parent in hidden else [parent])
                ))
        parents = {key: sources for key, sources in parents.items() if key not in hidden}
    columns = defaultdict(list)
    depths = {}
    for key in TopologicalSorter(parents).static_order():
        depth = max((depths[p] + 1 for p in parents.get(key, ())), default=0)
        depths[key] = depth
        columns[depth].append(key)

    # Reserve a lane in each skipped generation so long edges pass between boxes.
    edges = []
    for child, sources in parents.items():
        for parent in sources:
            previous = parent
            for depth in range(depths[parent] + 1, depths[child]):
                waypoint = (parent, child, depth)
                columns[depth].append(waypoint)
                edges.append((previous, waypoint))
                previous = waypoint
            edges.append((previous, child))

    heights = {key: max(4, len(parents.get(key, ())) + 2) for key in depths}
    column_heights = {
        depth: sum(heights.get(key, 4) + 1 for key in column) - 1
        for depth, column in columns.items()
    }
    height = max(column_heights.values(), default=0)
    positions = {}
    for depth, column in columns.items():
        y = (height - column_heights[depth]) // 2
        for key in column:
            positions[key] = (depth * COLUMN_STEP, y)
            y += heights.get(key, 4) + 1
    return positions, edges, heights


def draw_edge(cells, start, end, color):
    # Braille gives each terminal cell two horizontal and four vertical dots.
    x0, y0 = start
    x1, y1 = end
    dx, dy = (x1 - x0) * 2, (y1 - y0) * 4
    steps = max(abs(dx), abs(dy), 1)
    bits = ((1, 2, 4, 64), (8, 16, 32, 128))
    for step in range(steps + 1):
        x = x0 * 2 + round(dx * step / steps)
        y = y0 * 4 + 1 + round(dy * step / steps)
        point = x // 2, y // 4
        dots = cells.get(point, (0, color))[0]
        cells[point] = dots | bits[x % 2][y % 4], color


class ExplorationGraph(ScrollableContainer):
    class Inspect(Message):
        """Move focus to the selected exploration's detail tabs."""

    class Selected(Message):
        def __init__(self, item: ExplorationItem):
            super().__init__()
            self.item = item

    DEFAULT_CSS = """
    ExplorationGraph { height: 1fr; }
    ExplorationGraph > Static { width: auto; height: auto; }
    """

    BINDINGS = [(key, f"move_node('{key}')", "") for key in ("left", "right", "up", "down")] + [
        ("enter", "inspect", "查看详情")
    ]

    def action_inspect(self):
        self.post_message(self.Inspect())

    def action_move_node(self, direction):
        if not self.node_regions:
            return
        current = next((r for r, item in self.node_regions.items() if item.exploration_id == self.selected), None)
        if current is None:
            target = next(iter(self.node_regions))
        else:
            choices = []
            for region in self.node_regions:
                dx, dy = region.x - current.x, region.y - current.y
                forward, side = {"right": (dx, dy), "left": (-dx, dy), "down": (dy, dx), "up": (-dy, dx)}[direction]
                if forward > 0:
                    choices.append((forward + abs(side), abs(side), region))
            if not choices:
                return
            target = min(choices, key=lambda choice: choice[:2])[2]
        self.scroll_to_region(target, animate=False)
        self.post_message(self.Selected(self.node_regions[target]))

    def compose(self):
        yield Static()

    def show_items(self, items: list[ExplorationItem], selected: str | None = None, hidden=frozenset()) -> None:
        by_id = {item.exploration_id: item for item in items}
        self.selected = selected
        positions, edges, heights = layout(items, hidden)
        incoming = defaultdict(list)
        for source, target in edges:
            if isinstance(target, str):
                incoming[target].append(source)
        ports = {}
        for target, sources in incoming.items():
            sources.sort(key=lambda source: positions[source][1])
            for row, source in enumerate(sources, start=1):
                ports[source, target] = positions[target][1] + row
        cells = {}
        arrows = {}
        boxes = {}
        self.node_regions = {}
        for source, target in edges:
            destination = target[1] if isinstance(target, tuple) else target
            item = by_id.get(destination)
            color = COLORS[STATUS.index(item.status)] if item else "grey58"
            x, y = positions[source]
            tx, ty = positions[target]
            start = x + (BOX_WIDTH if isinstance(source, str) else BOX_WIDTH // 2)
            end = tx - 1 if isinstance(target, str) else tx + BOX_WIDTH // 2
            if isinstance(target, str):
                ty = ports[source, target]
                arrows[end, ty] = color
                draw_edge(cells, (start, y + 1), (end - 1, ty), color)
            else:
                draw_edge(cells, (start, y + 1), (end, ty + 1), color)

        for key, (x, y) in positions.items():
            if not isinstance(key, str):
                continue
            item = by_id.get(key)
            if item:
                self.node_regions[Region(x, y, BOX_WIDTH, heights[key])] = item
            color = COLORS[STATUS.index(item.status)] if item else "grey58"
            tl, tr, bl, br, horizontal, vertical = "╔╗╚╝═║" if key == selected else "╭╮╰╯─│"
            title = f"#{key} {item.name}" if item else f"#{key}"
            subtitle = (item.experiment_result or "") if item else self.app.tr("外部引用")
            lines = [(tl + horizontal * (BOX_WIDTH - 2) + tr, color)]
            for label in [title, subtitle] + [""] * (heights[key] - 4):
                content = Text(" ".join(label.split()))
                content.truncate(BOX_WIDTH - 2, overflow="ellipsis")
                content.align("center", BOX_WIDTH - 2)
                lines.append((f"{vertical}{content.plain}{vertical}", color))
            lines.append((bl + horizontal * (BOX_WIDTH - 2) + br, color))
            for offset, line in enumerate(lines):
                boxes[x, y + offset] = line

        width = max((x + BOX_WIDTH for x, _ in positions.values()), default=0)
        height = max((y + heights.get(key, 4) for key, (_, y) in positions.items()), default=0)
        drawing = Text(no_wrap=True)
        for y in range(height):
            if y:
                drawing.append("\n")
            x = 0
            while x < width:
                if (x, y) in boxes:
                    drawing.append(*boxes[x, y])
                    x += BOX_WIDTH
                else:
                    dots, color = cells.get((x, y), (0, None))
                    glyph = "▶" if (x, y) in arrows else chr(0x2800 + dots) if dots else " "
                    drawing.append(glyph, style=arrows.get((x, y), color))
                    x += 1
        self.query_one(Static).update(drawing)

    def on_click(self, event: events.Click) -> None:
        point = event.screen_offset - self.query_one(Static).region.offset
        for region, item in self.node_regions.items():
            if region.contains_point(point):
                self.post_message(self.Selected(item))
                return
