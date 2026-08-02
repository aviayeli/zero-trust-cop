"""R2: end-of-series Gmail reporting, with every Google call mocked.

No test may touch the network or a real mailbox, so the Google client is
patched at its seam in every case. The graceful-fallback contract matters
most: a missing token must never break CI, and must never silently look like
a successful send either — hence the draft artifact.
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
        "github_commit": "abc123",
        "mutual_agreement": {"confirmed": True, "turns_cross_checked": 5},
        "games": [{"game_number": 1, "terminal_reason": "capture"}],
    }
    path = tmp_path / "result_ztc001.json"
    path.write_text(json.dumps(payload, indent=2))
    return path


def _drafts(tmp_path):
    return sorted(Path(tmp_path).glob("**/email_draft_*.txt"))


# --- mutual agreement is a precondition, not decoration ----------------------

def test_a_confirmed_result_passes_the_agreement_check(result_path):
    assert sender.mutual_agreement_confirmed(json.loads(result_path.read_text()))


@pytest.mark.parametrize("value", [
    {"confirmed": False}, {}, None, "yes", {"confirmed": "true"},
])
def test_an_unconfirmed_result_fails_the_agreement_check(value):
    assert not sender.mutual_agreement_confirmed({"mutual_agreement": value})


def test_a_result_without_agreement_is_never_sent(tmp_path, result_path):
    payload = json.loads(result_path.read_text())
    payload["mutual_agreement"]["confirmed"] = False
    result_path.write_text(json.dumps(payload))

    with patch.object(sender, "gmail_send") as gmail:
        ok = sender.send_game_report(str(result_path), draft_dir=str(tmp_path))

    gmail.assert_not_called()
    assert ok is False, "an unagreed result must not report success"


# --- message construction ----------------------------------------------------

def test_the_message_is_plain_text_and_carries_the_result_json(result_path):
    body = json.loads(result_path.read_text())

    message = sender.build_message(body, "someone@example.com")

    assert message.get_content_type() == "text/plain"
    assert message["To"] == "someone@example.com"
    text = sender.message_text(message)
    assert "ztc001" in text
    assert json.loads(text.split("\n\n", 1)[1])["game_uid"] == "ztc001"


def test_the_body_is_readable_not_base64(result_path):
    """A draft full of base64 would be evidence of nothing."""
    message = sender.build_message(json.loads(result_path.read_text()), "a@b.c")

    assert sender.message_text(message).startswith("zero-trust match report")


def test_the_subject_names_the_game(result_path):
    message = sender.build_message(json.loads(result_path.read_text()), "a@b.c")

    assert "ztc001" in message["Subject"]


def test_the_default_recipient_is_the_course_address():
    assert sender.DEFAULT_RECIPIENT == "rmisegal+uoh26finalgame@gmail.com"


def test_the_scope_is_send_only():
    """gmail.send cannot read a mailbox — least privilege for a reporter."""
    assert sender.SCOPE == "https://www.googleapis.com/auth/gmail.send"
