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

QTABLE_PRIMARY = "qtable_primary"
MANHATTAN_PRIMARY = "manhattan_primary"

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


def _optimal_steps(state: tuple, move_set: list[str], role: str,
                   forbid=()) -> list[str]:
    """Every legal move that ties for the best resulting distance, in move-set order.

    Raises:
        ValueError: ``role`` is outside the engine's vocabulary.
    """
    if role not in _ROLE_CLOSES:
        raise ValueError(f"unknown role for the distance rule: {role!r}")
    relative, mask = state
    if relative is None:
        return []
    steps = []
    for action in move_set:
        # Excluded BEFORE the distance rule runs, never after: post-filtering
        # a chosen move would substitute one the rule never sanctioned.
        if action in forbid:
            continue
        delta = action_delta(parse_action(action))
        if not _is_blocked(delta, mask):
            steps.append((action, _resulting_distance(relative, delta)))
    if not steps:
        return []
    prefer = min if _ROLE_CLOSES[role] else max
    target = prefer(distance for _, distance in steps)
    return [action for action, distance in steps if distance == target]


def greedy_distance_action(state: tuple, move_set: list[str], role: str) -> str | None:
    """Return the legal move that best serves the role, or None if undecidable.

    Ties keep ``move_set`` order, matching ``best_action``'s documented
    tie-break. Returns None only when the opponent's cell is unobserved,
    which leaves no distance to be greedy about.
    """
    optimal = _optimal_steps(state, move_set, role)
    return optimal[0] if optimal else None


def manhattan_primary_action(
    state: tuple, move_set: list[str], role: str, q_value, forbid=()
) -> str | None:
    """Distance decides; the learned table chooses among equally-good moves.

    Both strategies stay live on every decision. The distance rule narrows the
    legal moves to the distance-optimal set -- which a learned value can never
    escape, however large -- and the table ranks what is left. ``max`` returns
    the first maximum, so a flat tie still resolves in ``move_set`` order.
    """
    optimal = _optimal_steps(state, move_set, role, forbid)
    if not optimal:
        return None
    return max(optimal, key=lambda action: q_value(state, action))


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


def policy_action(values, state: tuple, forbid=()) -> str | None:
    """Resolve one decision for a table's configured ``policy_mode``.

    Returns None to defer to ``best_action``'s plain greedy read -- which is
    what a role-less table and an unobserved opponent both do.

    Takes the ``QValues`` instance rather than its parts deliberately:
    ``strategy/qvalues.py`` sits on the project's 150-line limit, so this
    dispatch is allowed to cost it exactly one line and no more.

    Raises:
        ValueError: ``policy_mode`` is not a mode this module implements.
    """
    if values.role is None:
        return None
    move_set = values.config.move_set
    mode = values.settings.policy_mode
    if mode == MANHATTAN_PRIMARY:
        return manhattan_primary_action(state, move_set, values.role,
                                        values.q_value, forbid)
    if mode != QTABLE_PRIMARY:
        raise ValueError(f"unknown policy_mode: {mode!r}")
    allowed = [action for action in move_set if action not in forbid]
    return tiebreak_action(state, allowed or move_set, values.role,
                           values.q_value)
