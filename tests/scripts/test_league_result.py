"""The result must be shaped the way the league reads it (PRD_16).

`match_log.py` has carried this caveat since Phase 6: only the four FILENAMES
came from the specification, and the field layout was this project's own design
"pending reconciliation with the course appendix". Two result files from
SMNGRP05 supplied that reconciliation -- `schema_version: "1.1"`,
`report_type: "final_game_result"` -- and ours matched it nowhere that matters.
The lecturer's tooling reads `final_result.total_score` and
`sub_games[].score`; ours held the same numbers three levels down under
`mutual_agreement.consensus`.

Driven by the REAL graded artifacts, not fixtures. A translator for a
submission should be tested against the thing being submitted.
"""

import json

import pytest

from scripts.league_result import league_result

EVIDENCE = "logs/evidence/graded_series"
SCHEMA_KEYS = {"_schema", "schema_version", "report_type", "game_id",
               "game_uid", "links", "timezone", "groups", "num_sub_games",
               "sub_games", "final_result", "mutual_agreement"}


@pytest.fixture(scope="module")
def ours():
    with open(f"{EVIDENCE}/result_aviayeli-vs-bb-ai-12.json") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def logs():
    out = []
    for number in range(1, 7):
        name = f"{EVIDENCE}/log_aviayeli-vs-bb-ai-12_g{number:02d}.json"
        with open(name) as handle:
            out.append(json.load(handle))
    return out


@pytest.fixture(scope="module")
def built(ours, logs):
    return league_result(ours, logs)


# --- the shape ------------------------------------------------------------


def test_the_top_level_keys_are_the_schemas(built):
    assert set(built) == SCHEMA_KEYS


def test_it_declares_itself_as_the_league_report(built):
    assert built["report_type"] == "final_game_result"
    assert built["schema_version"] == "1.1"


def test_six_sub_games_numbered_one_to_six(built):
    assert built["num_sub_games"] == 6
    assert [row["sub_game_number"] for row in built["sub_games"]] == [1, 2, 3,
                                                                     4, 5, 6]


def test_links_derive_every_filename_from_the_game_id(built):
    game_id = built["game_id"]
    links = built["links"]

    assert links["declaration"] == f"declaration_{game_id}.json"
    assert links["result"] == f"result_{game_id}.json"
    assert links["log"] == f"log_{game_id}_g<NN>.json"
    assert links["config"] == f"config_{game_id}_g<NN>.json"


# --- the agreed hash must not move (FR2) ----------------------------------


def test_the_settlement_hash_is_carried_through_byte_identical(built, ours):
    """The one value bb-ai-12 independently confirmed. A recomputation that
    differed by a byte would break a verified cross-team agreement to satisfy
    a formatter."""
    assert built["mutual_agreement"]["sha256"] == ours["mutual_agreement"]["sha256"]
    assert built["mutual_agreement"]["confirmed"] is True


def test_the_scores_are_the_ones_the_hash_covers(built, ours):
    """FR3: every published score comes from the verified consensus rows."""
    agreed = {row["sub_game_number"]: row["score"]
              for row in ours["mutual_agreement"]["consensus"]["sub_games"]}

    for row in built["sub_games"]:
        assert row["score"] == agreed[row["sub_game_number"]]


def test_the_total_is_the_sum_of_the_rows(built):
    total = built["final_result"]["total_score"]
    for group, points in total.items():
        assert points == sum(row["score"][group] for row in built["sub_games"])


# --- honesty about what we know -------------------------------------------


def test_timestamps_come_from_real_turns_and_are_ordered(built):
    for row in built["sub_games"]:
        assert row["started_at"] and row["ended_at"]
        assert row["started_at"] <= row["ended_at"]


def test_the_opponents_commit_is_theirs_to_declare_not_ours_to_guess(built):
    """FR5, and the convention the reference files themselves use."""
    for row in built["sub_games"]:
        assert row["github_commit"]["bb-ai-12"] == "declared-in-their-own-report"
        assert len(row["github_commit"]["aviayeli"]) == 40


def test_the_audit_block_reports_what_we_actually_verified(built):
    for row in built["sub_games"]:
        audit = row["audit"]
        assert audit["log_verified"] is True
        assert audit["tampered"] is False
        assert audit["opponent_present"] is True


def test_the_timezone_is_configured_not_inlined():
    """FR8. A literal here is the hardcoded tunable the constitution bans."""
    import inspect

    from scripts import league_result as module

    with open("config/game.json") as handle:
        assert json.load(handle)["timezone"]
    assert "Asia/" not in inspect.getsource(module)
