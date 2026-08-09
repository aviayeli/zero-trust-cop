"""Compose the match report as a multipart message (Rulebook 34 / 9.3.3).

The result is an ATTACHMENT, not body text. That is a submission requirement,
but it is also the only form that survives the trip: a body is reflowed,
quoted, and line-wrapped by every client between here and the grader, so a
result pasted into one is no longer the bytes the peers agreed on. A
base64-encoded ``application/json`` part arrives byte-identical, and it lands
in the grader's filesystem under the same name the artifact has on ours.

The body is therefore a summary and nothing more. It is kept free of braces so
the "no plaintext report" rule is mechanically checkable rather than a matter
of review — see ``tests/unit/test_email_attachment.py``.
"""

import json
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

UNKNOWN_UID = "unknown"
JSON_SUBTYPE = "json"


def attachment_filename(uid: str) -> str:
    """The attachment carries the same name as the on-disk result artifact."""
    return f"result_{uid}.json"


def _summary(result: dict, uid: str) -> str:
    """A brace-free human summary. Never a serialisation of the result."""
    agreement = result.get("mutual_agreement") or {}
    games = result.get("games") or []
    return "\n".join([
        f"zero-trust match report for game_uid={uid}",
        "",
        f"mutual agreement confirmed: {bool(agreement.get('confirmed'))}",
        f"turns cross-checked: {agreement.get('turns_cross_checked', 'n/a')}",
        f"games in series: {len(games)}",
        f"commit: {result.get('github_commit', UNKNOWN_UID)}",
        "",
        f"The full result is attached as {attachment_filename(uid)} "
        "(application/json).",
    ])


def build_message(result: dict, recipient: str) -> MIMEMultipart:
    """Return a multipart/mixed report: summary body, result as attachment."""
    uid = result.get("game_uid", UNKNOWN_UID)
    message = MIMEMultipart()
    message["To"] = recipient
    message["From"] = "me"
    message["Subject"] = f"[zero-trust] match report {uid}"

    message.attach(MIMEText(_summary(result, uid), "plain", "utf-8"))

    payload = json.dumps(result, indent=2, sort_keys=True).encode("utf-8")
    attachment = MIMEApplication(payload, _subtype=JSON_SUBTYPE)
    attachment.add_header(
        "Content-Disposition", "attachment", filename=attachment_filename(uid)
    )
    message.attach(attachment)
    return message


def _first_part(message, content_type: str):
    for part in message.walk():
        if not part.is_multipart() and part.get_content_type() == content_type:
            return part
    raise ValueError(f"message carries no {content_type} part")


def summary_text(message) -> str:
    """The body part, decoded.

    MIMEText base64-encodes a utf-8 payload, so get_payload() alone would
    return an unreadable blob.
    """
    return _first_part(message, "text/plain").get_payload(decode=True).decode("utf-8")


def attachment_json(message) -> str:
    """The attached result, decoded back to the JSON text that was attached."""
    part = _first_part(message, "application/json")
    return part.get_payload(decode=True).decode("utf-8")
