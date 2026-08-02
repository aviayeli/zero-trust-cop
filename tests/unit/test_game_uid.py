"""R3: all four artifacts must carry the SAME game_uid.

The audit found only two of the four carried any identifier, and
config_<uid>_gNN.json carried none at all -- it was a verbatim copy of
game.json. A submission set whose parts cannot be tied together is not
auditable as a set.
"""

import json
from pathlib import Path

import pytest

from scripts.match_log import ARTIFACT_KINDS, write_artifacts


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
def written(tmp_path, history):
    paths = write_artifacts(tmp_path, "ztc042", 3, history,
                            group_id="groupa", config_root="config")
    return {kind: json.loads(Path(path).read_text()) for kind, path in paths.items()}


def test_all_four_artifacts_are_written(written):
    assert set(written) == set(ARTIFACT_KINDS) == {
        "declaration", "config", "log", "result"
    }


@pytest.mark.parametrize("kind", ["declaration", "config", "log", "result"])
def test_every_artifact_carries_a_game_uid(written, kind):
    assert written[kind]["game_uid"] == "ztc042"


def test_the_uid_is_uniform_across_the_whole_set(written):
    uids = {payload["game_uid"] for payload in written.values()}

    assert len(uids) == 1, f"artifacts disagree on game_uid: {uids}"


def test_the_config_snapshot_keeps_the_shared_contract_intact(written):
    """Stamping identity must not corrupt the config it is snapshotting."""
    snapshot = written["config"]

    assert snapshot["board_and_agents"]["grid_size"] == 7
    assert snapshot["movement_and_barriers"]["max_moves"] == 35
    assert snapshot["pheromones"]["pheromone_grid_size"] == 5


def test_the_legacy_game_id_is_retained_where_it_already_existed(written):
    """game_id was the prior name; dropping it would break existing readers."""
    assert written["log"]["game_id"] == "ztc042"
    assert written["result"]["game_id"] == "ztc042"
