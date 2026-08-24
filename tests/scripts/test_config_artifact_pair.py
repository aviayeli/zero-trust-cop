"""The config snapshot must name the pair that actually played (PRD_10 10.22).

`_stamp_config` copies the shared contract into the artifact so the file
records what the match RAN under. It copies `agreed_between` verbatim — and
ours still reads `["aviayeli", "groupb"]`, a placeholder from an earlier
phase. So a series against rstabcde ships a config artifact declaring a match
against groupb, beside a log and a result that both name rstabcde.

Nothing hashes `agreed_between`, so this was never a tamper risk. It is worse
in a quieter way: the four files stop agreeing with each other, and the one
that disagrees is the one describing the contract.

The pair is stamped from the ids the run actually derived, so it cannot
disagree with the filenames it sits beside.
"""

import json
from pathlib import Path

import pytest


@pytest.fixture
def stamped(tmp_path):
    from scripts.match_log import _stamp_config

    path = _stamp_config("config", str(tmp_path), "suffix", "some-uid",
                         pair=["aviayeli", "rstabcde"])
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_the_snapshot_names_the_pair_that_played(stamped):
    assert stamped["agreed_between"] == ["aviayeli", "rstabcde"]


def test_the_pair_is_sorted_so_both_sides_write_the_same_bytes(tmp_path):
    from scripts.match_log import _stamp_config

    path = _stamp_config("config", str(tmp_path), "s", "u",
                         pair=["rstabcde", "aviayeli"])

    assert json.loads(Path(path).read_text())["agreed_between"] == \
        ["aviayeli", "rstabcde"]


def test_the_uid_is_still_stamped(stamped):
    assert stamped["game_uid"] == "some-uid"


def test_without_a_pair_the_shipped_contract_is_copied_verbatim(tmp_path):
    """The native path passes no pair; it must be unchanged."""
    from scripts.match_log import _stamp_config

    path = _stamp_config("config", str(tmp_path), "s", "u")
    shipped = json.loads(Path("config/game.json").read_text(encoding="utf-8"))

    assert json.loads(Path(path).read_text())["agreed_between"] == \
        shipped["agreed_between"]
