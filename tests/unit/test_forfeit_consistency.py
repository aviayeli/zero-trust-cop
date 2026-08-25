"""Audit remediation Pass 2 (V5): forfeit must be visible everywhere.

The audit found the forfeit lived on SubmissionGate and was patched onto
``get_match_status`` alone, so a peer polling ``get_observation`` saw a LIVE
match while the status tool reported a technical loss. Two tools, two
answers, one match. The state now lives on MatchState, which every tool
reads.
"""

import asyncio

import pytest

from engine.config import load_config
from engine.game_loop import GameEpisode
from mcp_server.match_state import MatchState


@pytest.fixture
def match_state():
    config = load_config("config/game.json")
    return MatchState(GameEpisode(config), config.response_timeout_sec)


def test_a_live_match_is_not_forfeited(match_state):
    assert match_state.is_terminated is False
    assert match_state.terminal_reason() is None
    assert match_state.forfeited_by == []


def test_forfeit_terminates_the_match_state_itself(match_state):
    match_state.forfeit(["thief"])

    assert match_state.is_terminated is True
    assert match_state.terminal_reason() == "technical_loss"
    assert match_state.forfeited_by == ["thief"]


def test_forfeit_records_every_stalled_role(match_state):
    match_state.forfeit(["police", "thief"])

    assert match_state.forfeited_by == ["police", "thief"]


def test_forfeiting_nobody_leaves_the_match_live(match_state):
    """An empty stall list must not terminate a healthy match."""
    match_state.forfeit([])

    assert match_state.is_terminated is False
    assert match_state.terminal_reason() is None


def test_a_real_game_outcome_outranks_a_late_forfeit(match_state):
    """A finished game keeps its true reason; forfeit is a protocol fallback."""

    async def play_to_capture():
        for _ in range(match_state._episode.config.max_moves):
            await match_state.submit("cop", "S")
            await match_state.submit("thief", "N")
            if match_state.is_terminated:
                return

    asyncio.run(play_to_capture())
    assert match_state.is_terminated is True
    real_reason = match_state.terminal_reason()

    match_state.forfeit(["thief"])

    assert match_state.terminal_reason() == real_reason
    assert real_reason in {"capture", "max_moves_reached"}


def test_the_timeout_is_readable_without_touching_a_private(match_state):
    config = load_config("config/game.json")

    assert match_state.response_timeout_sec == config.response_timeout_sec
