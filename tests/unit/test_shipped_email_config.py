"""The SHIPPED [email] block must survive a machine with no Google credentials.

The graded run happens on someone else's laptop. ``mode = "send"`` there is a
guaranteed failure — it requires a real delivery and reports failure rather
than drafting — and ``mode = "draft"`` guarantees the opposite failure: it
never even tries. ``auto`` is the only setting that both attempts a real send
and still leaves a valid artifact behind when the credentials are absent.

This is a configuration test on purpose. The behaviour of each mode is covered
in ``test_email_fallback.py``; what is asserted here is which mode the repo
actually ships, because that is the part a grader inherits.
"""

import pytest

from mcp_server.repos import load_email_settings
from reporting.email_sender import DEFAULT_RECIPIENT

PEER_ROLES = ("police", "thief")


@pytest.mark.parametrize("role", PEER_ROLES)
def test_the_shipped_mode_falls_back_instead_of_failing(role):
    assert load_email_settings(role)["mode"] == "auto"


@pytest.mark.parametrize("role", PEER_ROLES)
def test_the_shipped_recipient_is_the_course_inbox(role):
    assert load_email_settings(role)["recipient"] == DEFAULT_RECIPIENT


def test_both_peers_agree_on_where_the_report_goes():
    """The reporter reads ONE peer's block, so a disagreement would be silent."""
    police, thief = (load_email_settings(role) for role in PEER_ROLES)

    assert police == thief
