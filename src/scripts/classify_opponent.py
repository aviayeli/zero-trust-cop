"""Classify an opponent from its reported scent grid (SPEC 6, PRD_20).

Grids appear only after a sub-game closes (at turn 35); there is no
partially-written log to tail mid-match. This classifier reads sealed logs
and reconstructs the opponent's strategy from the single channel available:
the transmitted argmax cells. A bluffer is indistinguishable from an honest
corner-hider on the grid alone; only refutation by standing on a non-captured
cell elevates CORNER_PARKED to BLUFFER. The three baseline classes come from
the grid; the fourth comes only from empirical refutation (the thaw's signal).
"""

from __future__ import annotations

import argparse
import json

from engine.config import load_config
from mcp_server.smell_reader import strongest_cell

RANDOM = "RANDOM"
STATIC = "STATIC"
CORNER_PARKED = "CORNER_PARKED"
BLUFFER = "BLUFFER"


def classify(grids: list, size: int):
    """Classify opponent behavior from a list of smell grids.

    Extracting argmax cells from each grid, returning the classification
    or None if fewer than three usable grids survive. An unreadable grid
    (one where strongest_cell yields None) is skipped without terminating.
    """
    argmax_cells = []
    for grid in grids:
        cell = strongest_cell(grid)
        if cell is not None:
            argmax_cells.append(cell)

    if len(argmax_cells) < 3:
        return None

    # Check if all argmax cells are the same
    first_cell = argmax_cells[0]
    if all(cell == first_cell for cell in argmax_cells):
        # Check if it's a corner
        r, c = first_cell
        corners = {(0, 0), (0, size - 1), (size - 1, 0), (size - 1, size - 1)}
        if first_cell in corners:
            return CORNER_PARKED
        else:
            return STATIC

    return RANDOM


def refute(verdict, standing_on_belief: bool, captured: bool):
    """Upgrade a verdict based on empirical refutation.

    Standing on the believed cell with no capture to claim proves the
    opponent is elsewhere. This refutes CORNER_PARKED only when both
    conditions hold (standing AND not captured); all other verdicts and
    combinations pass through unchanged.
    """
    if verdict == CORNER_PARKED and standing_on_belief and not captured:
        return BLUFFER
    return verdict


def warning(verdict):
    """Render a classification as an ANSI-colored single-line warning.

    Returns the empty string for None (no classification), or a colored
    string containing the verdict name in UPPERCASE.
    """
    if verdict is None:
        return ""

    # ANSI colors: bright yellow for the banner, default at end
    color_code = "\033[1;33m"
    reset_code = "\033[0m"
    return f"{color_code}[TACTICAL WARNING] {verdict}{reset_code}"


def main(argv=None):
    """Read a sub-game log and print the opponent classification.

    Loads turns[].theirs.smell_grid from the JSON, classifies, and prints
    the warning (or nothing if no verdict).
    """
    parser = argparse.ArgumentParser(
        description="Classify opponent from sealed sub-game log"
    )
    parser.add_argument("log_path", help="Path to completed sub-game log JSON")
    parser.add_argument("--config", default="config/game.json",
                        help="the agreed contract the board size comes from")
    args = parser.parse_args(argv)

    with open(args.log_path) as f:
        log = json.load(f)

    grids = []
    for turn in log.get("turns", []):
        theirs = turn.get("theirs", {})
        smell_grid = theirs.get("smell_grid")
        if smell_grid is not None:
            grids.append(smell_grid)

    # From the CONTRACT, never a literal: a sub-game log carries no config
    # block, so the fallback was unconditional and 7 was a hardcoded tunable.
    verdict = classify(grids, load_config(args.config).grid_size)
    warning_text = warning(verdict)
    if warning_text:
        print(warning_text)


if __name__ == "__main__":
    main()
