"""Stop the cop resting on a belief it has already refuted (PRD_18).

In three graded cop sub-games ours emitted ``MOVE:STAY`` for exactly 16
consecutive turns each -- 55 of 105 cop turns -- and never captured. The
sealed logs give the mechanism without inference: the opponent's transmitted
argmax parked at (6,6) for ~18 turns, we chased it, we ARRIVED on it, the
believed cell became our own, ``relative == (0,0)`` made ``STAY`` the only
distance-optimal move, and ``STAY`` kept us there.

The learned table cannot rescue that. ``manhattan_primary_action`` lets it
rank only WITHIN the distance-optimal set, and that set was ``{STAY}``.

THE REFUTATION. Capture on this wire is settled by claim and honest answer, so
a cop standing on the thief's cell would have a capture to claim. Standing
there with none is proof the thief is elsewhere -- empirical, needing no model
of their honesty and no extra message. It is the strongest signal available on
a wire that carries no positions.

Only the COP is filtered. Standing still is legitimate evasion for an evader,
and the thief is not the side being lured onto a fake target. The consecutive
bound applies to both, as a floor under any belief failure we have not
foreseen.

This constrains WHICH moves the trained policy may choose from. It changes no
Q-value, retrains nothing, and leaves every other decision untouched.
"""

from __future__ import annotations

STAY = "STAY"
_COP = "cop"


class Thaw:
    """Which moves this sub-game forbids, and why.

    One instance per sub-game: the visited set and the STAY run are both
    per-sub-game state, and carrying either across a boundary would judge a
    new board by an old walk.
    """

    def __init__(self, role: str, max_consecutive_stay: int):
        self.role = role
        self.max_consecutive_stay = max_consecutive_stay
        self._stays = 0
        self._visited: set = set()

    def forbid(self, position, belief) -> frozenset:
        """Moves the policy may not choose from this step.

        ``position`` is where we stand, ``belief`` the cell we think holds the
        opponent -- ``None`` when nothing has been observed yet, which forbids
        nothing because there is no belief to refute.
        """
        if self._refuted(position, belief) or self._stalled():
            return frozenset({STAY})
        return frozenset()

    def _refuted(self, position, belief) -> bool:
        """We are standing on the target and have no capture to claim."""
        return (self.role == _COP and belief is not None
                and tuple(belief) == tuple(position))

    def _stalled(self) -> bool:
        return self._stays >= self.max_consecutive_stay

    def took(self, move: str, position=None) -> None:
        """Record the move actually played, and where it left us."""
        self._stays = self._stays + 1 if move == STAY else 0
        if position is not None:
            self._visited.add(tuple(position))

    def unvisited(self, cell) -> bool:
        """Have we not stood here this sub-game?

        A random walk re-treads; preferring somewhere new turns the thaw into
        a sweep, and it stays deterministic and replayable.
        """
        return tuple(cell) not in self._visited
