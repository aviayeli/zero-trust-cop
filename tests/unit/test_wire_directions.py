"""Wire vocabulary v3.0.0: uppercase move tokens, explicit honesty flag.

`move` is the engine's own token so nothing is translated at the boundary,
and `intent` states honesty outright rather than leaving it implicit in
whether a spoken hint happened to match the move.
"""

import pytest

from mcp_server.directions import (
    LIE,
    MOVES,
    TRUTH,
    is_intent,
    is_move,
    opposite,
    stated_hint,
    token_for_claim,
)


def test_the_wire_vocabulary_is_the_engine_vocabulary():
    assert MOVES == ("N", "S", "E", "W", "STAY")


@pytest.mark.parametrize("token", ["N", "S", "E", "W", "STAY"])
def test_every_engine_token_is_a_valid_move(token):
    assert is_move(token)


@pytest.mark.parametrize("bad", ["north", "n", "", None, "BARRIER", "NE"])
def test_anything_outside_the_vocabulary_is_rejected(bad):
    """Lowercase and prose forms must NOT be silently accepted."""
    assert not is_move(bad)


@pytest.mark.parametrize("token, other", [("N", "S"), ("S", "N"), ("E", "W"), ("W", "E")])
def test_opposites_are_an_involution(token, other):
    assert opposite(token) == other
    assert opposite(opposite(token)) == token


def test_stay_is_its_own_opposite():
    """D4's documented hole: a thief that stays tells the truth that turn."""
    assert opposite("STAY") == "STAY"


def test_an_unknown_token_has_no_opposite():
    with pytest.raises(ValueError):
        opposite("BARRIER")


def test_only_truth_and_lie_are_valid_intents():
    assert is_intent(TRUTH) and is_intent(LIE)
    for bad in ("N", "", "TRUTH", None):
        assert not is_intent(bad)


@pytest.mark.parametrize("word, token", [
    ("north", "N"), ("south", "S"), ("east", "E"), ("west", "W"), ("stay", "STAY"),
])
def test_a_spoken_claim_maps_to_its_token(word, token):
    assert token_for_claim(word) == token


def test_an_unknown_claim_is_rejected_not_guessed():
    with pytest.raises(ValueError):
        token_for_claim("northeast")


def test_a_truthful_hint_is_the_move_itself():
    assert stated_hint("N", TRUTH) == "N"


def test_a_deceptive_hint_is_the_opposite_move():
    assert stated_hint("N", LIE) == "S"


def test_an_invalid_intent_cannot_produce_a_hint():
    with pytest.raises(ValueError):
        stated_hint("N", "maybe")
