"""Hand the reference-v3 loop our policy, our board, and our own inbox.

``claims_match_loop`` knows the protocol, not how WE pick a move or what we
believe. This module is that glue, and the reference-v3 twin of
``push_runner`` -- a twin rather than a branch, because the wires disagree on
something the loop cannot paper over: the push dialect resolves BOTH pieces
from a revealed move, this one resolves ours alone.

Every sub-game opens with ``negotiate`` and refuses to push a turn until it is
accepted. ali-ahm1's server queues inbound turns ungated while their game loop
will not READ that queue until the handshake completes, so a turn pushed first
is ignored rather than rejected. The handshake also runs the pairing check in
the direction we never ran it.

The opponent's turns land in ``app.inbox``, inside the SERVER, so a series
runs in the same process as the peer it plays through: a runner elsewhere
would complete the handshake and then poll an inbox it cannot see.

Belief on this wire comes from their SMELL, not their words: the hint is free
text, not our direction vocabulary, so nothing reads a move out of it. Their
trail feeds the pheromone field and the policy asks that field where they are.
"""

from __future__ import annotations

import asyncio
import inspect
from random import Random

from engine.barriers import barrier_layout, populated_board
from mcp_server.claims_side import Side
from mcp_server.directions import LIE, TRUTH, encode, token_for_claim
from mcp_server.negotiate_client import negotiate
from mcp_server.smell_trail import strongest_cell
from mcp_server.turn_client import TurnClient
from scripts.claims_match_loop import play_sub_game
from scripts.push_runner import role_schedule


def _chooser(app, side, rng, board):
    """``(step) -> (move, hint, intent)`` from this peer's own policy.

    The opponent's position is passed as None on purpose: we do not know it
    on this wire, and ``state_key`` resolves the hybrid itself -- falling back
    to the pheromone field, which is the only thing here that has an opinion.
    """
    def choose(step):
        state_key = app.policy.state_key(side.position, None, board)
        token, hint = app.policy.decide(state_key, rng)
        claimed = token_for_claim(app.policy.intent_for_move(token))
        return encode(token), hint, TRUTH if claimed == token else LIE

    return choose


def _observer(app):
    """Feed THEIR smell trail into our belief; ignore an unreadable grid."""
    def observe(turn):
        cell = strongest_cell(turn.get("smell_grid") or {})
        app.policy.pheromones.advance(deposits=[cell] if cell else [])

    return observe


async def play_series(apps: dict, call, sub_games: int, seed: int, wait,
                      first_role: str = "police", max_steps=None,
                      max_polls=None, call_for=None,
                      progress=None, on_sub_game=None, on_repush=None,
                      pause_between: float = 0, pause=None) -> list:
    """Play a whole series on reference-v3, swapping sides every sub-game.

    ``apps`` maps our wire role to the peer serving it; both are needed, since
    their turns land in the inbox of whichever peer plays this sub-game.
    ``call`` reaches an opponent serving both roles on one endpoint;
    ``call_for`` is the two-process form, ``(our_role) -> call``, asked per
    sub-game because the endpoint receiving our turns changes with the side
    they play; a wrong guess pushes a whole sub-game at the wrong peer.

    ``seed`` drives the policy RNG once for the series. ``pause_between``
    seconds are waited at each BOUNDARY for an opponent that relaunches per
    sub-game (PRD_14); zero, the default, is today.

    Raises:
        ValueError: a scheduled role has no peer -- otherwise silently played
            as the wrong side for half the series.
    """
    schedule = role_schedule(sub_games, first_role)
    missing = sorted({role for role in schedule if role not in apps})
    if missing:
        raise ValueError(
            f"no peer for scheduled role(s) {missing}: an alternating series "
            f"needs both, got {sorted(apps)}"
        )

    rng = Random(seed)
    summaries = []

    for index, role in enumerate(schedule, start=1):
        app = apps[role]
        # FIRST, before anything that awaits. Clearing AFTER the handshake
        # deleted turns that had just arrived: our server answers throughout,
        # so a peer that negotiates and pushes at once lands its step 1 DURING
        # our negotiate round-trip. That deadlocked a live series on
        # 2026-08-25: we waited for a step 1 we had accepted and deleted.
        app.inbox.clear()
        # AFTER the clear, never before (PRD_14 FR4): a peer that relaunches
        # per sub-game may push its step 1 during this window, and clearing
        # afterwards would delete exactly that turn.
        if index > 1 and pause_between:
            await (pause or asyncio.sleep)(pause_between)
        reach = call
        if call_for is not None:
            reach = call_for(role)
            # The lazy dialler opens the endpoint on first use,
            # so asking for a role may await a connection.
            if inspect.isawaitable(reach):
                reach = await reach
        # BEFORE the first push. Their server queues turns ungated and their
        # game loop will not read that queue until the handshake completes,
        # so a turn sent first sits unread and reads to us as a slow peer.
        handshake = await negotiate(reach, app.terms, app.identity(), role, index)
        # Both peers derive the identical layout from the contract's
        # barrier_seed, so the board needs no wire message (PLAN.md 4.3).
        board = populated_board(app.config)
        side = Side(app.config, board, role)
        steps = max_steps if max_steps is not None else app.config.max_moves
        kwargs = {} if max_polls is None else {"max_polls": max_polls}

        summary = await play_sub_game(
            TurnClient(reach, sender=role), app.inbox, side,
            choose=_chooser(app, side, rng, board),
            barriers=barrier_layout(app.config), max_steps=steps, wait=wait,
            observe=_observer(app), progress=progress,
            on_repush=on_repush, **kwargs
        )
        closed = {
            "sub_game": index, "role": role,
            # Whether the opponent COUNTER-SIGNED. A bare `accepted: true`
            # opens their queue and verifies nothing, and a series played on
            # one is not a series we checked.
            "handshake_counter_signed": handshake["counter_signed"],
            **summary,
        }
        summaries.append(closed)
        # Persist NOW. A sub-game that completed is evidence, and whatever
        # happens in the next one cannot un-play it.
        if on_sub_game is not None:
            on_sub_game(closed)

    return summaries
