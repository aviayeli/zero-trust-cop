"""Reproducibility, per-role persistence, epsilon decay, and data/ purity."""

from pathlib import Path

from scripts.run_tournament import train_tournament
from strategy.qvalues import QValues
from strategy.settings import load_strategy_settings

DATA_DIR = Path("data")


def _data_fingerprint():
    """Size and mtime of every file in the production data/ directory.

    Comparing a fingerprint rather than a name set catches an OVERWRITE of an
    already-present deliverable, and is order-independent: a bare
    before/after listing passes vacuously once an earlier test has already
    created the file it is meant to protect.
    """
    return {
        path.name: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in DATA_DIR.iterdir()
        if path.is_file()
    }


def test_a_seeded_series_is_reproducible(config, training_settings):
    cop_settings, thief_settings = training_settings(num_games=5)

    first_scores = train_tournament(config, cop_settings, thief_settings, seed=99)
    first_cop = Path(cop_settings.qtable_path).read_text()
    first_thief = Path(thief_settings.qtable_path).read_text()

    second_scores = train_tournament(config, cop_settings, thief_settings, seed=99)

    assert second_scores == first_scores
    assert Path(cop_settings.qtable_path).read_text() == first_cop
    assert Path(thief_settings.qtable_path).read_text() == first_thief


def test_a_different_seed_changes_the_series(config, training_settings):
    """Guards the reproducibility test above from passing vacuously."""
    cop_settings, thief_settings = training_settings(num_games=5)

    train_tournament(config, cop_settings, thief_settings, seed=99)
    first_cop = Path(cop_settings.qtable_path).read_text()

    train_tournament(config, cop_settings, thief_settings, seed=1234)

    assert Path(cop_settings.qtable_path).read_text() != first_cop


def test_each_role_persists_to_its_own_path(config, training_settings):
    cop_settings, thief_settings = training_settings(num_games=2)
    assert cop_settings.qtable_path != thief_settings.qtable_path

    train_tournament(config, cop_settings, thief_settings, seed=3)

    assert Path(cop_settings.qtable_path).exists()
    assert Path(thief_settings.qtable_path).exists()


def test_the_two_peers_ship_different_production_paths():
    cop_path = load_strategy_settings("police").qtable_path
    thief_path = load_strategy_settings("thief").qtable_path

    assert cop_path != thief_path


def test_epsilon_decays_exactly_once_per_game(
    config, training_settings, monkeypatch
):
    cop_settings, thief_settings = training_settings(num_games=4)
    calls = []
    original = QValues.decay_epsilon

    def spy(self):
        calls.append(self.settings.qtable_path)
        return original(self)

    monkeypatch.setattr(QValues, "decay_epsilon", spy)

    train_tournament(config, cop_settings, thief_settings, seed=3)

    assert calls.count(cop_settings.qtable_path) == 4
    assert calls.count(thief_settings.qtable_path) == 4


def test_training_never_touches_the_production_data_directory(
    config, training_settings
):
    before = _data_fingerprint()
    cop_settings, thief_settings = training_settings(num_games=3)

    train_tournament(config, cop_settings, thief_settings, seed=3)

    assert _data_fingerprint() == before
