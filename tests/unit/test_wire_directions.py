"""Wire payload semantics v3.0.0: move carries a DIRECTION, intent the honesty.

Previously `move` was an engine token ("N") and `intent` was a direction word
("north"), so honesty was implicit in whether the two agreed. The wire now
states it: move is 'north'/'south'/..., intent is exactly 'truth' or 'lie'.

The engine still speaks N/S/E/W/STAY, so the mapping lives at the protocol
layer -- src/engine/ must not learn that a wire encoding exists.
"""

import pytest

from mcp_server.directions import (
    LIE,
    TRUTH,
    is_intent,
    opposite,
    stated_hint,
    to_token,
    to_word,
)


@pytest.mark.parametrize("token, word", [
    ("N", "north"), ("S", "south"), ("E", "east"), ("W", "west"),
    ("STAY", "stay"),
])
def test_tokens_and_words_round_trip(token, word):
    assert to_word(token) == word
    assert to_token(word) == token


def test_an_unknown_word_is_rejected_not_guessed():
    with pytest.raises(ValueError):
        to_token("northeast")


def test_an_unknown_token_is_rejected():
    with pytest.raises(ValueError):
        to_word("NE")


@pytest.mark.parametrize("word, other", [
    ("north", "south"), ("south", "north"), ("east", "west"), ("west", "east"),
])
def test_opposites_are_an_involution(word, other):
    assert opposite(word) == other
    assert opposite(opposite(word)) == word


def test_stay_is_its_own_opposite():
    """D4's documented hole: a thief that stays tells the truth that turn."""
    assert opposite("stay") == "stay"


def test_only_truth_and_lie_are_valid_intents():
    assert is_intent(TRUTH) and is_intent(LIE)
    assert not is_intent("north")
    assert not is_intent("")
    assert not is_intent("TRUTH")


def test_a_truthful_hint_is_the_move_itself():
    assert stated_hint("north", TRUTH) == "north"


def test_a_deceptive_hint_is_the_opposite_move():
    """The hint an opponent's belief tracker should score."""
    assert stated_hint("north", LIE) == "south"


def test_an_invalid_intent_cannot_produce_a_hint():
    with pytest.raises(ValueError):
        stated_hint("north", "maybe")
