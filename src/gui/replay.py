"""Tkinter Replay Viewer: step a verified match and stamp the verdict.

The verdict comes from the SAME verifier the headless CLI uses, so the badge
cannot say one thing while `scripts.replay_match` says another. Frames are
replayed from the logged MOVES rather than read from the recorded positions,
so a forged log is drawn as it truly reconstructs, not as its author intended.
"""

import argparse
import json
import tkinter as tk

from engine.config import load_config
from gui.board_canvas import BoardCanvas
from gui.palette import badge
from mcp_server.peer_keys import load_public_keys
from scripts.render_replay import replay_frames
from scripts.replay_match import verify_log

_TITLE = "zero-trust-cop — Replay Viewer"
_BADGE_FONT = ("TkDefaultFont", 18, "bold")


class ReplayViewer(tk.Frame):
    """Board, verdict badge, and per-turn stepping for one match log."""

    def __init__(self, master, log, config, public_keys):
        super().__init__(master, padx=12, pady=12, background="#ffffff")
        self.frames = list(replay_frames(log, config, public_keys))
        self.report = verify_log(log, config, public_keys)
        self.index = 0

        text, colour = badge(self.report.ok)
        self.badge = tk.Label(self, text=text, fg="#ffffff", bg=colour,
                              font=_BADGE_FONT, padx=16, pady=6)
        self.badge.pack(fill="x")
        self.caption = tk.Label(self, background="#ffffff", pady=6)
        self.caption.pack(fill="x")
        self.canvas = BoardCanvas(self, config.grid_size)
        self.canvas.pack()

        controls = tk.Frame(self, background="#ffffff", pady=8)
        controls.pack(fill="x")
        tk.Button(controls, text="◀ Prev", command=self.previous).pack(side="left")
        tk.Button(controls, text="Next ▶", command=self.next).pack(side="right")
        self.show()

    def show(self) -> None:
        """Paint the current frame and describe its turn."""
        frame = self.frames[self.index]
        self.canvas.draw(frame.scent, frame.cop, frame.thief, frame.barriers)
        marks = {r: c["commitment"] and c["signature"] for r, c in frame.checks.items()}
        self.caption.configure(
            text=(f"Turn {frame.turn + 1}/{len(self.frames)}   "
                  f"police {frame.moves['police']}/{frame.intents['police']}   "
                  f"thief {frame.moves['thief']}/{frame.intents['thief']}   "
                  f"verified: {marks}")
        )

    def next(self) -> None:
        self.index = min(self.index + 1, len(self.frames) - 1)
        self.show()

    def previous(self) -> None:
        self.index = max(self.index - 1, 0)
        self.show()


def build(master, log_path, config_path="config/game.json", own_role="police"):
    """Construct a viewer for a log on disk."""
    with open(log_path) as handle:
        log = json.load(handle)
    return ReplayViewer(master, log, load_config(config_path),
                        load_public_keys(own_role))


def main(argv=None):
    """Open the replay window."""
    parser = argparse.ArgumentParser(description=_TITLE)
    parser.add_argument("log_path")
    parser.add_argument("--config", default="config/game.json")
    parser.add_argument("--own-role", default="police")
    args = parser.parse_args(argv)

    root = tk.Tk()
    root.title(_TITLE)
    build(root, args.log_path, args.config, args.own_role).pack()
    root.mainloop()


if __name__ == "__main__":
    main()
