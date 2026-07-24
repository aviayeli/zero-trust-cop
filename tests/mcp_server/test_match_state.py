"""Strict-TDD tests for MatchState (Task 3) — the async buffering core.

These assert the intended behaviour per PLAN_02_MCP_Server.md's locked
algorithm. Against the current SKELETON (methods raise NotImplementedError)
they are RED; they turn GREEN once the logic is implemented.

Async note: MatchState.submit is a coroutine guarded by an asyncio.Lock. To
avoid cross-event-loop lock binding, every scenario performs all of a given
MatchState's awaits inside ONE `asyncio.run(...)` call (one event loop per
MatchState instance).
"""

import asyncio

from engine.config import load_config
from engine.game_loop import GameEpisode
from mcp_server.match_state import MatchState, SubmitOutcome


def _cfg():
    return load_config("config/game.json")


def _fresh(clock=None):
    """A MatchState around a fresh GameEpisode; timeout sourced from config."""
    cfg = _cfg()
    ep = GameEpisode(cfg)
    ms = MatchState(ep, cfg.response_timeout_sec, clock=clock or __import__("time").monotonic)
    return ep, ms


class FakeClock:
    """Deterministic injectable clock: no real waiting in the suite."""

    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def _count_steps(ep):
    """Wrap ep.step to count invocations; returns the calls list."""
    calls = []
    original = ep.step

    def counting(cop_token, thief_token):
        calls.append((cop_token, thief_token))
        return original(cop_token, thief_token)

    ep.step = counting
    return calls


# --- buffer basics ---------------------------------------------------------

def test_buffer_starts_empty():
    _ep, ms = _fresh()
    assert ms.pending_roles() == []


def test_first_submit_waits_and_does_not_advance_episode():
    ep, ms = _fresh()
    out = asyncio.run(ms.submit("cop", "S"))
    assert isinstance(out, SubmitOutcome)
    assert out.status == "waiting"
    assert ep.turn_count == 0  # episode not advanced by a single submission
    assert ms.pending_roles() == ["cop"]


def test_second_submit_resolves_with_exactly_one_step():
    ep, ms = _fresh()
    calls = _count_steps(ep)

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

def test_invalid_role_rejected_no_mutation():
    ep, ms = _fresh()
    out = asyncio.run(ms.submit("referee", "N"))
    assert out.status == "rejected"
    assert out.reason == "invalid_role"
    assert ep.turn_count == 0
    assert ms.pending_roles() == []


def test_invalid_direction_rejected_no_mutation():
    ep, ms = _fresh()
    out = asyncio.run(ms.submit("cop", "NE"))
    assert out.status == "rejected"
    assert out.reason == "invalid_direction"
    assert ep.turn_count == 0
    assert ms.pending_roles() == []


def test_double_submission_rejected_and_does_not_overwrite():
    ep, ms = _fresh()

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


# --- lazy, non-blocking timeout via injected clock -------------------------

def test_lazy_timeout_forfeits_stale_half_filled_turn():
    """A half-filled turn past its deadline is cleared on the next call; the
    stale action is dropped and no step fires. (Timeout SEMANTICS flagged for
    Conductor review: current expectation = the triggering submission becomes
    the first action of a fresh turn -> 'waiting', and no GameEpisode.step is
    called for the abandoned turn.)"""
    clock = FakeClock(0.0)
    cfg = _cfg()
    ep = GameEpisode(cfg)
    ms = MatchState(ep, cfg.response_timeout_sec, clock=clock)  # 30s timeout
    calls = _count_steps(ep)

    async def scenario():
        first = await ms.submit("cop", "S")   # buffered; deadline = 0 + 30
        clock.advance(cfg.response_timeout_sec + 1)  # 31s: past deadline
        after = await ms.submit("thief", "N")  # lazy check clears cop's stale slot
        return first, after

    first, after = asyncio.run(scenario())
    assert first.status == "waiting"
    assert len(calls) == 0        # the abandoned turn never stepped
    assert ep.turn_count == 0
    assert after.status == "waiting"      # thief now first of a fresh turn
    assert ms.pending_roles() == ["thief"]


def test_no_timeout_before_deadline():
    clock = FakeClock(0.0)
    cfg = _cfg()
    ep = GameEpisode(cfg)
    ms = MatchState(ep, cfg.response_timeout_sec, clock=clock)

    async def scenario():
        await ms.submit("cop", "S")
        clock.advance(cfg.response_timeout_sec - 1)  # still within window
        return await ms.submit("thief", "N")

    out = asyncio.run(scenario())
    assert out.status == "resolved"   # resolved normally, not timed out
    assert ep.turn_count == 1


# --- terminal_reason derivation --------------------------------------------

def test_terminal_reason_none_when_active():
    _ep, ms = _fresh()
    assert ms.terminal_reason() is None


def test_terminal_reason_capture():
    cfg = _cfg()
    ep = GameEpisode(cfg)
    ep.cop_state.position = (2, 2)
    ep.thief_state.position = (2, 4)
    ms = MatchState(ep, cfg.response_timeout_sec)

    async def scenario():
        await ms.submit("cop", "E")     # (2,2)->(2,3)
        return await ms.submit("thief", "W")  # (2,4)->(2,3): same cell capture

    out = asyncio.run(scenario())
    assert out.status == "resolved"
    assert out.result.captured is True
    assert ms.is_terminated is True
    assert ms.terminal_reason() == "capture"


def test_terminal_reason_max_moves():
    cfg = _cfg()
    ep = GameEpisode(cfg)
    ep.turn_count = cfg.max_moves - 1   # one turn short of the limit
    ms = MatchState(ep, cfg.response_timeout_sec)

    async def scenario():
        await ms.submit("cop", "STAY")   # cop (0,0) / thief (3,3): no capture
        return await ms.submit("thief", "STAY")

    out = asyncio.run(scenario())
    assert out.status == "resolved"
    assert ms.turn_count == cfg.max_moves
    assert ms.is_terminated is True
    assert ms.terminal_reason() == "max_moves_reached"


# --- concurrency (FR8): exactly one step under asyncio.gather --------------

def test_concurrent_submissions_fire_exactly_one_step():
    ep, ms = _fresh()
    calls = _count_steps(ep)

    async def scenario():
        await asyncio.gather(ms.submit("cop", "S"), ms.submit("thief", "N"))

    asyncio.run(scenario())
    assert len(calls) == 1     # asyncio.Lock guarantees a single step per turn
    assert ep.turn_count == 1
    assert ms.pending_roles() == []


# --- determinism (FR10): matches a direct Phase-1 step ---------------------

def test_resolution_matches_direct_game_episode_step():
    cfg = _cfg()
    ep1 = GameEpisode(cfg)
    ms = MatchState(ep1, cfg.response_timeout_sec)

    async def scenario():
        await ms.submit("cop", "S")
        return await ms.submit("thief", "N")

    out = asyncio.run(scenario())

    ep2 = GameEpisode(cfg)
    direct = ep2.step("S", "N")

    assert out.status == "resolved"
    assert out.result.cop_position == direct.cop_position
    assert out.result.thief_position == direct.thief_position
    assert out.result.captured == direct.captured
