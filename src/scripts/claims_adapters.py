"""Our policy and our belief, adapted to the reference-v3 loop.

Split from ``claims_runner`` at the 150-line limit, on a real seam: that module
sequences a SERIES -- handshakes, boundaries, artifacts -- while these two are
the per-step adapters between the loop and this peer's brain.

Both exist because of what this wire withholds. It carries no opponent
position, so ``_chooser`` passes None and lets the policy fall back to its
pheromone field; and it carries their SMELL rather than their words, so
``_observer`` feeds that trail in and nothing tries to read a move out of a
fifteen-word hint.
"""

from __future__ import annotations

from mcp_server.directions import LIE, TRUTH, encode, token_for_claim
from mcp_server.smell_trail import strongest_cell


def _chooser(app, side, rng, board, thaw):
    """``(step) -> (move, hint, intent)`` from this peer's own policy.

    The opponent's position is passed as None on purpose: we do not know it on
    this wire, and ``state_key`` resolves the hybrid itself -- falling back to
    the pheromone field, the only thing here with an opinion. ``thaw`` refuses
    moves belief has already refuted (PRD_18): standing on our own believed
    target with no capture to claim proves it is elsewhere.
    """
    def choose(step):
        state_key = app.policy.state_key(side.position, None, board)
        belief = app.policy.pheromones.strongest()
        forbid = thaw.forbid(position=side.position, belief=belief)
        token, hint = app.policy.decide(state_key, rng, forbid)
        thaw.took(token, position=side.position)
        claimed = token_for_claim(app.policy.intent_for_move(token))
        return encode(token), hint, TRUTH if claimed == token else LIE

    return choose


def _observer(app):
    """Feed THEIR smell trail into our belief; ignore an unreadable grid."""
    def observe(turn):
        cell = strongest_cell(turn.get("smell_grid") or {})
        app.policy.pheromones.advance(deposits=[cell] if cell else [])

    return observe


