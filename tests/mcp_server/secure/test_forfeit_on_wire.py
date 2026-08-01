"""D7 seen from the wire: a stalled peer forfeits, and the match closes.

The compliant peer learns the match is over by polling its status; expiry
is lazy, because a stalled match produces no other traffic.
"""

import asyncio


def test_the_wire_reports_a_technical_loss_against_the_stalled_peer(
    forfeit_app, forfeit_clock, commitment_pair
):
    """The compliant peer polls status and learns the match is over."""
    police, _ = commitment_pair
    asyncio.run(forfeit_app.submit_commitment(
        "police", 0, police["h_commit"], police["signature"]))

    forfeit_clock.advance(31.0)
    status = asyncio.run(forfeit_app.get_match_status())

    assert status["is_terminated"] is True
    assert status["terminal_reason"] == "technical_loss"
    assert "thief" in status["forfeited_by"]


def test_a_forfeited_match_refuses_further_submissions(
    forfeit_app, forfeit_clock, commitment_pair
):
    police, late = commitment_pair
    asyncio.run(forfeit_app.submit_commitment(
        "police", 0, police["h_commit"], police["signature"]))
    forfeit_clock.advance(31.0)
    asyncio.run(forfeit_app.get_match_status())

    outcome = asyncio.run(forfeit_app.submit_commitment(
        "thief", 0, late["h_commit"], late["signature"]))

    assert outcome["error"] == "match_forfeited"


def test_a_live_match_is_never_reported_forfeited(forfeit_app):
    status = asyncio.run(forfeit_app.get_match_status())

    assert status["is_terminated"] is False
    assert status["terminal_reason"] is None
