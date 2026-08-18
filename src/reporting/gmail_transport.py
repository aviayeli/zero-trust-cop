"""The Google-specific half of reporting, isolated behind one function.

The Google client libraries are an OPTIONAL dependency: they are imported
inside ``gmail_send`` rather than at module scope, so importing the reporter —
and therefore collecting the test suite — works on a machine that has never
installed them. That is what lets every test patch this one seam instead of
faking a package tree.

Scope is ``gmail.send`` only: it cannot read a mailbox. A reporter has no
business holding read access.
"""

import base64
import os
import time

SCOPE = "https://www.googleapis.com/auth/gmail.send"
TOKEN_FILE = "token.json"
CREDENTIALS_FILE = "credentials.json"
SHARED_CONTRACT = "config/game.json"


def _load_credentials(token_path: str):
    """Load stored OAuth credentials, refreshing them when they have expired.

    Raises FileNotFoundError when no token exists — the caller decides whether
    that is fatal or a reason to draft.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not os.path.exists(token_path):
        raise FileNotFoundError(f"no OAuth token at {token_path}")
    credentials = Credentials.from_authorized_user_file(token_path, [SCOPE])
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if not credentials.valid:
        raise PermissionError("stored OAuth credentials are not usable")
    return credentials


def _send_once(message, token_path: str) -> bool:
    """One delivery attempt, with no retry policy of its own."""
    from googleapiclient.discovery import build

    credentials = _load_credentials(token_path)
    service = build("gmail", "v1", credentials=credentials)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return True


def gmail_send(
    message,
    token_path: str = TOKEN_FILE,
    retries: int | None = None,
    backoff_sec: float | None = None,
    _transport=_send_once,
    _sleeper=time.sleep,
) -> bool:
    """Send one MIME message through the Gmail API, retrying transient faults.

    Raises rather than returning False, so the caller can distinguish "no
    credentials" (draft instead) from "the API refused" (a real failure).

    A momentary 503 used to abort straight to a draft. The retry policy is the
    one the shared contract already names — ``retry_backoff_sec`` and
    ``max_retries`` — rather than numbers invented here.

    A missing or unusable CREDENTIAL is never retried: that is a decision, not
    a hiccup, and retrying it only delays the draft the caller wants.
    """
    policy = _retry_policy(retries, backoff_sec)
    for attempt in range(policy[0] + 1):
        try:
            return _transport(message, token_path)
        except (FileNotFoundError, PermissionError):
            raise
        except Exception:
            if attempt == policy[0]:
                raise
            _sleeper(policy[1] * 2**attempt)


def _retry_policy(retries, backoff_sec) -> tuple:
    """(max_retries, backoff_sec), defaulting to the agreed contract."""
    if retries is not None and backoff_sec is not None:
        return retries, backoff_sec
    from engine.config import load_config

    config = load_config(SHARED_CONTRACT)
    return (
        config.max_retries if retries is None else retries,
        config.retry_backoff_sec if backoff_sec is None else backoff_sec,
    )
