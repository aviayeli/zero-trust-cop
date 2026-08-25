"""The post-game tail: where artifacts land, and where the result is sent.

Split out of ``run_local_mcp_match`` to keep that module under the 150-line
limit. Reporting is a genuinely separate concern from driving a match: it runs
only after the wire has gone quiet, and it must not be able to fail the match
it is reporting on.
"""

import json

from mcp_server.repos import load_email_settings
from reporting.email_sender import send_game_report

# Both peers' [email] blocks are identical; read one of them.
_REPORTING_ROLE = "police"


def group_id(config_root=None):
    """The group directory logs land in, from the published declaration."""
    root = config_root or "config"
    with open(f"{root}/declaration.json") as declared:
        return json.load(declared)["group_name"]


def report_by_email(result_path, config_root, logs_dir, mode=None):
    """Post-game step: email the result, or leave a draft if it cannot send.

    ``mode`` overrides the peer's configured ``[email] mode`` for ONE run.
    Absent it the config still decides, so the shipped ``auto`` keeps
    governing CI and local play -- where a missing credential must never
    break the suite. A GRADED series passes ``send``, which reports a failure
    rather than writing a draft nobody looks for.
    """
    settings = load_email_settings(_REPORTING_ROLE, config_root)
    chosen = mode or settings["mode"]
    handled = send_game_report(
        result_path,
        recipient=settings["recipient"],
        config_mode=chosen,
        draft_dir=logs_dir,
    )
    print(f"email_report={'ok' if handled else 'FAILED'} mode={chosen}")
