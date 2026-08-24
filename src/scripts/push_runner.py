"""Hand the push loop our policy, our engine, and the opponent's store.

``push_match_loop`` knows the protocol; it does not know how WE pick a move or
resolve a turn. This module is that glue, and it was the piece missing while
the handshake succeeded and no move ever crossed: the loop existed, tested,
with nothing wiring it to a live peer.

The opponent's pushes land in ``app.push``, which lives inside the SERVER.
That is why a series runs in the same process as the peer it plays through --
a runner in another process could complete a handshake and then wait forever
for a store it cannot see.
"""

from __future__ import annotations

from random import Random

from engine.barriers import populated_board
from mcp_server.directions import LIE, TRUTH, decode, encode, token_for_claim

# The engine names the sides cop/thief; the wire names the peers police/thief.
_OPPONENT = {"cop": "thief", "thief": "cop"}


def _chooser(app, rng, board):
    """``(step) -> (move, hint, intent)`` from this peer's own policy.

    The hint is the policy's own truncated line and may be a lie -- ``intent``
    says which, and the two are chosen together so a deceptive hint is
    declared rather than smuggled.
    """
    def choose(step):
        own, other = _positions(app)
        state_key = app.policy.state_key(own, other, board)
        token, hint = app.policy.decide(state_key, rng)
        claimed = token_for_claim(app.policy.intent_for_move(token))
        intent = TRUTH if claimed == token else LIE
        return encode(token), hint, intent

    return choose


def _positions(app):
    """Our position first, then theirs, in the engine's vocabulary."""
    cop, thief = app.match_state.cop_position, app.match_state.thief_position
    return (cop, thief) if app.own_role == "cop" else (thief, cop)


def _advancer(app):
    """``(step, ours, theirs) -> dict`` -- one engine step, both moves in.

    Async because ``MatchState.submit`` resolves the turn behind an
    asyncio.Lock: exactly one engine step per turn, however the two
    submissions interleave (FR8).
    """
    async def advance(step, our_move, their_move):
        await app.match_state.submit(app.own_role, decode(our_move))
        await app.match_state.submit(_OPPONENT[app.own_role], decode(their_move))
        return {
            "terminated": app.match_state.is_terminated,
            "terminal_reason": app.match_state.terminal_reason(),
        }

    return advance


def _reset(app) -> None:
    """Start the next sub-game on a clean board and an empty inbox.

    Carrying their step 1 across a boundary would let a stale commit satisfy
    a step we never played.
    """
    app.match_state.reset()
    store = app.push
    store.commits.clear()
    store.reveals.clear()
    store.acks.clear()
    store.claims.clear()
    store.nonces.clear()


async def play_series(app, client, sub_games: int, seed: int, wait,
                      max_steps=None, max_polls=None) -> list:
    """Play ``sub_games`` sub-games through ``client`` and return a summary each.

    ``seed`` drives the policy's RNG, so a series replays move for move.
    """
    from scripts.push_match_loop import play_sub_game

    rng = Random(seed)
    # Both peers derive the identical layout from the contract's barrier_seed,
    # so the board needs no wire message (PLAN.md §4.3).
    board = populated_board(app.config)
    steps = max_steps if max_steps is not None else app.config.max_moves
    summaries = []

    for index in range(1, sub_games + 1):
        if index > 1:
            _reset(app)
        kwargs = {} if max_polls is None else {"max_polls": max_polls}
        summary = await play_sub_game(
            client, app.push, choose=_chooser(app, rng, board),
            advance=_advancer(app), max_steps=steps, wait=wait, **kwargs
        )
        summaries.append({"sub_game": index, **summary})
        if index < sub_games:
            _reset(app)

    return summaries
