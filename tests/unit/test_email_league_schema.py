"""The submitted email must match what the league schema declares (PRD_16).

Two defects found while holding the graded submission, both in the metadata
around a payload that was itself correct.

The attachment was named from ``game_uid`` while the schema states plainly
that "every actual file name MUST be derived from the game_id". Our own report
declares ``links.result: result_aviayeli-vs-bb-ai-12.json`` and we were
attaching ``result_521727a1-....json`` — a submission contradicting its own
manifest, which is exactly what an automatic validator is built to catch.

And the summary counted ``result["games"]``, a key the league schema does not
have, so a six-sub-game series reported "games in series: 0" with an unknown
commit. The attachment was right and the covering note was false.

Driven by the real graded artifact.
"""

import json

import pytest

from reporting.mime_report import (
    attachment_filename, build_message, summary_text,
)

GRADED = "logs/evidence/graded_series/result_aviayeli-vs-bb-ai-12.json"


@pytest.fixture(scope="module")
def league():
    """The graded result, in league schema."""
    from scripts.league_result import league_result

    with open(GRADED) as handle:
        ours = json.load(handle)
    logs = []
    for number in range(1, 7):
        name = (f"logs/evidence/graded_series/"
                f"log_aviayeli-vs-bb-ai-12_g{number:02d}.json")
        with open(name) as handle:
            logs.append(json.load(handle))
    return league_result(ours, logs)


@pytest.fixture(scope="module")
def message(league):
    return build_message(league, "rmisegal+uoh26finalgame@gmail.com")


# --- the filename the schema mandates --------------------------------------


def test_the_attachment_is_named_from_the_game_id(message, league):
    """`<role>_<game_id>.json`, per the schema's own remark."""
    attached = [p.get_filename() for p in message.walk() if p.get_filename()]

    assert attached == [f"result_{league['game_id']}.json"]
    assert attached == ["result_aviayeli-vs-bb-ai-12.json"]


def test_the_attachment_matches_what_the_report_declares(message, league):
    """A submission must not contradict its own manifest."""
    attached = next(p.get_filename() for p in message.walk() if p.get_filename())

    assert attached == league["links"]["result"]


def test_the_uid_is_no_longer_used_for_the_filename(league):
    assert attachment_filename(league["game_id"]) != \
        f"result_{league['game_uid']}.json"


# --- the summary must describe the series it is attached to ----------------


def test_the_summary_counts_all_six_sub_games(message):
    assert "sub-games in series: 6" in summary_text(message)


def test_the_summary_carries_our_real_commit(message, league):
    ours = next(sha for sha in league["sub_games"][0]["github_commit"].values()
                if sha != "declared-in-their-own-report")
    body = summary_text(message)

    assert ours in body
    assert "unknown" not in body


def test_the_summary_reports_the_agreed_outcome(message, league):
    body = summary_text(message)

    assert "mutual agreement confirmed: True" in body
    assert league["mutual_agreement"]["sha256"][:16] in body


# --- and the rule that zeroes a submission still holds ---------------------


def test_the_body_still_carries_no_serialised_result(message):
    """The requirement that disqualifies on sight: JSON belongs in the
    attachment, never in the body."""
    body = summary_text(message)

    assert "{" not in body and "}" not in body


def test_the_result_is_still_an_application_json_attachment(message):
    kinds = [p.get_content_type() for p in message.walk() if not p.is_multipart()]

    assert kinds == ["text/plain", "application/json"]
    assert message.get_content_type() == "multipart/mixed"


# --- the older native-dialect result must not break ------------------------


def test_a_pre_league_result_still_produces_a_usable_report():
    """`run_local_mcp_match` still writes the older shape; its summary must
    keep working rather than reporting zeros."""
    old = {"game_id": "aviayeli", "game_uid": "u",
           "github_commit": "a" * 40,
           "games": [{"game_number": 1}, {"game_number": 2}],
           "mutual_agreement": {"confirmed": True}}

    body = summary_text(build_message(old, "x@y"))

    assert "sub-games in series: 2" in body
    assert "a" * 40 in body
