"""Email the end-of-series result (Rulebook 9.3).

Two properties matter more than delivery itself:

* **Mutual agreement is a precondition.** A result is only reported when
  ``mutual_agreement.confirmed`` is literally True — that flag is written only
  after both peers' independent engines agreed on every turn, so reporting an
  unagreed result would launder a divergence into a submission.
* **A missing credential must never break CI.** With no token the reporter
  writes a draft artifact and returns True. The draft is what stops that being
  indistinguishable from a real send: there is always a file on disk saying
  exactly what would have gone out.

This module holds the POLICY. Message construction lives in
``reporting.mime_report`` — the report is a multipart message carrying the
result as an ``application/json`` attachment (Rulebook 34 / 9.3.3), and
keeping that separate is what keeps this file under the line limit.
"""

import json
import logging
import os

from reporting.gmail_transport import SCOPE, TOKEN_FILE, gmail_send
from reporting.mime_report import attachment_json, build_message, summary_text

DEFAULT_RECIPIENT = "rmisegal+uoh26finalgame@gmail.com"
MODES = ("auto", "draft", "send")
_LOG = logging.getLogger(__name__)


def mutual_agreement_confirmed(result: dict) -> bool:
    """True only when the result records a confirmed mutual agreement."""
    agreement = result.get("mutual_agreement")
    return isinstance(agreement, dict) and agreement.get("confirmed") is True


def message_text(message) -> str:
    """Everything the message conveys, as readable text, for the draft.

    The body alone is no longer the report — it is a summary pointing at an
    attachment. A draft holding only that would record that a send was
    attempted while losing the result it was attempting to send, so the
    decoded attachment is appended and the draft stays complete evidence.
    """
    return f"{summary_text(message)}\n\n{attachment_json(message)}"


def _write_draft(message, draft_dir: str, uid: str, reason: str) -> str:
    """Persist what WOULD have been sent, so a fallback leaves evidence."""
    os.makedirs(draft_dir, exist_ok=True)
    path = os.path.join(draft_dir, f"email_draft_{uid}.txt")
    with open(path, "w", encoding="utf-8") as draft:
        draft.write(f"# not sent: {reason}\n")
        draft.write(f"To: {message['To']}\nSubject: {message['Subject']}\n\n")
        draft.write(message_text(message))
    _LOG.warning("gmail unavailable (%s); wrote draft to %s", reason, path)
    return path


def send_game_report(
    result_json_path: str,
    recipient: str = DEFAULT_RECIPIENT,
    config_mode: str = "auto",
    draft_dir: str = "logs",
    token_path: str = TOKEN_FILE,
) -> bool:
    """Report one series. Returns whether the report was handled successfully.

    ``auto`` sends when credentials exist and drafts otherwise; ``draft`` never
    contacts Google; ``send`` requires a real send and reports failure rather
    than quietly drafting, so a required delivery cannot be missed silently.
    """
    if config_mode not in MODES:
        raise ValueError(f"config_mode must be one of {MODES}: {config_mode!r}")
    try:
        with open(result_json_path, encoding="utf-8") as handle:
            result = json.load(handle)
    except (OSError, ValueError) as error:
        _LOG.error("cannot read result %s: %s", result_json_path, error)
        return False

    if not mutual_agreement_confirmed(result):
        _LOG.error("refusing to report %s: mutual agreement not confirmed",
                   result_json_path)
        return False

    message = build_message(result, recipient)
    uid = result.get("game_uid", "unknown")
    if config_mode == "draft":
        _write_draft(message, draft_dir, uid, "draft mode requested")
        return True
    try:
        return bool(gmail_send(message, token_path))
    except Exception as error:
        if config_mode == "send":
            _LOG.error("send mode required delivery but failed: %s", error)
            return False
        _write_draft(message, draft_dir, uid, f"{type(error).__name__}: {error}")
        return True
