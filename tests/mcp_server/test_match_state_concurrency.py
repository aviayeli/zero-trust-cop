"""Tests for MatchState concurrency and determinism."""

import asyncio

from engine.game_loop import GameEpisode
from mcp_server.match_state import MatchState

# --- concurrency (FR8): exactly one step under asyncio.gather --------------

def test_concurrent_submissions_fire_exactly_one_step(fresh, count_steps):
    ep, ms = fresh()
    calls = count_steps(ep)

    async def scenario():
        await asyncio.gather(ms.submit("cop", "S"), ms.submit("thief", "N"))

    asyncio.run(scenario())
    assert len(calls) == 1     # asyncio.Lock guarantees a single step per turn
    assert ep.turn_count == 1
    assert ms.pending_roles() == []


# --- determinism (FR10): matches a direct Phase-1 step ---------------------

def test_resolution_matches_direct_game_episode_step(cfg):
    cfg_obj = cfg()
    ep1 = GameEpisode(cfg_obj)
    ms = MatchState(ep1, cfg_obj.response_timeout_sec)

    async def scenario():
        await ms.submit("cop", "S")
        return await ms.submit("thief", "N")

    out = asyncio.run(scenario())

    ep2 = GameEpisode(cfg_obj)
    direct = ep2.step("S", "N")

    assert out.status == "resolved"
    assert out.result.cop_position == direct.cop_position
    assert out.result.thief_position == direct.thief_position
    assert out.result.captured == direct.captured
