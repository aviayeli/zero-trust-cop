"""The two capture families only the hidden side can see (SPEC 3.1).

Split from ``claims_side`` at the 150-line limit; the seam is the subject.
That module is our piece and what it discloses. This is the barrier record
that piece keeps, and the two endings it produces.

A capture settles three ways in this league and we encoded ONE. The other two
are rule 46 -- a barrier placed on the thief's own cell -- and rule 47, the
thief boxed in with every ORTHOGONAL neighbour a barrier or off the board.
Both are properties of our own hidden position, so the opponent cannot infer
them and the SPEC requires them to be SAID.

Silence does not merely lose a point. We would settle CAPTURE from knowledge
they lack while they, having learned nothing, wait out their budget and
settle TIMEOUT -- two honest peers describing one sub-game two ways, which is
the contradictory-report shape App. E rule 35 ZEROES. Conceding is how BOTH
sides score at all.

Live, not theoretical: rstabcde's cop places barriers as core strategy, nine
placements per game in their last counted series, and we ignored the field.
"""

from __future__ import annotations

# Rule 47 is about MOVEMENT, so it reads the four ORTHOGONAL neighbours. A
# diagonal is not a move on this board and must not rescue a boxed-in thief.
ORTHOGONAL = ((-1, 0), (1, 0), (0, -1), (0, 1))


class BarrierRecord:
    """Barriers the OPPONENT has placed, and what they settle.

    Ours is the only record that counts: SPEC 5 keeps positions hidden, so
    there is no shared board frame either side reproduces, and a concession
    is corroborated at audit against the COP's own record -- never against
    the list the thief reports.
    """

    def __init__(self, board):
        self._board = board
        self._cells: set = set()

    def __contains__(self, cell) -> bool:
        return tuple(cell) in self._cells

    def place(self, value) -> bool:
        """Record a barrier; return whether it captures us where we stand.

        A cell we cannot parse is IGNORED: it comes from their serialiser,
        and a malformed one is a reason to learn nothing from it, never a
        reason to end a live match.
        """
        cell = self._cell(value)
        if cell is None:
            return False
        self._cells.add(cell)
        return True

    def captures(self, position: tuple) -> bool:
        """Rule 46 (a barrier on our cell) or rule 47 (no legal move out)."""
        return tuple(position) in self._cells or self._boxed_in(position)

    def _boxed_in(self, position: tuple) -> bool:
        """Every orthogonal neighbour a barrier or off the board."""
        row, col = position
        for delta_row, delta_col in ORTHOGONAL:
            cell = (row + delta_row, col + delta_col)
            if not self._board.in_bounds(cell):
                continue
            if cell in self._cells or self._board.is_barrier(cell):
                continue
            return False
        return True

    def _cell(self, value):
        """``[r, c]`` on this board, or None."""
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return None
        if not all(isinstance(n, int) and not isinstance(n, bool) for n in value):
            return None
        cell = (value[0], value[1])
        return cell if self._board.in_bounds(cell) else None
