"""What an operator sees while a live series runs.

Split from ``reference_run`` at the 150-line limit, on a real seam: that
module wires a run together, this decides what reaches the console while it
happens. Nothing here changes what is played -- every function is a
diagnostic, and a run behaves identically without them.

Everything prints with ``flush=True``, matching the ``-u`` the entry point is
run with. A live series that buffers its own side prints nothing until it
ends, which for a series that never ends is nothing at all -- four aborted
runs were argued from the opponent's inbound traffic alone for exactly that
reason.
"""

from __future__ import annotations


def progress(entry: dict) -> None:
    """One line per half-turn we pushed, and how long theirs took to land."""
    print(f"  step {entry['step']:>2} pushed {entry['move']} "
          f"| theirs +{entry['theirs']}s", flush=True)


def stalled(entry: dict) -> None:
    """A wait going nowhere, said out loud (PRD_12 FR6).

    ``inbox_depth`` 0 is "they never reached us"; non-zero is "they did and we
    are not matching it". Nothing distinguished those two, and it cost a day
    against bb-ai-12 on 2026-08-25.
    """
    print(f"  WAITING on their step {entry['step']} "
          f"(re-pushed {entry['attempt']}x) | our inbox: "
          f"{entry['inbox_depth']} msg, steps={entry['inbox_steps']}, "
          f"senders={entry['senders']}", flush=True)


def paused(seconds: float) -> None:
    """The window a per-sub-game-relaunching opponent is being given."""
    print(f"  PAUSE {seconds:g}s -- window for the opponent to relaunch "
          f"(their sessions released)", flush=True)


def saved(path: str) -> None:
    """A sub-game banked before the next one can go wrong."""
    print(f"  saved {path}", flush=True)
