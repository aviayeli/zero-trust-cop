"""The README's state-space claims, checked against the shipped tables.

These went stale exactly the way §10.10's provenance note did. The Phase 9
retrain moved the police table from 177 states to 233 and the thief from 144
to 230, and the "~6% of the representable state space" paragraph kept quoting
the old counts because nothing re-derived them. `test_thief_figures.py`
already does this for the thief's own strategy block; the README's own
paragraph had no equivalent.

Everything here is read from `data/*.json` and `config/game.json`, so it costs
no training run — which is why it can afford to be exact.
"""

import json
import re
from pathlib import Path

import pytest

from engine.config import load_config
from strategy.settings import load_strategy_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
README = PROJECT_ROOT / "README.md"


def _table_facts(role):
    """(entries, states, states_with_every_action_valued) for one shipped table."""
    path = load_strategy_settings(role).qtable_path
    records = json.loads((PROJECT_ROOT / path).read_text(encoding="utf-8"))["q_values"]
    actions = {}
    for relative, mask, action, _ in records:
        key = (tuple(relative) if relative else None, mask)
        actions.setdefault(key, set()).add(action)
    move_set = load_config(str(PROJECT_ROOT / "config/game.json")).move_set
    full = sum(1 for valued in actions.values() if len(valued) == len(move_set))
    return len(records), len(actions), full


@pytest.fixture(scope="module")
def readme():
    return README.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def facts():
    return {"police": _table_facts("police"), "thief": _table_facts("thief")}


def test_the_representable_state_space_is_stated_correctly(readme):
    """`(relative_opponent, barrier_mask)` over a 7x7 board."""
    config = load_config(str(PROJECT_ROOT / "config/game.json"))
    space = (2 * config.grid_size - 1) ** 2 * 2 ** 4

    assert f"{space:,}" in readme, f"the README no longer states {space:,} states"


def test_the_documented_state_counts_match_the_shipped_tables(readme, facts):
    _, police_states, _ = facts["police"]
    _, thief_states, _ = facts["thief"]

    assert (
        f"holds {police_states:,} distinct states and the thief "
        f"{thief_states:,}" in readme
    )


def test_the_documented_coverage_percentages_match(readme, facts):
    config = load_config(str(PROJECT_ROOT / "config/game.json"))
    space = (2 * config.grid_size - 1) ** 2 * 2 ** 4
    for role in ("police", "thief"):
        _, states, _ = facts[role]
        quoted = f"**{100 * states / space:.2f}%**"

        assert quoted in readme, f"the README no longer states {quoted} for {role}"


def test_the_fully_valued_state_counts_match(readme, facts):
    """The 'all five actions valued' fraction, which the retrain also moved."""
    _, police_states, police_full = facts["police"]
    _, thief_states, thief_full = facts["thief"]

    assert (
        f"{police_full:,}/{police_states:,} and {thief_full:,}/{thief_states:,}"
        in readme
    )


def test_the_documented_entry_counts_match(readme, facts):
    for role in ("police", "thief"):
        entries, _, _ = facts[role]

        assert f"({entries:,} entries, all" in readme, (
            f"the README no longer states {entries} entries for {role}"
        )
