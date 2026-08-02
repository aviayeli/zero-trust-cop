"""Tkinter Live GUI: the belief heatmap as the match advances.

Shows what a peer BELIEVES rather than what it is told: each cell is shaded
in red proportional to its pheromone concentration, which decays every turn,
so the thief's trail visibly builds and fades. Auto-advances on a timer,
which is what makes it "live" as opposed to the step-by-step replay viewer.

The field is a CONCENTRATION, not a normalised probability: overlapping
kernels can push a cell above 1.0 (observed peak 2.41 on a real match), so
the shading clamps rather than claiming a probability it does not compute.
"""

import argparse
import json
import tkinter as tk

from engine.config import load_config
from gui.board_canvas import BoardCanvas
from mcp_server.peer_keys import load_public_keys
from scripts.render_replay import replay_frames

_TITLE = "zero-trust-cop — Live Belief Heatmap"
_CAPTION_FONT = ("TkDefaultFont", 12)
DEFAULT_INTERVAL_MS = 700


class LiveHeatmap(tk.Frame):
    """Auto-advancing belief view over a match's frames."""

    def __init__(self, master, log, config, public_keys,
                 interval_ms: int = DEFAULT_INTERVAL_MS):
        super().__init__(master, padx=12, pady=12, background="#ffffff")
        self.frames = list(replay_frames(log, config, public_keys))
        self.interval_ms = interval_ms
        self.index = 0

        tk.Label(self, text="Belief heatmap — red intensity ∝ pheromone concentration",
                 font=_CAPTION_FONT, background="#ffffff").pack(fill="x")
        self.canvas = BoardCanvas(self, config.grid_size)
        self.canvas.pack(pady=6)
        self.caption = tk.Label(self, background="#ffffff", font=_CAPTION_FONT)
        self.caption.pack(fill="x")
        self.show()

    def show(self) -> None:
        """Paint the current belief field."""
        frame = self.frames[self.index]
        self.canvas.draw(frame.scent, frame.cop, frame.thief, frame.barriers)
        strongest = max(frame.scent.values(), default=0.0)
        self.caption.configure(
            text=(f"turn {frame.turn + 1}/{len(self.frames)}   "
                  f"traced cells {len(frame.scent)}   "
                  f"peak belief {strongest:.2f}")
        )

    def advance(self) -> bool:
        """Step one turn. False once the last frame is reached."""
        if self.index >= len(self.frames) - 1:
            return False
        self.index += 1
        self.show()
        return True

    def play(self) -> None:
        """Advance on the timer until the match ends."""
        if self.advance():
            self.after(self.interval_ms, self.play)


def build(master, log_path, config_path="config/game.json", own_role="police"):
    """Construct a live heatmap for a log on disk."""
    with open(log_path) as handle:
        log = json.load(handle)
    return LiveHeatmap(master, log, load_config(config_path),
                       load_public_keys(own_role))


def main(argv=None):
    """Open the live heatmap window."""
    parser = argparse.ArgumentParser(description=_TITLE)
    parser.add_argument("log_path")
    parser.add_argument("--config", default="config/game.json")
    parser.add_argument("--own-role", default="police")
    args = parser.parse_args(argv)

    root = tk.Tk()
    root.title(_TITLE)
    view = build(root, args.log_path, args.config, args.own_role)
    view.pack()
    root.after(view.interval_ms, view.play)
    root.mainloop()


if __name__ == "__main__":
    main()
