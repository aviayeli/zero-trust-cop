"""Shared test fixtures for mcp_server test modules.

Stub-drift policy: the MatchState double is spec-locked to the real class with
create_autospec(spec_set=True), so a renamed member, a changed signature, or a
method becoming a property fails here instead of drifting silently. GameConfig
and TurnResult are plain dataclasses, so tests use real instances rather than
doubles at all — construction itself enforces their field contract.
"""

import time
from dataclasses import replace
from unittest.mock import create_autospec

import pytest

from engine.config import load_config
from engine.game_loop import GameEpisode
from engine.resolver import TurnResult
from mcp_server.match_state import MatchState


def _make_match_state(
    turn_count=4,
    is_terminated=False,
    cop_position=(0, 0),
    thief_position=(3, 4),
    barrier_count=3,
    pending_roles=None,
    terminal_reason=None,
):
    """A MatchState double locked to the real class's public interface.

    pending_roles and terminal_reason stay CALLABLES because that is what
    MatchState declares. Reading either as a plain attribute now yields a Mock
    rather than a value — the precise drift that shipped a JSON-serialization
    bug in Task 4.5, and which the old SimpleNamespace stub could not detect.
    """
    ms = create_autospec(MatchState, instance=True, spec_set=True)
    ms.turn_count = turn_count
    ms.is_terminated = is_terminated
    ms.cop_position = cop_position
    ms.thief_position = thief_position
    ms.barrier_count = barrier_count
    ms.pending_roles.return_value = [] if pending_roles is None else pending_roles
    ms.terminal_reason.return_value = terminal_reason
    return ms


def _make_config(grid_size=7):
    """A real GameConfig. It is a plain dataclass, so a real instance enforces
    the full field contract more strictly than any double could."""
    return replace(load_config("config/game.json"), grid_size=grid_size)


def _make_turn_result(cop_position=(1, 0), thief_position=(3, 4), captured=False):
    """A real TurnResult: a field rename fails at construction."""
    return TurnResult(
        cop_position=cop_position,
        thief_position=thief_position,
        captured=captured,
    )


def _cfg():
    return load_config("config/game.json")


def _fresh(clock=None):
    """A MatchState around a fresh GameEpisode; timeout sourced from config."""
    cfg = _cfg()
    ep = GameEpisode(cfg)
    ms = MatchState(ep, cfg.response_timeout_sec, clock=clock or time.monotonic)
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


@pytest.fixture
def make_match_state():
    return _make_match_state


@pytest.fixture
def make_config():
    return _make_config


@pytest.fixture
def make_turn_result():
    return _make_turn_result


@pytest.fixture
def fresh():
    return _fresh


@pytest.fixture
def fake_clock():
    return FakeClock


@pytest.fixture
def count_steps():
    return _count_steps


@pytest.fixture
def cfg():
    return _cfg
