"""...and is never mistaken for a settled one (PRD_13 FR2-FR3, FR5).

Split from `test_unsettled_subgame` at the 150-line limit; the seam is real.
That module asks whether the sub-game survives its own audit. This asks
whether the surviving record can ever be read as a verdict it never got --
which is the half that would corrupt a submission rather than lose one.
"""

import json

from unsettled import as_result, config, play_closing, unsettled  # noqa: F401

from reporting.email_sender import send_game_report
from scripts.reference_artifacts import _accepted


def test_the_absent_verdict_names_the_cause_and_is_not_a_refusal(config):
    """`refused` and `unreachable` are opposite claims about who is at fault:
    they rejected our chain, versus they were not there to see it."""
    verdict = unsettled(config)["their_audit_response"]

    assert verdict["status"] == "unreachable"
    assert verdict["accepted"] is False
    assert "502" in verdict["reason"]


def test_an_unsettled_sub_game_is_not_accepted(config):
    """`_accepted` reads three spellings of yes; none may match this."""
    assert not _accepted(unsettled(config)["their_audit_response"])


def test_a_result_built_from_it_confirms_no_mutual_agreement(config):
    result = as_result(unsettled(config))

    assert result["mutual_agreement"]["confirmed"] is False


def test_the_reporter_refuses_an_unsettled_result(config, tmp_path):
    """End to end: an unsettled sub-game must never be emailed as a result.
    That would launder a game nobody verified into a submission."""
    path = tmp_path / "result.json"
    path.write_text(json.dumps(as_result(unsettled(config))), encoding="utf-8")

    assert send_game_report(str(path), draft_dir=str(tmp_path)) is False


def test_a_successful_audit_is_exactly_what_it_is_today(config):
    """The guard on the whole phase: this must be invisible to a healthy run."""
    _, summary = play_closing(config)

    assert summary["their_audit_response"] == {"status": "accepted",
                                               "records_verified": 1}
    assert sorted(summary) == ["our_chain", "result_claim", "steps",
                               "terminal_reason", "their_audit_response",
                               "their_turns"]
