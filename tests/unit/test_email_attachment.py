"""Rule 34 / 9.3.3: the result travels as an attachment, never as body text.

The previous message pasted the serialised result into a text/plain body.
That is what this suite exists to make impossible again: a body assertion
alone would pass the moment someone "helpfully" appends the JSON back for
readability, so the body is pinned as brace-free and the payload is required
to live in a part with its own filename and MIME type.

Nothing here touches Google. Construction is a pure function of the result
dict, which is exactly why it can be pinned this tightly.
"""

import json
from email.mime.multipart import MIMEMultipart

import pytest

from reporting import email_sender as sender
from reporting.mime_report import (
    attachment_filename,
    attachment_json,
    build_message,
    summary_text,
)

RESULT = {
    "game_uid": "aviayeli",
    "github_commit": "abc123",
    "mutual_agreement": {"confirmed": True, "turns_cross_checked": 5},
    "games": [{"game_number": 1, "terminal_reason": "capture"}],
}


@pytest.fixture
def message():
    return build_message(RESULT, "someone@example.com")


def _parts(message):
    return [part for part in message.walk() if not part.is_multipart()]


# --- the envelope ------------------------------------------------------------

def test_the_message_is_a_multipart_container(message):
    assert isinstance(message, MIMEMultipart)
    assert message.get_content_type() == "multipart/mixed"


def test_the_headers_still_address_the_report(message):
    assert message["To"] == "someone@example.com"
    assert message["From"] == "me"
    assert "aviayeli" in message["Subject"]


def test_it_has_exactly_two_parts_a_body_and_an_attachment(message):
    types = [part.get_content_type() for part in _parts(message)]

    assert types == ["text/plain", "application/json"]


# --- the attachment ----------------------------------------------------------

def test_the_result_is_attached_as_application_json(message):
    attachment = [
        part for part in _parts(message)
        if part.get_content_type() == "application/json"
    ]

    assert len(attachment) == 1, "exactly one JSON attachment, or it is ambiguous"


def test_the_attachment_is_named_for_the_game(message):
    part = next(
        p for p in _parts(message) if p.get_content_type() == "application/json"
    )

    assert part.get_filename() == "result_aviayeli.json"
    assert part.get("Content-Disposition", "").startswith("attachment")


def test_the_filename_follows_the_result_artifact_convention():
    assert attachment_filename("aviayeli") == "result_aviayeli.json"


def test_the_payload_round_trips_to_the_original_result(message):
    assert json.loads(attachment_json(message)) == RESULT


def test_the_payload_is_base64_encoded_on_the_wire(message):
    """A raw utf-8 payload would be corrupted by any transfer that folds lines."""
    part = next(
        p for p in _parts(message) if p.get_content_type() == "application/json"
    )

    assert part["Content-Transfer-Encoding"] == "base64"
    assert "mutual_agreement" not in part.get_payload(), "payload is not encoded"


# --- the body must NOT be the report ----------------------------------------

def test_the_body_does_not_contain_the_serialised_result(message):
    body = summary_text(message)

    assert json.dumps(RESULT, indent=2, sort_keys=True) not in body
    assert "turns_cross_checked" not in body
    assert "{" not in body, "a brace in the body means JSON crept back in"


def test_the_body_points_at_the_attachment_instead(message):
    body = summary_text(message)

    assert "result_aviayeli.json" in body
    assert body.startswith("zero-trust match report")


def test_the_body_is_readable_not_base64(message):
    assert "aviayeli" in summary_text(message)


# --- the draft fallback still records everything -----------------------------

def test_the_draft_text_carries_both_the_summary_and_the_payload(message):
    """The draft is the evidence artifact; dropping the JSON would gut it."""
    text = sender.message_text(message)

    assert summary_text(message) in text
    assert "turns_cross_checked" in text
    assert json.loads(text.split("\n\n")[-1])["game_uid"] == "aviayeli"


# --- a result with no uid must still produce a valid message -----------------

def test_a_result_without_a_uid_still_attaches_something_nameable():
    message = build_message({"mutual_agreement": {"confirmed": True}}, "a@b.c")
    part = next(
        p for p in _parts(message) if p.get_content_type() == "application/json"
    )

    assert part.get_filename() == "result_unknown.json"


# --- both settlement digests, when an off-the-wire one exists (PRD 20) -------

_OFFICIAL = {
    "sha256": "c39d331ce8c45e30823baf2aeae58053020836542aa6e14d584fa2a58af23ee6",
    "confirmed": True,
    "official_settlement": {
        "sha256": "5077306a3703467941ce7593bcf805a022c9f162588acc4f3feca97a045b0373",
        "byte_length": 3997,
        "serialization": "json.dumps(scope, sort_keys=True, ensure_ascii=False)",
        "method": "independent derivation from our own artifacts, digests compared",
        "channel": "off-the-wire settlement, not earned at submit_audit",
    },
}


def _with_official():
    result = dict(RESULT, mutual_agreement=_OFFICIAL)
    return summary_text(build_message(result, "grader@example.com"))


def test_the_body_states_the_official_digest_when_one_exists():
    """The opponent's report quotes the OFFICIAL digest. A body quoting only
    the historical one reads to a grader as two teams disagreeing about the
    same series, which is exactly what settling it was meant to prevent."""
    body = _with_official()

    assert _OFFICIAL["official_settlement"]["sha256"] in body
    assert "3997" in body


def test_the_body_still_states_the_historical_digest():
    """Both are real. The official one supersedes for reporting; the
    historical one stays on the record and is not quietly dropped."""
    assert _OFFICIAL["sha256"] in _with_official()


def test_the_official_line_keeps_the_body_brace_free():
    assert "{" not in _with_official()


def test_a_result_without_an_official_settlement_is_unchanged():
    """Every series settled the normal way must render exactly as before."""
    body = summary_text(build_message(RESULT, "grader@example.com"))

    assert "official settlement" not in body.lower()
