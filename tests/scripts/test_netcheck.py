"""Can we reach their endpoint at all, and does it serve this wire (PRD_11)?

`connect_and_play` retries a failing open for the whole `--wait-minutes`
window. That is right for a launch and useless as a diagnostic: a typo in
their URL, a tunnel that is down, and a peer that is up but disagrees on
`num_games` all present as the same silence for thirty minutes.

This module covers the first two checks and, more importantly, the ORDERING:
a failed check must stop the ones after it. `test_netcheck_terms` covers the
handshake and the comparison; the shared fake lives in
`tests/_support/netcheck_peer.py`.
"""

import pytest
from netcheck_peer import (
    TOOLS, FakePeer, load_terms, run_probe, signed_reply, verdict_for,
)

from scripts import netcheck


@pytest.fixture
def our_terms():
    return load_terms()


# --- the happy path --------------------------------------------------------


def test_a_conformant_peer_passes_every_check(our_terms):
    report = run_probe(FakePeer(reply=signed_reply(our_terms)), our_terms)

    assert [check["check"] for check in report] == [
        "reachable", "surface", "handshake", "terms"]
    assert all(check["ok"] for check in report)
    assert netcheck.exit_code(report) == 0


# --- ordering: a later verdict is meaningless after an earlier failure -----


def test_an_unreachable_peer_stops_the_probe_at_the_first_check(our_terms):
    """Reporting `terms disagree` against a peer that is down is how an
    operator ends up editing a `game.json` that was already correct."""
    peer = FakePeer(opens=RuntimeError("502 Bad Gateway"))

    report = run_probe(peer, our_terms)

    assert [check["check"] for check in report] == ["reachable"]
    assert verdict_for(report, "reachable")["ok"] is False
    assert "502" in verdict_for(report, "reachable")["detail"]
    assert netcheck.exit_code(report) != 0


def test_a_missing_tool_stops_the_probe_before_the_handshake(our_terms):
    peer = FakePeer(tools=[t for t in TOOLS if t != "submit_audit"],
                    reply=signed_reply(our_terms))

    report = run_probe(peer, our_terms)

    assert [check["check"] for check in report] == ["reachable", "surface"]
    assert verdict_for(report, "surface")["ok"] is False
    assert "submit_audit" in verdict_for(report, "surface")["detail"]
    assert "negotiate" not in [call[0] for call in peer.calls]
    assert netcheck.exit_code(report) != 0


def test_every_reference_v3_tool_is_required(our_terms):
    """All four, not a subset: a peer missing `receive_control` cannot be
    told a sub-game ended, and one missing `submit_audit` cannot close one."""
    for absent in TOOLS:
        served = [tool for tool in TOOLS if tool != absent]

        assert netcheck.missing_tools(served) == (absent,)


def test_an_extra_tool_is_not_a_failure(our_terms):
    """Their surface may carry their own dialect beside this one; we require
    the four we call, not that they serve nothing else."""
    peer = FakePeer(tools=TOOLS + ("receive_commit",),
                    reply=signed_reply(our_terms))

    assert verdict_for(run_probe(peer, our_terms), "surface")["ok"] is True


def test_the_leaf_cause_is_named_not_the_task_group_wrapping_it(our_terms):
    """anyio wraps a refused connection in a TaskGroup whose str() is
    "unhandled errors in a TaskGroup" — which names nothing at all. The
    opponent's tunnel being down is the likeliest failure of the whole
    phase, so the leaf is what the operator has to be handed."""
    refused = ConnectionRefusedError("[Errno 111] Connection refused")
    wrapped = BaseExceptionGroup("unhandled errors in a TaskGroup", [refused])

    report = run_probe(FakePeer(opens=wrapped), our_terms)

    detail = verdict_for(report, "reachable")["detail"]
    assert "ConnectionRefusedError" in detail
    assert "Connection refused" in detail
    assert "TaskGroup" not in detail


def test_a_plain_failure_is_reported_unwrapped(our_terms):
    peer = FakePeer(opens=RuntimeError("502 Bad Gateway"))

    detail = verdict_for(run_probe(peer, our_terms), "reachable")["detail"]

    assert detail == "RuntimeError: 502 Bad Gateway"


# --- the exit code is what gates a launch script (FR7) ---------------------


def test_an_empty_report_is_not_a_pass():
    """`all()` of nothing is True. A probe that ran no check at all must not
    hand a launch script a green light."""
    assert netcheck.exit_code([]) != 0
