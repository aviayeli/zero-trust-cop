"""Greedy Manhattan tie-break for states the Q-table has never visited.

Self-play converges hard onto its own trajectory distribution. Off that
manifold every action reads ``initial_q_value``, so ``best_action``'s
move-set tie order degenerated into "always ``move_set[0]``" -- a fixed
compass heading, played against an opponent it has no values for.

The state key already carries the opponent's cell RELATIVE to our own
(``strategy/qvalues.py``), so the resulting distance of each candidate step
is arithmetic on the key alone: no new observation, no wider state space, and
nothing learned is touched. The barrier mask in that same key is what keeps
the choice legal, which is why this module -- not ``qvalues`` -- owns the
mask's bit order: the writer and the reader must not be able to drift apart.

Applied only when EVERY action on the state is exactly flat. One learned
value, positive or negative, means the state is on-manifold and the table
speaks for itself.
"""

from engine.actions import action_delta, parse_action

BARRIER_BIT_DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))

_FLAT = 0.0
# True where the role wants the gap CLOSED: the cop pursues, the thief flees.
_ROLE_CLOSES = {"cop": True, "thief": False}


def _is_blocked(delta: tuple[int, int], mask: int) -> bool:
    """Read this step's availability off the state key's barrier mask.

    STAY has no neighbour bit and is always legal; the engine treats a
    barrier and the board edge alike, and so does the mask.
    """
    if delta == (0, 0):
        return False
    return bool(mask >> BARRIER_BIT_DIRECTIONS.index(delta) & 1)


def _resulting_distance(relative: tuple[int, int], delta: tuple[int, int]) -> int:
    """Manhattan distance to the opponent AFTER taking this step.

    Moving by ``delta`` shifts us, so the opponent's relative cell shifts by
    the negation: ``relative - delta``.
    """
    return abs(relative[0] - delta[0]) + abs(relative[1] - delta[1])


def greedy_distance_action(state: tuple, move_set: list[str], role: str) -> str | None:
    """Return the legal move that best serves the role, or None if undecidable.

    Ties keep ``move_set`` order, matching ``best_action``'s documented
    tie-break. Returns None only when the opponent's cell is unobserved,
    which leaves no distance to be greedy about.

    Raises:
        ValueError: ``role`` is outside the engine's vocabulary.
    """
    if role not in _ROLE_CLOSES:
        raise ValueError(f"unknown role for the distance fallback: {role!r}")
    relative, mask = state
    if relative is None:
        return None

    closes = _ROLE_CLOSES[role]
    chosen: str | None = None
    chosen_distance = 0
    for action in move_set:
        delta = action_delta(parse_action(action))
        if _is_blocked(delta, mask):
            continue
        distance = _resulting_distance(relative, delta)
        better = distance < chosen_distance if closes else distance > chosen_distance
        if chosen is None or better:
            chosen, chosen_distance = action, distance
    return chosen


def tiebreak_action(state: tuple, move_set: list[str], role, q_value) -> str | None:
    """Return the fallback move for a role-bearing, wholly unlearned state.

    ``role`` of None disables the fallback outright, so a table built without
    one behaves exactly as it did before this module existed.
    """
    if role is None:
        return None
    if any(q_value(state, action) != _FLAT for action in move_set):
        return None
    return greedy_distance_action(state, move_set, role)
