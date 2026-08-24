"""The league's spelling of the coordinate origin (SPEC §4 terms).

`axis_origin_corner` sits INSIDE the signed terms, and `negotiate` compares
those value-by-value. We spell it `topleft`; the community kit spells it
`top-left` in all five places it appears, including the terms-signature
fixture every kit-following group hashes. So our handshake refuses every one
of them, on a hyphen.

The two strings mean the SAME convention — origin at the top-left, row
increasing downward — so this is a spelling to normalise, not a geometry to
change. What must NOT be normalised away is a genuinely different origin: a
peer on `bottom-left` plays a vertically mirrored game that looks entirely
plausible, and refusing that is the whole reason this validation exists.
"""

import json

import pytest

from engine.config import load_config

BOARD = "board_and_agents"


def _contract(tmp_path, origin):
    contract = json.loads(open("config/game.json", encoding="utf-8").read())
    contract[BOARD]["axis_origin_corner"] = origin
    path = tmp_path / "game.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    return str(path)


@pytest.mark.parametrize("origin", ["top-left", "topleft"])
def test_both_spellings_of_the_same_corner_load(tmp_path, origin):
    """Ours and the kit's. A contract written either way must still run."""
    assert load_config(_contract(tmp_path, origin)) is not None


@pytest.mark.parametrize("origin", ["bottom-left", "topright", "bottom_right"])
def test_a_genuinely_different_origin_is_still_refused(tmp_path, origin):
    """The mirrored game is the failure this check exists for; normalising a
    hyphen must not widen it into accepting a different corner."""
    with pytest.raises(ValueError, match="axis_origin_corner"):
        load_config(_contract(tmp_path, origin))


def test_the_shipped_contract_uses_the_leagues_spelling():
    """What actually crosses the wire. Every opposing group runs the kit, so
    the hyphenated form is the one their negotiate compares against."""
    contract = json.loads(open("config/game.json", encoding="utf-8").read())

    assert contract[BOARD]["axis_origin_corner"] == "top-left"


def test_the_terms_carry_the_spelling_verbatim():
    """The terms are hashed as sent — normalising on load must not leave the
    signed value disagreeing with the file both peers diffed."""
    from mcp_server.terms import terms_from_config

    contract = json.loads(open("config/game.json", encoding="utf-8").read())

    assert terms_from_config(contract)["axis_origin_corner"] == "top-left"
