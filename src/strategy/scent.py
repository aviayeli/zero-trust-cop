"""Break a distance tie on belief mass instead of an off-manifold table.

`manhattan_primary_action` narrows to the distance-optimal moves and lets the
learned table rank what is left. That table was trained against TRUE opponent
positions and is executed against a lagging belief estimate, so on this wire
its ranking answers a question about a state distribution it never saw. Among
moves the distance rule already calls equal, it is close to arbitrary.

This ranks them by the belief mass ADJACENT to where each lands. The mass is
our belief about THEM -- the field is fed from the opponent's transmitted grid
-- so "most adjacent mass" means "closest to where we think they are". That is
the right direction for a pursuer and would be exactly backwards for an evader,
which is why nothing here is offered to the thief.

Summed over neighbours rather than read off one cell on purpose: reading a
single cell would just be the argmax again, and the argmax is the very
estimate PRD_18 showed can be stale. A sum over the neighbourhood prefers a
region the belief actually favours over a single lucky peak.

Ties within the ranking keep the caller's order, so the decision stays
deterministic and a replay reproduces it.
"""

from __future__ import annotations

from engine.actions import action_delta, parse_action

_NEIGHBOURS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def _landing(cell, move: str) -> tuple:
    """Where ``move`` puts us, ignoring legality -- the caller already filtered."""
    delta = action_delta(parse_action(move))
    return (cell[0] + delta[0], cell[1] + delta[1])


def _mass(field: dict, cell, size: int) -> float:
    """Belief mass on the cells adjacent to ``cell``, on-board only.

    Off-board neighbours are not counted. Crediting them as zero is right;
    counting them at all would let an edge or a corner win by having fewer
    competitors, which is a bias toward exactly the cells a stale belief
    already over-favours.
    """
    total = 0.0
    for step in _NEIGHBOURS:
        neighbour = (cell[0] + step[0], cell[1] + step[1])
        if 0 <= neighbour[0] < size and 0 <= neighbour[1] < size:
            total += field.get(neighbour, 0.0)
    return total


def densest(position, candidates, field: dict, size: int):
    """The candidate landing beside the most believed mass, or None.

    Returns the caller's first candidate when the field is empty or flat: no
    information means no opinion, and overriding a deterministic order on a
    tie of zeros would make a replay irreproducible for nothing.
    """
    if not candidates:
        return None
    if not field:
        return candidates[0]

    scored = [(_mass(field, _landing(position, move), size), index, move)
              for index, move in enumerate(candidates)]
    best = max(score for score, _, _ in scored)
    if best <= 0.0:
        return candidates[0]
    # `min` on (index) keeps the caller's order among equals.
    return min((entry for entry in scored if entry[0] == best),
               key=lambda entry: entry[1])[2]
