"""The diverse trainer: both tables learn, only the learner learns.

Two properties decide whether this phase did anything. Both are cheap to
assert and neither is visible by reading the training output:

* The LEARNER's table grows and the scripted opponents' tables stay empty. A
  frozen opponent that quietly learned would co-evolve, which is the exact
  failure being fixed.
* The barrier layout VARIES across episodes. Training on one board is how the
  tables came to be specialised to one board.
"""

from dataclasses import replace

import pytest

from engine.config import load_config
from scripts.opponent_pool import load_training_settings
from scripts.train_diverse import layout_seed_for, train_diverse


@pytest.fixture
def config():
    return load_config("config/game.json")


@pytest.fixture
def short(tmp_path):
    """A short run writing its tables somewhere disposable."""
    return {
        "cop_path": str(tmp_path / "cop.json"),
        "thief_path": str(tmp_path / "thief.json"),
    }


def test_both_learners_end_with_a_non_empty_table(config, short):
    result = train_diverse(config, seed=7, episodes=60, **short)

    assert result["cop_entries"] > 0
    assert result["thief_entries"] > 0


def test_the_run_reports_which_opponents_were_actually_faced(config, short):
    """A mix that silently collapsed would still 'train'."""
    result = train_diverse(config, seed=7, episodes=200, **short)

    assert set(result["opponents"]) == {"scripted", "learning", "random"}
    assert all(count > 0 for count in result["opponents"].values())


def test_the_layout_varies_across_episodes(config):
    settings = load_training_settings()
    seeds = {layout_seed_for(episode, settings) for episode in range(200)}

    assert len(seeds) > 1, "every episode trained on the same board"
    assert len(seeds) <= settings.layout_seeds


def test_the_layout_cycle_is_reproducible():
    settings = load_training_settings()

    assert layout_seed_for(17, settings) == layout_seed_for(17, settings)


def test_a_run_is_reproducible_from_its_seed(config, tmp_path):
    """Same seed, same tables — the property every published figure rests on."""
    first = train_diverse(
        config, seed=11, episodes=80,
        cop_path=str(tmp_path / "a.json"), thief_path=str(tmp_path / "b.json"),
    )
    second = train_diverse(
        config, seed=11, episodes=80,
        cop_path=str(tmp_path / "c.json"), thief_path=str(tmp_path / "d.json"),
    )

    assert first == second


def test_a_different_seed_produces_different_training(config, tmp_path):
    first = train_diverse(
        config, seed=1, episodes=80,
        cop_path=str(tmp_path / "a.json"), thief_path=str(tmp_path / "b.json"),
    )
    second = train_diverse(
        config, seed=2, episodes=80,
        cop_path=str(tmp_path / "c.json"), thief_path=str(tmp_path / "d.json"),
    )

    assert first != second


def test_scripted_opponents_are_built_once_not_per_episode(config, short, monkeypatch):
    """Rebuilding an opponent every episode re-read its TOML from disk.

    `scripted()` calls `load_strategy_settings`, so a 10,000-episode run opened
    and parsed the same two files roughly 6,000 times. The pool is fixed for
    the whole run; only its per-episode STATE is not.
    """
    import strategy.opponents as opponents

    built = []
    real = opponents.scripted
    monkeypatch.setattr(
        opponents, "scripted",
        lambda cfg, role, root=None: built.append(role) or real(cfg, role, root),
    )
    monkeypatch.setattr(
        "scripts.train_diverse.scripted", opponents.scripted, raising=False
    )

    train_diverse(config, seed=3, episodes=120, **short)

    assert len(built) <= 4, f"scripted opponents rebuilt {len(built)} times"


def test_a_reused_opponent_starts_each_episode_with_an_empty_scent_field(config):
    """Caching must not leak state between episodes.

    A policy's turn-0 state key falls back to `pheromones.strongest()`, so an
    opponent carrying deposits from a previous episode would decide its first
    move differently. Caching the object is an optimisation; carrying its
    memory would be a behaviour change.
    """
    from scripts.train_diverse import fresh_opponent
    from strategy.opponents import scripted

    opponent = scripted(config, "thief")
    opponent.pheromones.deposit((3, 3))
    assert opponent.pheromones.strongest() is not None

    reused = fresh_opponent(opponent, config)

    assert reused.pheromones.strongest() is None
