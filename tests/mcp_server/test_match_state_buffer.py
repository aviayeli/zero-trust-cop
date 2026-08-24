"""Tests for MatchState buffer basics and validation."""

import asyncio

from mcp_server.match_state import MatchState, SubmitOutcome


# --- buffer basics ---------------------------------------------------------

def test_buffer_starts_empty(fresh):
    _ep, ms = fresh()
    assert ms.pending_roles() == []


def test_first_submit_waits_and_does_not_advance_episode(fresh):
    ep, ms = fresh()
    out = asyncio.run(ms.submit("cop", "S"))
    assert isinstance(out, SubmitOutcome)
    assert out.status == "waiting"
    assert ep.turn_count == 0  # episode not advanced by a single submission
    assert ms.pending_roles() == ["cop"]


def test_second_submit_resolves_with_exactly_one_step(fresh, count_steps):
    ep, ms = fresh()
    calls = count_steps(ep)

    async def scenario():
        first = await ms.submit("cop", "S")
        second = await ms.submit("thief", "N")
        return first, second

    first, second = asyncio.run(scenario())
    assert first.status == "waiting"
    assert second.status == "resolved"
    assert second.result is not None
    assert len(calls) == 1           # exactly one GameEpisode.step
    assert ep.turn_count == 1
    assert ms.pending_roles() == []  # buffer cleared after resolution


# --- validation & rejection (no mutation) ----------------------------------

def test_invalid_role_rejected_no_mutation(fresh):
    ep, ms = fresh()
    out = asyncio.run(ms.submit("referee", "N"))
    assert out.status == "rejected"
    assert out.reason == "invalid_role"
    assert ep.turn_count == 0
    assert ms.pending_roles() == []


def test_invalid_direction_rejected_no_mutation(fresh):
    ep, ms = fresh()
    out = asyncio.run(ms.submit("cop", "NE"))
    assert out.status == "rejected"
    assert out.reason == "invalid_direction"
    assert ep.turn_count == 0
    assert ms.pending_roles() == []


def test_double_submission_rejected_and_does_not_overwrite(fresh):
    ep, ms = fresh()

    async def scenario():
        a = await ms.submit("cop", "S")   # first: buffered
        b = await ms.submit("cop", "N")   # same role again: rejected
        c = await ms.submit("thief", "STAY")  # resolves the turn
        return a, b, c

    a, b, c = asyncio.run(scenario())
    assert a.status == "waiting"
    assert b.status == "rejected"
    assert b.reason == "already_submitted"
    assert c.status == "resolved"
    # cop's FIRST action ("S": (0,0)->(1,0)) was kept, not overwritten by "N"
    assert c.result.cop_position == (1, 0)


# --- sub-game boundary ------------------------------------------------------


def test_reset_clears_the_board_and_the_half_filled_buffer():
    """A sub-game boundary must not leave one peer's action buffered.

    Carrying a slot across the boundary would resolve the next sub-game's
    first turn against a move submitted for the previous one.
    """
    import asyncio

    from engine.config import load_config
    from engine.game_loop import GameEpisode

    config = load_config("config/game.json")
    state = MatchState(GameEpisode(config), config.response_timeout_sec)

    asyncio.run(state.submit("cop", "N"))
    assert state.pending_roles() != []

    state.reset()

    assert state.pending_roles() == []
    assert state.turn_count == 0
    assert state.is_terminated is False
    assert state.forfeited_by == []
