"""Tests for MatchState timeout and terminal_reason derivation.

Async note: MatchState.submit is a coroutine guarded by an asyncio.Lock. To
avoid cross-event-loop lock binding, every scenario performs all of a given
MatchState's awaits inside ONE `asyncio.run(...)` call (one event loop per
MatchState instance).
"""

import asyncio

from engine.game_loop import GameEpisode
from mcp_server.match_state import MatchState

# --- lazy, non-blocking timeout via injected clock -------------------------

def test_lazy_timeout_forfeits_stale_half_filled_turn(cfg, fake_clock, count_steps):
    """A half-filled turn past its deadline is cleared on the next call; the
    stale action is dropped and no step fires. (Timeout SEMANTICS flagged for
    Conductor review: current expectation = the triggering submission becomes
    the first action of a fresh turn -> 'waiting', and no GameEpisode.step is
    called for the abandoned turn.)"""
    clock = fake_clock(0.0)
    cfg_obj = cfg()
    ep = GameEpisode(cfg_obj)
    ms = MatchState(ep, cfg_obj.response_timeout_sec, clock=clock)  # 30s timeout
    calls = count_steps(ep)

    async def scenario():
        first = await ms.submit("cop", "S")   # buffered; deadline = 0 + 30
        clock.advance(cfg_obj.response_timeout_sec + 1)  # 31s: past deadline
        after = await ms.submit("thief", "N")  # lazy check clears cop's stale slot
        return first, after

    first, after = asyncio.run(scenario())
    assert first.status == "waiting"
    assert len(calls) == 0        # the abandoned turn never stepped
    assert ep.turn_count == 0
    assert after.status == "waiting"      # thief now first of a fresh turn
    assert ms.pending_roles() == ["thief"]


def test_no_timeout_before_deadline(cfg, fake_clock):
    clock = fake_clock(0.0)
    cfg_obj = cfg()
    ep = GameEpisode(cfg_obj)
    ms = MatchState(ep, cfg_obj.response_timeout_sec, clock=clock)

    async def scenario():
        await ms.submit("cop", "S")
        clock.advance(cfg_obj.response_timeout_sec - 1)  # still within window
        return await ms.submit("thief", "N")

    out = asyncio.run(scenario())
    assert out.status == "resolved"   # resolved normally, not timed out
    assert ep.turn_count == 1


# --- terminal_reason derivation --------------------------------------------

def test_terminal_reason_none_when_active(fresh):
    _ep, ms = fresh()
    assert ms.terminal_reason() is None


def test_terminal_reason_capture(cfg):
    cfg_obj = cfg()
    ep = GameEpisode(cfg_obj)
    ep.cop_state.position = (2, 2)
    ep.thief_state.position = (2, 4)
    ms = MatchState(ep, cfg_obj.response_timeout_sec)

    async def scenario():
        await ms.submit("cop", "E")     # (2,2)->(2,3)
        return await ms.submit("thief", "W")  # (2,4)->(2,3): same cell capture

    out = asyncio.run(scenario())
    assert out.status == "resolved"
    assert out.result.captured is True
    assert ms.is_terminated is True
    assert ms.terminal_reason() == "capture"


def test_terminal_reason_max_moves(cfg):
    cfg_obj = cfg()
    ep = GameEpisode(cfg_obj)
    ep.turn_count = cfg_obj.max_moves - 1   # one turn short of the limit
    ms = MatchState(ep, cfg_obj.response_timeout_sec)

    async def scenario():
        await ms.submit("cop", "STAY")   # cop (0,0) / thief (3,3): no capture
        return await ms.submit("thief", "STAY")

    out = asyncio.run(scenario())
    assert out.status == "resolved"
    assert ms.turn_count == cfg_obj.max_moves
    assert ms.is_terminated is True
    assert ms.terminal_reason() == "max_moves_reached"
