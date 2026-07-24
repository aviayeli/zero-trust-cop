"""Shared test fixtures for mcp_server test modules."""

import time
from types import SimpleNamespace

import pytest

from engine.config import load_config
from engine.game_loop import GameEpisode
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
    _pending = pending_roles if pending_roles is not None else []
    return SimpleNamespace(
        turn_count=turn_count,
        is_terminated=is_terminated,
        cop_position=cop_position,
        thief_position=thief_position,
        barrier_count=barrier_count,
        pending_roles=lambda _v=_pending: _v,
        terminal_reason=lambda _v=terminal_reason: _v,
    )


def _make_config(grid_size=7):
    return SimpleNamespace(grid_size=grid_size)


def _make_turn_result(cop_position=(1, 0), thief_position=(3, 4), captured=False):
    return SimpleNamespace(
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
