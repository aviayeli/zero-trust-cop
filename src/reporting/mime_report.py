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
# The opponent's commit, which only they can state. Never ours.
_THEIRS = "declared-in-their-own-report"


def attachment_filename(game_id: str) -> str:
    """``result_<game_id>.json`` -- the name the league schema mandates.

    "Every actual file name MUST be derived from the game_id so that files
    from different games are never mixed." It was derived from ``game_uid``,
    so a report declaring ``links.result: result_a-vs-b.json`` shipped an
    attachment called ``result_<uuid>.json`` -- a submission contradicting its
    own manifest, which is what an automatic validator exists to catch.
    """
    return f"result_{game_id}.json"


def _sub_games(result: dict) -> list:
    """The series rows, under either schema.

    The league calls them ``sub_games``; the native dialect's own result still
    says ``games``, and both are live -- so a summary that knew only one
    reported a six-sub-game series as zero.
    """
    return result.get("sub_games") or result.get("games") or []


def _our_commit(result: dict) -> str:
    """Our commit, from wherever this schema keeps it.

    The league schema records it per sub-game and per group, so ours is the
    one value that is not the opponent's placeholder.
    """
    if result.get("github_commit"):
        return result["github_commit"]
    for row in _sub_games(result):
        for sha in (row.get("github_commit") or {}).values():
            if sha and sha != _THEIRS:
                return sha
    return UNKNOWN_UID


def _summary(result: dict, name: str) -> str:
    """A brace-free human summary. Never a serialisation of the result."""
    agreement = result.get("mutual_agreement") or {}
    digest = agreement.get("sha256")
    lines = [
        f"zero-trust match report for game_id={result.get('game_id', name)}",
        f"game_uid: {result.get('game_uid', UNKNOWN_UID)}",
        "",
        f"mutual agreement confirmed: {bool(agreement.get('confirmed'))}",
        f"settlement sha256: {digest or 'n/a'}",
    ]
    # When a series was settled off the wire (PRD 20) the OFFICIAL digest is
    # the one the opponent's own report quotes. A body naming only the
    # historical digest reads to a grader as two teams disagreeing about one
    # series -- the exact failure settling it was meant to prevent. Both are
    # stated; neither is dropped.
    official = agreement.get("official_settlement") or {}
    if official.get("sha256"):
        lines.append(
            f"official settlement sha256: {official['sha256']} "
            f"({official.get('byte_length', 'n/a')} bytes)")
    lines += [
        f"sub-games in series: {len(_sub_games(result))}",
        f"commit: {_our_commit(result)}",
        "",
        f"The full result is attached as {name} (application/json).",
    ]
    return "\n".join(lines)


def build_message(result: dict, recipient: str) -> MIMEMultipart:
    """Return a multipart/mixed report: summary body, result as attachment."""
    game_id = result.get("game_id") or result.get("game_uid", UNKNOWN_UID)
    name = attachment_filename(game_id)
    message = MIMEMultipart()
    message["To"] = recipient
    message["From"] = "me"
    message["Subject"] = f"[zero-trust] match report {game_id}"

    message.attach(MIMEText(_summary(result, name), "plain", "utf-8"))

    payload = json.dumps(result, indent=2, sort_keys=True).encode("utf-8")
    attachment = MIMEApplication(payload, _subtype=JSON_SUBTYPE)
    attachment.add_header("Content-Disposition", "attachment", filename=name)
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
