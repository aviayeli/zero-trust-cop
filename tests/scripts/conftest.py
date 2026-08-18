"""Fixtures for the offline trainer and the off-manifold probe.

Every TRAINING fixture redirects ``qtable_path`` under ``tmp_path``. A test run
must never write into the production ``data/`` directory, whose contents are
the committed Step 4 deliverables. The probe only ever READS those tables, so
``benchmark_rows`` runs against them directly — and once per session, because
both probe test modules assert against the same published run.
"""

from dataclasses import replace

import pytest

from engine.config import load_config
from strategy.settings import load_strategy_settings

SHARED_CONFIG_PATH = "config/game.json"


@pytest.fixture
def config():
    """The real shared GameConfig."""
    return load_config(SHARED_CONFIG_PATH)


@pytest.fixture
def training_settings(tmp_path):
    """Build both peers' settings, redirected to tmp_path with a short series."""

    def build(num_games):
        cop = replace(
            load_strategy_settings("police"),
            qtable_path=str(tmp_path / "q_table_police.json"),
            num_games=num_games,
        )
        thief = replace(
            load_strategy_settings("thief"),
            qtable_path=str(tmp_path / "q_table_thief.json"),
            num_games=num_games,
        )
        return cop, thief

    return build


@pytest.fixture
def police_settings():
    """The cop's real private settings; the probe never writes through them."""
    return load_strategy_settings("police")


@pytest.fixture
def thief_settings():
    """The evader's real private settings, for probe tests that need a role."""
    return load_strategy_settings("thief")


@pytest.fixture(scope="session")
def benchmark_rows():
    """One full published off-manifold run (~1s), shared by every asserter."""
    from scripts.benchmark_offmanifold import benchmark

    return benchmark()


class PeerStub:
    """A connection stub reporting a fixed barrier count."""

    def __init__(self, barriers, own_role="cop", **extra):
        self.barriers = barriers
        self.own_role = own_role
        self.calls = 0
        self.asked = None
        self.extra = extra

    def __init_subclass__(cls):  # pragma: no cover - documentation only
        raise TypeError("stub is final")

    async def get_observation(self, role):
        self.calls += 1
        self.asked = role
        if role != self.own_role:
            return {"status": "error", "reason": "invalid_role"}
        return dict(
            {"role": role, "barrier_count": self.barriers, "grid_size": 7},
            **self.extra,
        )


@pytest.fixture
def peer_stub():
    """The connection double the agreement tests drive."""
    return PeerStub
