"""Four thieves to measure the thawed cop against (PRD_19 FR2).

A profile is two decisions, and the second is the one that matters here: how
it MOVES, and what grid it TRANSMITS. Those come apart, because the smell grid
is a self-report -- an unverified, costless signal -- and nothing on the wire
binds it to where the sender actually is.

Profile C is the reason this module exists. It moves to evade and transmits a
grid whose argmax never leaves a corner, which is what bb-ai-12's traffic
actually did for eighteen turns in the graded series. It is not an accusation
of intent; the behaviour froze our cop whether or not it was deliberate, and a
benchmark that omitted it would measure the thaw against nothing.
"""

from __future__ import annotations

from engine.actions import action_delta, parse_action

_MOVES = ("N", "S", "E", "W", "STAY")


def _legal(board, cell, move) -> tuple:
    """Where ``move`` lands from ``cell``, or ``cell`` if it is refused."""
    delta = action_delta(parse_action(move))
    landing = (cell[0] + delta[0], cell[1] + delta[1])
    if not board.in_bounds(landing) or board.is_barrier(landing):
        return cell
    return landing


def _away(board, cell, cop) -> str:
    """The legal move maximising Manhattan distance from the cop."""
    best, far = "STAY", -1
    for move in _MOVES:
        landing = _legal(board, cell, move)
        gap = abs(landing[0] - cop[0]) + abs(landing[1] - cop[1])
        if gap > far:
            best, far = move, gap
    return best


def random_walker(board, cell, cop, rng, size):
    """A: moves at random, reports honestly."""
    return _legal(board, cell, rng.choice(_MOVES)), None


def greedy_evader(board, cell, cop, rng, size):
    """B: maximises distance every step, reports honestly."""
    return _legal(board, cell, _away(board, cell, cop)), None


def deceptive_bluffer(board, cell, cop, rng, size):
    """C: evades, and pins its transmitted argmax to a fixed corner.

    The returned second value OVERRIDES the cell the grid is built around, so
    the transmitted trail says "I am at the corner" while the piece is
    elsewhere. That is the exploit: a cop minimising distance to the argmax
    walks to the corner, stands on its own belief, and -- before PRD_18 --
    stayed there.
    """
    return _legal(board, cell, _away(board, cell, cop)), (size - 1, size - 1)


def corner_hider(board, cell, cop, rng, size):
    """D: runs to a corner and sits, reporting honestly.

    Honest and still awkward: an argmax that never moves looks exactly like
    profile C's lie, so this is the control that says whether the thaw
    punishes truthfulness.
    """
    corner = (size - 1, size - 1)
    if cell == corner:
        return cell, None
    row = cell[0] + (1 if cell[0] < corner[0] else 0)
    if row != cell[0]:
        return _legal(board, cell, "S"), None
    return _legal(board, cell, "E"), None


PROFILES = {
    "A_random": random_walker,
    "B_greedy": greedy_evader,
    "C_bluffer": deceptive_bluffer,
    "D_corner": corner_hider,
}
