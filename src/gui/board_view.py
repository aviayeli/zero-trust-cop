"""Single entry point for the two Tkinter windows.

Reference-compatible alias layer: the drawing logic stays in
``board_canvas.py``, the colour rules in ``palette.py``, and the windows in
``live_heatmap.py`` and ``replay.py``. This module re-exports them so a caller
needs one import, and adds a ``--view`` launcher so both windows are reachable
from one command.

It deliberately owns no behaviour of its own — anything added here would be
logic living outside the modules the tests target.
"""

import argparse
import tkinter as tk

from gui.board_canvas import CELL, BoardCanvas
from gui.live_heatmap import DEFAULT_INTERVAL_MS, LiveHeatmap
from gui.live_heatmap import build as build_heatmap
from gui.palette import badge, heat_colour
from gui.replay import ReplayViewer
from gui.replay import build as build_replay

__all__ = [
    "BoardCanvas",
    "CELL",
    "DEFAULT_INTERVAL_MS",
    "LiveHeatmap",
    "ReplayViewer",
    "badge",
    "build_heatmap",
    "build_replay",
    "heat_colour",
    "main",
]

_VIEWS = {"heatmap": build_heatmap, "replay": build_replay}
_TITLES = {
    "heatmap": "zero-trust-cop — Live Belief Heatmap",
    "replay": "zero-trust-cop — Replay Viewer",
}


def main(argv=None):
    """Open either window: ``--view heatmap`` or ``--view replay``."""
    parser = argparse.ArgumentParser(description="Board views for a match log.")
    parser.add_argument("log_path")
    parser.add_argument("--view", choices=sorted(_VIEWS), default="replay")
    parser.add_argument("--config", default="config/game.json")
    parser.add_argument("--own-role", default="police")
    args = parser.parse_args(argv)

    root = tk.Tk()
    root.title(_TITLES[args.view])
    view = _VIEWS[args.view](root, args.log_path, args.config, args.own_role)
    view.pack()
    if args.view == "heatmap":
        root.after(view.interval_ms, view.play)
    root.mainloop()


if __name__ == "__main__":
    main()
