"""Reading an inbound scent grid (SPEC 5).

Split from ``smell_trail`` at the emit/absorb seam: that module builds the
trail we transmit, this one interprets the one we receive. They are separate
directions of the same protocol and only this half has to tolerate another
team's serialiser.
"""

from __future__ import annotations


def strongest_cell(grid: dict):
    """The cell an inbound grid points hardest at, or None.

    Ties break LEXICOGRAPHICALLY by (row, col), matching the kit's
    ``hottest``. Falling back to iteration order would be deterministic for us
    and different for them -- the kind of divergence that surfaces only as two
    peers disagreeing about a replay neither can debug.

    Their grid is THEIR serialiser's output, so a key we cannot parse is
    SKIPPED rather than raised on: a malformed cell is a reason to learn
    nothing from it, never a reason to end a live match.
    """
    best, best_value = None, None
    for cell, value in (grid or {}).items():
        parsed = _parse_cell(cell)
        if parsed is None or isinstance(value, bool):
            continue
        if not isinstance(value, (int, float)):
            continue
        if best_value is None or value > best_value or (
            value == best_value and parsed < best
        ):
            best, best_value = parsed, value
    return best


def _parse_cell(cell):
    """``'3,4'`` -> ``(3, 4)``, or None for anything else."""
    if not isinstance(cell, str) or cell.count(",") != 1:
        return None
    row, _, col = cell.partition(",")
    try:
        return (int(row), int(col))
    except ValueError:
        return None
