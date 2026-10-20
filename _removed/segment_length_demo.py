"""
segment_length_demo.py

A standalone Tkinter reference implementation of "Dynamic Segment Length
Measurement via Vertex Selection" -- kept separate from the Flask/JS
Geometry Workspace (which already has this same behaviour built into its
canvas), so you have a small, self-contained script to read, run, or
adapt for a different backend (Pygame, PyQt, etc.) without wading through
the full web app.

Behaviour
---------
- Click empty canvas space  -> places a new vertex (Point).
- Click an existing vertex  -> "selects" it (drawn with a highlight ring).
- Selecting a SECOND vertex -> instantly draws a Segment between the two
  and computes their Euclidean distance.
- Drag any vertex           -> every Segment attached to it redraws AND
  its length label updates live, every frame -- because the label is
  computed from the two Point objects' current coordinates each time we
  paint, never cached.

Run:  python segment_length_demo.py
"""

from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Model: plain geometry objects, no Tkinter/canvas knowledge here at all.
# This mirrors the "Point / Segment / Scene" split used in the project's
# own JS geometry engine (model.js), so the same mental model applies.
# ---------------------------------------------------------------------------

POINT_RADIUS = 6
HIT_TOLERANCE = 10  # pixels; how close a click must land to "hit" a point


@dataclass
class Point:
    """A single draggable vertex, in canvas (pixel) coordinates."""
    x: float
    y: float
    label: str = ""

    def distance_to_xy(self, x: float, y: float) -> float:
        return math.hypot(self.x - x, self.y - y)


@dataclass
class Segment:
    """A line between two Points. Holds REFERENCES, not copies, of its
    endpoints -- so when a Point moves, every Segment built on it is
    automatically up to date; there is nothing to manually re-sync."""
    p1: Point
    p2: Point

    def length(self) -> float:
        """Standard Euclidean distance formula: sqrt((x2-x1)^2 + (y2-y1)^2)."""
        return math.hypot(self.p2.x - self.p1.x, self.p2.y - self.p1.y)

    def midpoint(self) -> tuple[float, float]:
        return ((self.p1.x + self.p2.x) / 2, (self.p1.y + self.p2.y) / 2)


@dataclass
class Scene:
    """Owns every Point and Segment currently on the canvas."""
    points: list[Point] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)
    _next_label_index: int = 0

    def add_point(self, x: float, y: float) -> Point:
        letter = chr(ord('A') + (self._next_label_index % 26))
        self._next_label_index += 1
        p = Point(x, y, label=letter)
        self.points.append(p)
        return p

    def add_segment(self, p1: Point, p2: Point) -> Segment:
        seg = Segment(p1, p2)
        self.segments.append(seg)
        return seg

    def point_at(self, x: float, y: float, tolerance: float = HIT_TOLERANCE) -> Optional[Point]:
        """Return the closest Point within `tolerance` pixels of (x, y),
        or None. This is the "hit test" the click handler uses to decide
        whether a click selected an existing vertex vs. empty space."""
        best, best_d = None, tolerance
        for p in self.points:
            d = p.distance_to_xy(x, y)
            if d <= best_d:
                best, best_d = p, d
        return best


# ---------------------------------------------------------------------------
# View + Controller: the Tkinter canvas, its event bindings, and drawing.
# ---------------------------------------------------------------------------

class GeometryApp:
    """
    Owns the Tk window/canvas and wires up mouse events:

    - <Button-1>        (mouse DOWN): decide whether we hit an existing
      vertex (select / start a drag) or empty space (place a new vertex,
      or complete a 2-vertex selection into a Segment).
    - <B1-Motion>        (mouse MOVE while button held): if a drag is in
      progress, update the dragged Point's coordinates -- redraw() then
      picks that up automatically because Segment.length() always reads
      the Points' CURRENT x/y, never a stale cached value.
    - <ButtonRelease-1> (mouse UP): end the drag.

    Tkinter delivers each of these as an `event` object with `event.x` /
    `event.y` already in canvas-local pixel coordinates -- that's the
    entire "capture" step; no manual coordinate transform is needed here
    because we treat canvas pixels as our one and only coordinate system.
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Segment Length Demo — click to place points, drag to move")

        self.scene = Scene()
        self.selected: Optional[Point] = None   # first vertex of an in-progress segment pick
        self.dragging: Optional[Point] = None    # point currently being dragged, if any

        self.canvas = tk.Canvas(root, width=800, height=560, background="#fdfcf9")
        self.canvas.pack(fill="both", expand=True)

        info = tk.Label(
            root,
            text="Click empty space to add a point. Click two points in a row to "
                 "connect them. Drag a point to move it — the length updates live.",
            anchor="w", padx=8, pady=4,
        )
        info.pack(fill="x")

        # --- event wiring -----------------------------------------------
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        self.redraw()

    # ------------------------------------------------------------ events
    def on_mouse_down(self, event: tk.Event) -> None:
        x, y = event.x, event.y
        hit = self.scene.point_at(x, y)

        if hit is not None:
            # Clicked an existing vertex: either start dragging it, or --
            # if a different vertex was already selected -- complete the
            # pair into a new Segment.
            if self.selected is not None and self.selected is not hit:
                self.scene.add_segment(self.selected, hit)
                self.selected = None
            else:
                self.selected = hit
            self.dragging = hit
        else:
            # Clicked empty space: place a brand-new vertex there. If one
            # vertex was already selected, treat the new point as the
            # second vertex of a segment immediately.
            new_point = self.scene.add_point(x, y)
            if self.selected is not None:
                self.scene.add_segment(self.selected, new_point)
                self.selected = None
            else:
                self.selected = new_point
            self.dragging = new_point

        self.redraw()

    def on_mouse_drag(self, event: tk.Event) -> None:
        if self.dragging is None:
            return
        # Just mutate the Point's coordinates. Every Segment referencing
        # this Point will automatically compute its new length/midpoint
        # on the next redraw() -- there is no separate "update segment"
        # step to remember.
        self.dragging.x = event.x
        self.dragging.y = event.y
        self.redraw()

    def on_mouse_up(self, _event: tk.Event) -> None:
        self.dragging = None

    # ----------------------------------------------------------- drawing
    def redraw(self) -> None:
        self.canvas.delete("all")

        for seg in self.scene.segments:
            self._draw_segment(seg)
        for p in self.scene.points:
            self._draw_point(p)

    def _draw_point(self, p: Point) -> None:
        r = POINT_RADIUS
        fill = "#2a6df4" if p is self.selected else "#b3541e"
        self.canvas.create_oval(p.x - r, p.y - r, p.x + r, p.y + r,
                                 fill=fill, outline="#fdfcf9", width=2)
        self.canvas.create_text(p.x + 10, p.y - 10, text=p.label,
                                 fill="#1c2321", font=("Georgia", 12, "bold"))

    def _draw_segment(self, seg: Segment) -> None:
        self.canvas.create_line(seg.p1.x, seg.p1.y, seg.p2.x, seg.p2.y,
                                 fill="#1c2321", width=2)
        # Length label at the midpoint, recomputed from the endpoints'
        # CURRENT positions every time we get here -- this is what makes
        # it "dynamic": there is no stored length value to go stale.
        mx, my = seg.midpoint()
        length = seg.length()
        self.canvas.create_text(
            mx, my - 12, text=f"{length:.2f}",
            fill="#2f5d50", font=("Georgia", 11, "italic"),
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = GeometryApp(root)
    root.mainloop()
