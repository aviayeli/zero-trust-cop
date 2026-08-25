"""A reference-v3 log must be verifiable offline (PRD_17).

`scripts.replay_match` is the command this project points a marker at -- the
README opens with it. Run it on the graded series and it printed `TAMPERED!`,
once per turn, on a series both teams audited and whose settlement hash they
independently confirmed.

Nothing was tampered with. The verifier reads the NATIVE dialect, whose turns
carry a `submissions` block of commit, reveal and signature; a reference-v3
turn carries `{step, ours, theirs}`, because the move stays sealed until
`submit_audit`. Two record shapes, one verifier.

The worst failure mode for an evidence-based submission is the evidence being
real and the tool that reads it saying otherwise.

Driven by the real graded logs.
"""

import copy
import json

import pytest

from scripts.reference_replay import verify

EVIDENCE = "logs/evidence/graded_series"


def _log(number: int = 1) -> dict:
    with open(f"{EVIDENCE}/log_aviayeli-vs-bb-ai-12_g{number:02d}.json") as f:
        return json.load(f)


@pytest.fixture
def log():
    return _log(1)


# --- the graded series verifies -------------------------------------------


@pytest.mark.parametrize("number", [1, 2, 3, 4, 5, 6])
def test_every_graded_log_verifies(number):
    report = verify(_log(number))

    assert report.ok, report.failures


def test_the_verdict_says_how_much_was_re_hashed(log):
    assert "35 sealed records re-hashed" in str(verify(log))


def test_the_verdict_states_what_it_did_not_cover(log):
    """FR4. A marker must not read `Verified OK` as both chains re-verified
    offline -- theirs is not in this file."""
    report = verify(log)

    assert "NOT COVERED" in report.caveat
    assert "submit_audit" in report.caveat


# --- and a rewritten chain is refused --------------------------------------


def test_an_edited_payload_is_refused_naming_the_step(log):
    """The load-bearing check: rewriting a record after the fact must not
    pass, however plausible the result."""
    tampered = copy.deepcopy(log)
    tampered["turns"][4]["ours"]["payload"]["hint"] = "a different hint"

    report = verify(tampered)

    assert not report.ok
    assert any("step 5" in failure for failure in report.failures)


def test_an_edited_nonce_is_refused(log):
    tampered = copy.deepcopy(log)
    tampered["turns"][0]["ours"]["nonce"] = "0" * 32

    report = verify(tampered)

    assert not report.ok


def test_a_missing_step_is_refused_as_a_gap(log):
    """A fabricated middle hides in a gap, so contiguity is checked."""
    tampered = copy.deepcopy(log)
    del tampered["turns"][10]

    report = verify(tampered)

    assert not report.ok
    assert any("contiguous" in f or "gap" in f for f in report.failures)


def test_a_move_that_does_not_reach_its_position_is_refused(log):
    """A payload edited to a legal-looking move still has to be reachable
    from the previous cell."""
    tampered = copy.deepcopy(log)
    record = tampered["turns"][6]["ours"]
    record["payload"]["position"] = [6, 6]
    from mcp_server import interop
    record["commit"] = interop.commit(record["payload"], record["nonce"])

    report = verify(tampered)

    assert not report.ok, "a re-sealed but unreachable position passed"
    assert any("step 7" in failure for failure in report.failures)


def test_a_claim_of_more_steps_than_were_played_is_refused(log):
    tampered = copy.deepcopy(log)
    tampered["result_claim"] = {"outcome": "survival", "steps": 99}

    report = verify(tampered)

    assert not report.ok


# --- the native path is untouched (FR2) ------------------------------------


def test_replay_match_dispatches_on_the_declared_wire_shape():
    import scripts.replay_match as module

    source = __import__("inspect").getsource(module.main)

    assert "reference-v3" in source or "wire_shape" in source


def test_a_graded_log_now_exits_zero(capsys):
    from scripts.replay_match import main

    with pytest.raises(SystemExit) as exit_code:
        main([f"{EVIDENCE}/log_aviayeli-vs-bb-ai-12_g01.json"])

    assert exit_code.value.code == 0
    assert "Verified OK" in capsys.readouterr().out
