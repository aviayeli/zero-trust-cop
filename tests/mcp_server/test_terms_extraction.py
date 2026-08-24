"""The agreed terms are EXTRACTED from game.json, never hashed wholesale.

``game_uid`` and the pre-game signature are computed over a flat 14-key terms
dict -- the book's App. F table. Hashing the whole ``game.json`` instead
produces a uid that is stable, reproducible and identical across all four of
our own artifacts, so they join each other perfectly and only the CROSS-team
join fails. That failure mode is silent: the uid never crosses the wire, and
every game value in the two teams' reports can agree exactly while the uid
does not. It went six sub-games unnoticed in the league's 2026-07-25 series.
"""

import json

import pytest

from mcp_server import interop
from mcp_server.terms import TERMS_KEYS, terms_from_config


@pytest.fixture
def config():
    with open("config/game.json", encoding="utf-8") as source:
        return json.load(source)


@pytest.fixture
def terms(config):
    return terms_from_config(config)


def test_the_terms_are_exactly_the_agreed_key_set(terms):
    """Closed key set: an extra key changes every hash it feeds."""
    assert sorted(terms) == sorted(TERMS_KEYS)
    assert len(TERMS_KEYS) == 14


def test_the_terms_are_flat(terms):
    """No nested containers except the two start coordinates."""
    for key, value in terms.items():
        if key not in ("cop_start", "thief_start"):
            assert not isinstance(value, (dict, list)), f"{key} is nested"


def test_every_term_is_read_from_the_config(config, terms):
    assert terms["board_size"] == config["board_and_agents"]["grid_size"]
    assert terms["thief_start"] == config["board_and_agents"]["thief_start"]
    assert terms["cop_start"] == config["board_and_agents"]["cop_start"]
    assert terms["max_steps"] == config["movement_and_barriers"]["max_moves"]
    assert terms["barriers_max"] == config["movement_and_barriers"]["max_barriers"]
    assert terms["smell_grid_size"] == config["pheromones"]["pheromone_grid_size"]
    assert terms["decay_per_step"] == config["pheromones"]["pheromone_decay"]
    assert terms["emit_intensity"] == config["pheromones"]["pheromone_center_intensity"]
    assert terms["min_center_intensity"] == \
        config["pheromones"]["pheromone_min_center_intensity"]
    assert terms["setting"] == config["world"]["map_area"]
    assert terms["hint_max_words"] == config["world"]["hint_max_words"]
    assert terms["num_games"] == config["network_and_league"]["num_games"]
    assert terms["axis_origin_corner"] == config["board_and_agents"]["axis_origin_corner"]
    assert terms["axis_start_index"] == config["board_and_agents"]["axis_start_index"]


def test_nothing_in_the_terms_is_hardcoded(terms, config):
    """Project constitution: no tunable value inlined in source. Every term
    must move when game.json moves."""
    edited = json.loads(json.dumps(config))
    edited["board_and_agents"]["grid_size"] = 11
    edited["pheromones"]["pheromone_decay"] = 0.42

    moved = terms_from_config(edited)

    assert moved["board_size"] == 11
    assert moved["decay_per_step"] == 0.42
    assert moved != terms


def test_a_missing_term_is_a_setup_error_not_a_default(config):
    """A silently defaulted term hashes to a uid the opponent cannot reach."""
    broken = json.loads(json.dumps(config))
    del broken["pheromones"]["pheromone_min_center_intensity"]

    with pytest.raises(KeyError):
        terms_from_config(broken)


def test_the_uid_is_derived_from_the_terms_not_the_whole_config(config, terms):
    """The silent 2026-07-25 failure, pinned as a regression."""
    from_terms = interop.game_uid(terms, "aviayeli", "groupb")
    from_config = interop.game_uid(config, "aviayeli", "groupb")

    assert from_terms != from_config


def test_the_extraction_is_stable_across_calls(config):
    assert terms_from_config(config) == terms_from_config(config)
