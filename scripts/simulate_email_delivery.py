#!/usr/bin/env python3
"""TEMPORARY manual harness for Step 7: prove real Gmail delivery works.

This is not part of the engine and is not covered by tests. It fabricates a
minimal result file that satisfies the reporter's preconditions, makes sure an
OAuth token exists, and then hands off to the REAL ``send_game_report`` so that
what gets exercised is production code, not a copy of it.

Why the token bootstrap lives here: ``gmail_transport._load_credentials``
deliberately raises when ``token.json`` is absent — the library half never
opens a browser, because an unattended CI run must not block on a consent
screen. A human-run bootstrap is exactly the thing that does not belong in the
library, so it sits in this throwaway script instead.

Usage:  .venv/bin/python scripts/simulate_email_delivery.py
"""

import argparse
import importlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
RESULT_PATH = "results/result_simulation.json"
CREDENTIALS_PATH = "credentials.json"
TOKEN_PATH = "token.json"
DEFAULT_RECIPIENT = "avi.ayeli@gmail.com"
DEFAULT_MODE = "send"
GAME_UID = "aviayeli"

BANNER = """
================================================================
 Step 7 - live Gmail delivery simulation
================================================================
 A Google OAuth consent window is about to open in your browser.

   * Sign in as the account that owns this OAuth client.
   * Google will warn the app is unverified -> Advanced -> Continue.
   * Approve the single requested scope: gmail.send (send only,
     it grants NO ability to read your mailbox).
   * On success this script writes {token} in the repo root.
     That file is a bearer credential; .gitignore already blocks
     it and it must never be committed.

 If the browser does not open, copy the URL printed below into it.
================================================================
"""


def write_dummy_result(path: Path) -> dict:
    """Write the throwaway result the reporter will be asked to send."""
    result = {
        "game_uid": GAME_UID,
        "mutual_agreement": {"confirmed": True},
        "status": "simulation_test",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"[1/3] wrote dummy result -> {path}")
    return result


def ensure_token(token_path: Path, credentials_path: Path, scope: str) -> None:
    """Run the interactive OAuth flow unless a token is already on disk."""
    if token_path.exists():
        print(f"[2/3] reusing existing token at {token_path} (no browser)")
        return
    if not credentials_path.exists():
        sys.exit(
            f"missing {credentials_path}: download the OAuth client secret "
            "for a Desktop app from Google Cloud Console and save it there."
        )
    from google_auth_oauthlib.flow import InstalledAppFlow

    print(BANNER.format(token=token_path))
    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_path), [scope]
    )
    credentials = flow.run_local_server(port=0)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    os.chmod(token_path, 0o600)
    print(f"[2/3] authenticated; wrote {token_path} (mode 600)")


def load_sender():
    """Import the real reporter from src/ without installing the package."""
    sys.path.insert(0, str(SRC))
    transport = importlib.import_module("reporting.gmail_transport")
    sender = importlib.import_module("reporting.email_sender")
    print(f"      using {sender.__file__}")
    return sender.send_game_report, transport.SCOPE


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--recipient", default=DEFAULT_RECIPIENT)
    parser.add_argument(
        "--mode", default=DEFAULT_MODE, choices=("auto", "draft", "send")
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    os.chdir(ROOT)  # keep every path below relative to the repo root
    send_game_report, scope = load_sender()
    write_dummy_result(Path(RESULT_PATH))
    if args.mode == "draft":
        print("[2/3] draft mode: skipping OAuth, nothing will be sent")
    else:
        ensure_token(Path(TOKEN_PATH), Path(CREDENTIALS_PATH), scope)

    print(f"[3/3] send_game_report({RESULT_PATH!r}, {args.recipient!r}, "
          f"config_mode={args.mode!r})")
    delivered = send_game_report(
        RESULT_PATH, args.recipient, config_mode=args.mode
    )
    if delivered and args.mode == "draft":
        print(f"\nOK: drafted only. See logs/email_draft_{GAME_UID}.txt; "
              "nothing was sent.")
        return 0
    if delivered:
        print(f"\nOK: report handled. Check the inbox of {args.recipient} "
              f"for '[zero-trust] match report {GAME_UID}'.")
        return 0
    print("\nFAILED: send mode required real delivery and did not get it. "
          "The logged error above says why.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
