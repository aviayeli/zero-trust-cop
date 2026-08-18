"""The coordinate convention is agreed, so it must be READ, not assumed.

`actions.py` documents "origin at top-left, row increases downward" in a
docstring and `board.py` indexes from 0. Both are correct, and neither was
ever compared against `axis_origin_corner` / `axis_start_index` in the shared
contract — the values both groups actually signed off.

A peer shipping `bottomleft` would compute `N` as `(+1, 0)` where we compute
`(-1, 0)`. Every move mirrors. That does not fail loudly; it produces a
plausible game that is silently the wrong one. Reading the field turns a
silent logical divergence into a startup error.
"""

import json
from dataclasses import replace

import pytest

from engine.actions import Action, action_delta
from engine.config import load_config

SHARED = "config/game.json"


def _written(tmp_path, **board):
    payload = json.loads(open(SHARED, encoding="utf-8").read())
    payload["board_and_agents"].update(board)
    path = tmp_path / "game.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_the_shipped_contract_states_the_convention_we_implement():
    config = load_config(SHARED)

    assert config.axis_origin_corner == "topleft"
    assert config.axis_start_index == 0


def test_north_decreases_the_row_which_is_what_topleft_means():
    """The assumption the config value is being checked against."""
    assert action_delta(Action.N) == (-1, 0)
    assert action_delta(Action.S) == (1, 0)


def test_a_different_origin_corner_is_refused_at_load(tmp_path):
    with pytest.raises(ValueError, match="axis_origin_corner"):
        load_config(_written(tmp_path, axis_origin_corner="bottomleft"))


def test_a_different_start_index_is_refused_at_load(tmp_path):
    with pytest.raises(ValueError, match="axis_start_index"):
        load_config(_written(tmp_path, axis_start_index=1))


def test_the_error_explains_the_consequence_not_just_the_mismatch(tmp_path):
    """A bare 'invalid value' would leave the reader to guess why it matters."""
    with pytest.raises(ValueError) as raised:
        load_config(_written(tmp_path, axis_origin_corner="bottomleft"))

    assert "mirror" in str(raised.value).lower()
