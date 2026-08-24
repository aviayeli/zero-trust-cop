"""One outbound reference-v3 TurnMessage (PRD_10 FR1).

Conformance is asserted through the REAL validator, `wire_v3` — the one an
opponent's receiver is built from. Asserting against a hand-written copy of
the field list would pass a message a conformant peer refuses, which is
exactly the failure mode this project keeps hitting.

The optional claim fields appear only when this turn actually carries one. A
null `capture_claim` is legal on the wire (the fixture's accept case spells
its nulls out), but sending "no claim" every step makes the one turn that
DOES claim harder to see in a log, not easier.
"""

import pytest

from engine.config import load_config
from mcp_server import interop, wire_v3
from mcp_server.turn_message import build_turn, sealed_payload, state_string


@pytest.fixture
def config():
    return load_config("config/game.json")


def _turn(**extra):
    return build_turn(step=1, sender="police", hint="north of the park",
                      smell_grid={}, commit="a" * 64, **extra)


def test_a_built_turn_passes_the_real_validator():
    assert wire_v3.validate_turn_message(_turn()) == wire_v3.ACCEPT


def test_the_timestamp_is_filled_in_and_never_empty():
    """A peer sending an empty string here is telling us its clock never ran,
    and a conformant receiver refuses every one of its turns."""
    assert _turn()["timestamp"].strip() != ""


def test_optional_fields_are_absent_unless_this_turn_carries_one():
    assert set(_turn()) == set(wire_v3.TURN_REQUIRED)


def test_a_capture_claim_rides_when_set():
    turn = _turn(capture_claim=[4, 3])

    assert turn["capture_claim"] == [4, 3]
    assert wire_v3.validate_turn_message(turn) == wire_v3.ACCEPT


def test_every_optional_field_is_carried_when_set():
    turn = _turn(capture_claim=[4, 3], claim_response={"claim": [4, 3], "caught": False},
                 win_claim={"type": "survival"}, barrier_placed=[5, 6])

    assert set(turn) == set(wire_v3.TURN_REQUIRED) | set(wire_v3.TURN_OPTIONAL)


def test_the_sealed_state_uses_the_kits_own_spelling(config):
    """`grid=7x7;self=[4, 3];barriers=[]` — the fixture's vector format."""
    assert state_string(config, (4, 3), ()) == "grid=7x7;self=[4, 3];barriers=[]"
    assert state_string(config, (4, 3), [(1, 1)]) == \
        "grid=7x7;self=[4, 3];barriers=[[1, 1]]"


def test_the_sealed_payload_binds_position_move_intent_and_hint(config):
    payload = sealed_payload(config, step=1, position=(4, 3), move="MOVE:S",
                             intent="truth", hint="I keep to the main avenues.",
                             barriers=())

    assert payload == {
        "step": 1,
        "state": "grid=7x7;self=[4, 3];barriers=[]",
        "position": [4, 3],
        "move": "MOVE:S",
        "intent": "truth",
        "hint": "I keep to the main avenues.",
    }


def test_the_sealed_payload_reproduces_the_kits_published_commit(config):
    """The kit's own move-record vector. If this drifts, every audit we send
    is re-hashed by the opponent to a different digest and scored as tamper."""
    payload = sealed_payload(config, step=1, position=(4, 3), move="MOVE:S",
                             intent="truth", hint="I keep to the main avenues.",
                             barriers=())

    assert interop.commit(payload, "112233445566778899aabbccddeeff00") == \
        "aa6420e2d3a907d6c140856caecbb351b4d5ad98e381549c28268669af378dcc"
