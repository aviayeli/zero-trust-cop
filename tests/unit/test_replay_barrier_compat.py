"""A log must replay against the board it was PLAYED on (PLAN.md §4.3).

Phase 9 populates every episode's board from configuration, which would have
re-decided the flagship log's match on a board it never saw. The layout is
therefore recorded in the log and reconstructed from it, and a log written
before Phase 9 carries no such field and must still replay bare -- that
backwards compatibility is what lets signed pre-Phase-9 evidence stay
verifiable without re-sealing it (PLAN.md §10.10, *Provenance*).
"""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from engine.barriers import barrier_layout
from engine.config import load_config
from scripts.log_checks import replay_episode

SHIPPED_LOG = Path("logs/aviayeli/log_aviayeli_g01.json")


@pytest.fixture
def config():
    return replace(load_config("config/game.json"), barrier_seed=20260818)


def test_a_log_without_the_field_replays_on_a_bare_board(config):
    """Pre-Phase-9 evidence: the absent key means bare, not "use today's".""" ""
    episode = replay_episode({"turns": []}, config)

    assert episode.board.barrier_count == 0


def test_a_log_carrying_a_layout_replays_against_exactly_that_layout(config):
    layout = barrier_layout(config)
    log = {"turns": [], "barriers": [list(cell) for cell in sorted(layout)]}

    episode = replay_episode(log, config)

    assert episode.board.barrier_count == len(layout)
    assert all(episode.board.is_barrier(cell) for cell in layout)


def test_a_logged_layout_wins_over_the_configured_one(config):
    """The log is the record of what happened; config is only today's default."""
    log = {"turns": [], "barriers": [[1, 1]]}

    episode = replay_episode(log, config)

    assert episode.board.barrier_count == 1
    assert episode.board.is_barrier((1, 1))


def test_the_shipped_flagship_log_carries_no_layout():
    """Guards the assumption the fallback exists for: it predates Phase 9."""
    log = json.loads(SHIPPED_LOG.read_text(encoding="utf-8"))

    assert "barriers" not in log


def test_build_log_records_the_layout_the_match_was_played_on(config):
    """The log must be replayable on its own; a seed the reader lacks is not."""
    from scripts.match_log import build_log

    layout = barrier_layout(config)
    log = build_log("g1", 1, [], "aviayeli", barriers=layout)

    assert log["barriers"] == [list(cell) for cell in sorted(layout)]


def test_build_log_defaults_to_a_bare_board(config):
    from scripts.match_log import build_log

    assert build_log("g1", 1, [], "aviayeli")["barriers"] == []


def test_a_written_log_round_trips_through_the_replay_board(config, tmp_path):
    """Record, re-read, reconstruct: the layout must survive JSON."""
    from scripts.match_log import build_log

    layout = barrier_layout(config)
    written = tmp_path / "log.json"
    written.write_text(json.dumps(build_log("g1", 1, [], "aviayeli", barriers=layout)))

    episode = replay_episode(json.loads(written.read_text()), config)

    assert {cell for cell in layout if episode.board.is_barrier(cell)} == layout
