"""A Tk canvas that paints one board frame: heatmap, agents, barriers.

Widget construction is separated from the colour rules in palette.py so the
rules stay testable headless; this module is the thin part that needs a
display.
"""

import tkinter as tk

from gui.palette import (
    BARRIER_COLOUR,
    CAPTURE_COLOUR,
    COP_COLOUR,
    THIEF_COLOUR,
    heat_colour,
)

CELL = 54
_LABEL = ("TkDefaultFont", 13, "bold")


class BoardCanvas(tk.Canvas):
    """Draws a grid whose cell shade is the belief probability for that cell."""

    def __init__(self, master, grid_size: int, cell: int = CELL):
        super().__init__(
            master, width=grid_size * cell, height=grid_size * cell,
            highlightthickness=0, background="#ffffff",
        )
        self._grid_size = grid_size
        self._cell = cell

    def draw(self, scent, cop=None, thief=None, barriers=frozenset()) -> None:
        """Repaint every cell from the current belief field and positions."""
        self.delete("all")
        for row in range(self._grid_size):
            for col in range(self._grid_size):
                self._draw_cell((row, col), scent, barriers)
        if cop is not None and cop == thief:
            self._stamp(cop, "X", CAPTURE_COLOUR)
            return
        if cop is not None:
            self._stamp(cop, "C", COP_COLOUR)
        if thief is not None:
            self._stamp(thief, "T", THIEF_COLOUR)

    def _draw_cell(self, cell, scent, barriers) -> None:
        row, col = cell
        left, top = col * self._cell, row * self._cell
        colour = BARRIER_COLOUR if cell in barriers else heat_colour(
            scent.get(cell, 0.0)
        )
        self.create_rectangle(
            left, top, left + self._cell, top + self._cell,
            fill=colour, outline="#cfd8dc",
        )

    def _stamp(self, cell, letter: str, colour: str) -> None:
        row, col = cell
        centre = (col * self._cell + self._cell / 2, row * self._cell + self._cell / 2)
        self.create_oval(
            centre[0] - 18, centre[1] - 18, centre[0] + 18, centre[1] + 18,
            fill=colour, outline="",
        )
        self.create_text(*centre, text=letter, fill="#ffffff", font=_LABEL)
