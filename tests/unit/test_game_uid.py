"""The four artifacts carry the league's DERIVED match ids, and agree on them.

Two findings, one file:

* R3 (ours): all four artifacts must carry the SAME ``game_uid``. The audit
  found only two of the four carried any identifier, and
  ``config_<uid>_gNN.json`` carried none -- a submission set whose parts
  cannot be tied together is not auditable as a set.
* The league interop kit's: the ids must be DERIVED, and the group pair
  SORTED. We previously passed our own group name in as the ``game_id``, so
  each side of a match named the artifacts after itself: one match produced
  two sets of filenames, and two final reports that cannot be joined by
  ``game_id`` at all. The uid must come from the extracted TERMS, not from the
  whole ``game.json`` -- that variant is self-consistent across our own four
  files and fails only the cross-team join, silently.
"""

import json
from pathlib import Path

import pytest

from mcp_server import interop
from mcp_server.terms import opponent_of, terms_from_config
from scripts.match_log import ARTIFACT_KINDS, write_artifacts

GROUP = "aviayeli"


@pytest.fixture
def history():
    return [{
        "turn": 0,
        "submissions": [],
        "result": {"cop_position": (0, 1), "thief_position": (3, 3),
                   "captured": False, "turn_count": 1, "is_terminated": True,
                   "terminal_reason": "capture"},
    }]


@pytest.fixture
def config():
    return json.loads(Path("config/game.json").read_text(encoding="utf-8"))


@pytest.fixture
def expected(config):
    opponent = opponent_of(config, GROUP)
    return {
        "game_id": interop.game_id(GROUP, opponent),
        "game_uid": interop.game_uid(terms_from_config(config), GROUP, opponent),
    }


@pytest.fixture
def written(tmp_path, history):
    paths = write_artifacts(tmp_path, 3, history,
                            group_id=GROUP, config_root="config")
    return {kind: (Path(path), json.loads(Path(path).read_text()))
            for kind, path in paths.items()}


def test_all_four_artifacts_are_written(written):
    assert set(written) == set(ARTIFACT_KINDS) == {
        "declaration", "config", "log", "result"
    }


@pytest.mark.parametrize("kind", ["declaration", "config", "log", "result"])
def test_every_artifact_carries_the_derived_game_uid(written, kind, expected):
    assert written[kind][1]["game_uid"] == expected["game_uid"]


def test_the_uid_is_uniform_across_the_whole_set(written):
    uids = {payload["game_uid"] for _, payload in written.values()}

    assert len(uids) == 1, f"artifacts disagree on game_uid: {uids}"


def test_the_uid_is_a_uuid_derived_from_the_terms(written, expected, config):
    """Not our group name, and not a hash of the whole config."""
    uid = written["log"][1]["game_uid"]

    assert uid == expected["game_uid"]
    assert uid != GROUP
    assert uid != interop.game_uid(config, GROUP, opponent_of(config, GROUP))


def test_the_filenames_are_named_after_the_sorted_pair(written, expected):
    """Both peers derive one identical set of filenames with no round-trip."""
    game_id = expected["game_id"]

    assert written["declaration"][0].name == f"declaration_{game_id}.json"
    assert written["config"][0].name == f"config_{game_id}_g03.json"
    assert written["log"][0].name == f"log_{game_id}_g03.json"
    assert written["result"][0].name == f"result_{game_id}.json"


def test_the_game_id_sorts_the_pair_rather_than_naming_us_first(expected):
    assert expected["game_id"] == "aviayeli-vs-groupb"
    assert not expected["game_id"].startswith(f"{GROUP}-vs-{GROUP}")


def test_the_legacy_game_id_field_is_retained_where_it_already_existed(
    written, expected
):
    """game_id was the prior name; dropping it would break existing readers."""
    assert written["log"][1]["game_id"] == expected["game_id"]
    assert written["result"][1]["game_id"] == expected["game_id"]


def test_the_config_snapshot_keeps_the_shared_contract_intact(written):
    """Stamping identity must not corrupt the config it is snapshotting."""
    snapshot = written["config"][1]

    assert snapshot["board_and_agents"]["grid_size"] == 7
    assert snapshot["movement_and_barriers"]["max_moves"] == 35
    assert snapshot["pheromones"]["pheromone_grid_size"] == 5


def test_an_explicit_opponent_overrides_the_configured_pair(tmp_path, history):
    """A league match against someone the shipped contract does not name."""
    paths = write_artifacts(tmp_path, 1, history, group_id=GROUP,
                            config_root="config", opponent_id="team-aleph")

    assert Path(paths["log"]).name == "log_aviayeli-vs-team-aleph_g01.json"


def test_an_unknown_group_is_a_setup_error(tmp_path, history):
    """Deriving against the wrong pair yields a uid the opponent never sees."""
    with pytest.raises(ValueError, match="agreed_between"):
        write_artifacts(tmp_path, 1, history, group_id="not-a-party",
                        config_root="config")
