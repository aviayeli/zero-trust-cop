"""The shared contract must still load when a peer omits our extension.

`config/game.json` is stamped `agreed_between: ["aviayeli", "groupb"]`. Phase 9
added `barrier_seed` to it as a REQUIRED key, so `load_config` raised KeyError
on the very schema both groups signed off — a cross-group match could not even
start. That is the failure mode a loopback test can never surface, because
both local peers read the same file (audit T-1).

The key is now an optional extension: absent means a bare board, which is
exactly the pre-Phase-9 behaviour and is what a peer that never heard of it
will play.
"""

import json

import pytest

from engine.config import load_config

SHARED = "config/game.json"


@pytest.fixture
def spec_config(tmp_path):
    """The agreed contract as a peer without our extension would send it."""
    payload = json.loads(open(SHARED, encoding="utf-8").read())
    del payload["movement_and_barriers"]["barrier_seed"]
    path = tmp_path / "game.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_a_config_without_our_extension_still_loads(spec_config):
    """A KeyError here is a technical loss before turn 0."""
    assert load_config(spec_config).barrier_seed is None


def test_an_absent_seed_means_a_bare_board(spec_config):
    """Absent must mean what the opposing peer will actually play."""
    from engine.barriers import barrier_layout

    assert barrier_layout(load_config(spec_config)) == frozenset()


def test_an_explicit_null_is_honoured_the_same_way(tmp_path):
    payload = json.loads(open(SHARED, encoding="utf-8").read())
    payload["movement_and_barriers"]["barrier_seed"] = None
    path = tmp_path / "game.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert load_config(str(path)).barrier_seed is None


def test_the_schema_version_records_the_extension():
    """A new field without a version bump is an undeclared schema change."""
    payload = json.loads(open(SHARED, encoding="utf-8").read())

    assert payload["schema_version"] == "1.3"


def test_every_other_key_is_still_required(tmp_path):
    """Optional-by-default must not spread: a missing core key stays fatal."""
    payload = json.loads(open(SHARED, encoding="utf-8").read())
    del payload["movement_and_barriers"]["max_barriers"]
    path = tmp_path / "game.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(KeyError):
        load_config(str(path))
