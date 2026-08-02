"""The send path and the graceful fallback, with every Google call mocked.

The fallback contract is the point: a missing token must never break CI, and
must never be indistinguishable from a real send either — hence the draft
artifact, which records exactly why nothing went out.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from reporting import email_sender as sender


@pytest.fixture
def result_path(tmp_path):
    payload = {
        "game_uid": "ztc001",
        "mutual_agreement": {"confirmed": True, "turns_cross_checked": 5},
        "games": [{"game_number": 1, "terminal_reason": "capture"}],
    }
    path = tmp_path / "result_ztc001.json"
    path.write_text(json.dumps(payload, indent=2))
    return path


def _drafts(tmp_path):
    return sorted(Path(tmp_path).glob("**/email_draft_*.txt"))


# --- the real send path, fully mocked ---------------------------------------

def test_a_real_send_is_attempted_when_credentials_exist(tmp_path, result_path):
    with patch.object(sender, "gmail_send", return_value=True) as gmail:
        ok = sender.send_game_report(
            str(result_path), recipient="x@y.z",
            config_mode="send", draft_dir=str(tmp_path),
        )

    assert ok is True
    gmail.assert_called_once()
    assert gmail.call_args.args[0]["To"] == "x@y.z"


def test_send_mode_reports_failure_rather_than_silently_drafting(
    tmp_path, result_path
):
    """'send' means send; masking a failure as success would hide a miss."""
    with patch.object(sender, "gmail_send", side_effect=RuntimeError("no creds")):
        ok = sender.send_game_report(
            str(result_path), config_mode="send", draft_dir=str(tmp_path)
        )

    assert ok is False


# --- graceful fallback: CI must never break ---------------------------------

def test_missing_credentials_fall_back_to_a_draft_and_still_return_true(
    tmp_path, result_path
):
    with patch.object(sender, "gmail_send", side_effect=FileNotFoundError("token.json")):
        ok = sender.send_game_report(
            str(result_path), config_mode="auto", draft_dir=str(tmp_path)
        )

    assert ok is True, "a missing token must not break the pipeline"
    assert len(_drafts(tmp_path)) == 1


def test_draft_mode_never_calls_google_at_all(tmp_path, result_path):
    with patch.object(sender, "gmail_send") as gmail:
        ok = sender.send_game_report(
            str(result_path), config_mode="draft", draft_dir=str(tmp_path)
        )

    gmail.assert_not_called()
    assert ok is True
    assert len(_drafts(tmp_path)) == 1


def test_the_draft_contains_the_whole_report(tmp_path, result_path):
    with patch.object(sender, "gmail_send", side_effect=FileNotFoundError()):
        sender.send_game_report(str(result_path), draft_dir=str(tmp_path))

    text = _drafts(tmp_path)[0].read_text()
    assert sender.DEFAULT_RECIPIENT in text
    assert "ztc001" in text and "mutual_agreement" in text


def test_a_missing_result_file_fails_without_raising(tmp_path):
    ok = sender.send_game_report(str(tmp_path / "nope.json"), draft_dir=str(tmp_path))

    assert ok is False


def test_an_unknown_mode_is_rejected(tmp_path, result_path):
    with pytest.raises(ValueError):
        sender.send_game_report(
            str(result_path), config_mode="teleport", draft_dir=str(tmp_path)
        )


# --- post-game integration ---------------------------------------------------

def test_the_harness_trigger_reads_config_and_reports(tmp_path, result_path, capsys):
    """Regression: the trigger once referenced an undefined constant.

    Unit-testing send_game_report could not catch that — only exercising the
    harness's own wiring does.
    """
    from scripts.run_local_mcp_match import _report_by_email

    with patch("scripts.run_local_mcp_match.send_game_report",
               return_value=True) as reporter:
        _report_by_email(str(result_path), None, str(tmp_path))

    reporter.assert_called_once()
    assert reporter.call_args.kwargs["recipient"] == sender.DEFAULT_RECIPIENT
    assert reporter.call_args.kwargs["config_mode"] in sender.MODES
    assert "email_report=ok" in capsys.readouterr().out


def test_the_harness_trigger_announces_a_failure(tmp_path, result_path, capsys):
    from scripts.run_local_mcp_match import _report_by_email

    with patch("scripts.run_local_mcp_match.send_game_report", return_value=False):
        _report_by_email(str(result_path), None, str(tmp_path))

    assert "email_report=FAILED" in capsys.readouterr().out
