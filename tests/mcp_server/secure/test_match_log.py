"""D4: the four match artifacts, written under logs/<group_id>/.

SCHEMA CAVEAT: Appendix F of police_thief_p2p.pdf is not in this repository,
so only the four FILENAMES are taken from the specification. The internal
field layout below is this project's own design and must be reconciled with
the real appendix before submission. ``declaration_<game_id>.json`` is the
exception — its schema was fixed in PRD_03 FR6 and is produced unchanged by
the existing declaration module.
"""

import json
from pathlib import Path

import pytest

from scripts.match_log import ARTIFACT_VERSION, build_log, write_artifacts


@pytest.fixture
def history(app, commitment_pair):
    """One turn's worth of match history in the shape play_match returns."""
    police, thief = commitment_pair
    return [
        {
            "turn": 0,
            "submissions": [_Sub(police), _Sub(thief)],
            "result": {
                "status": "resolved",
                "cop_position": (0, 1),
                "thief_position": (3, 3),
                "captured": False,
                "turn_count": 1,
                "is_terminated": True,
                "terminal_reason": "max_moves_reached",
            },
        }
    ]


class _Sub:
    """Stand-in with the Submission attributes the writer reads."""

    def __init__(self, data):
        for key, value in data.items():
            setattr(self, key, value)


def test_the_log_records_every_field_a_verifier_needs(history):
    log = build_log("g1", 1, history, group_id="aviayeli")

    turn = log["turns"][0]
    for role in ("police", "thief"):
        entry = turn["submissions"][role]
        assert set(entry) == {
            "h_commit", "signature", "state", "move", "intent", "nonce"
        }


def test_the_log_records_the_resolved_outcome(history):
    log = build_log("g1", 1, history, group_id="aviayeli")

    result = log["turns"][0]["result"]
    assert result["cop_position"] == [0, 1]
    assert result["captured"] is False
    assert result["terminal_reason"] == "max_moves_reached"


def test_the_log_is_self_describing(history):
    log = build_log("g1", 1, history, group_id="aviayeli")

    assert log["artifact_version"] == ARTIFACT_VERSION
    assert log["game_id"] == "g1"
    assert log["game_number"] == 1
    assert log["group_id"] == "aviayeli"


def test_the_log_is_json_serialisable(history):
    """Positions arrive as tuples and must not reach json.dump raw."""
    json.dumps(build_log("g1", 1, history, group_id="aviayeli"))


def test_all_four_artifacts_land_under_the_group_directory(tmp_path, history):
    paths = write_artifacts(
        tmp_path, "g1", 1, history, group_id="aviayeli", config_root="config"
    )

    assert set(paths) == {"declaration", "config", "log", "result"}
    for path in paths.values():
        assert Path(path).parent == tmp_path / "aviayeli"
        assert Path(path).exists()


def test_the_filenames_follow_the_required_pattern(tmp_path, history):
    paths = write_artifacts(
        tmp_path, "abc", 7, history, group_id="aviayeli", config_root="config"
    )

    assert Path(paths["declaration"]).name == "declaration_abc.json"
    assert Path(paths["config"]).name == "config_abc_g07.json"
    assert Path(paths["log"]).name == "log_abc_g07.json"
    assert Path(paths["result"]).name == "result_abc.json"


def test_the_config_artifact_snapshots_the_shared_contract(tmp_path, history):
    paths = write_artifacts(
        tmp_path, "abc", 1, history, group_id="aviayeli", config_root="config"
    )

    snapshot = json.loads(Path(paths["config"]).read_text())

    assert snapshot["board_and_agents"]["grid_size"] == 7
    assert snapshot["movement_and_barriers"]["max_moves"] == 35


def test_the_result_artifact_reports_the_outcome(tmp_path, history):
    paths = write_artifacts(
        tmp_path, "abc", 1, history, group_id="aviayeli", config_root="config"
    )

    result = json.loads(Path(paths["result"]).read_text())

    assert result["games"][0]["terminal_reason"] == "max_moves_reached"
    assert result["games"][0]["turns"] == 1
    assert result["game_id"] == "abc"


def test_writing_twice_is_byte_identical(tmp_path, history):
    """An artifact that shifts between runs cannot be defended."""
    first = write_artifacts(
        tmp_path / "a", "abc", 1, history, group_id="aviayeli", config_root="config"
    )
    second = write_artifacts(
        tmp_path / "b", "abc", 1, history, group_id="aviayeli", config_root="config"
    )

    assert Path(first["log"]).read_text() == Path(second["log"]).read_text()
