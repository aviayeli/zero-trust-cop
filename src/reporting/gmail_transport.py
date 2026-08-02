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

SCOPE = "https://www.googleapis.com/auth/gmail.send"
TOKEN_FILE = "token.json"
CREDENTIALS_FILE = "credentials.json"


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


def gmail_send(message, token_path: str = TOKEN_FILE) -> bool:
    """Send one MIME message through the Gmail API.

    Raises rather than returning False, so the caller can distinguish "no
    credentials" (draft instead) from "the API refused" (a real failure).
    """
    from googleapiclient.discovery import build

    credentials = _load_credentials(token_path)
    service = build("gmail", "v1", credentials=credentials)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return True
