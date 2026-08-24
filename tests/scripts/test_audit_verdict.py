"""Reading the opponent's audit verdict, in either spelling (PRD_10 10.19).

Split from `test_reference_artifacts.py`, which covers what the four files
say. This covers the one field that was WRONG in a real graded artifact: a
friendly against rstabcde recorded `confirmed: false` while their reply said
`{"accepted": true}`, because we only read our own `status` key.

Every opponent met so far answers in their spelling and none in ours. The
direction that must never loosen is the other one — `tampered`,
`accepted: false`, and silence are all not confirmation.
"""

from mcp_server import interop


def _record(step, move="MOVE:N"):
    payload = {"step": step, "state": f"grid=7x7;self=[{step}, 0];barriers=[]",
               "position": [step, 0], "move": move, "intent": "truth",
               "hint": "north"}
    nonce = f"{step:032d}"
    return {"payload": payload, "nonce": nonce,
            "commit": interop.commit(payload, nonce)}


def _their_turn(step, sender="thief"):
    return {"step": step, "sender": sender, "hint": "", "smell_grid": {"3,3": 0.9},
            "commit": "b" * 64, "timestamp": "2026-08-24T00:00:00Z"}


def _summary(sub_game, role, outcome="capture", steps=2):
    return {
        "sub_game": sub_game, "role": role, "steps": steps,
        "terminal_reason": outcome,
        "handshake_counter_signed": False,
        "result_claim": {"outcome": outcome, "steps": steps},
        "their_audit_response": {"status": "accepted", "records_verified": steps},
        "our_chain": [_record(s) for s in range(1, steps + 1)],
        "their_turns": [_their_turn(s) for s in range(1, steps + 1)],
    }


# --- the audit verdict, in either spelling ---------------------------------


def _audited(reply):
    from scripts.reference_artifacts import build_result

    summary = _summary(1, "police")
    summary["their_audit_response"] = reply
    return build_result({"game_uid": "u", "game_id": "g"}, [summary], "aviayeli")


def test_their_acceptance_is_recognised_in_their_own_spelling():
    """rstabcde and ali-ahm1 both answer `{"accepted": true}` with no
    `status`. We only read `status`, so a clean mutual audit was recorded in
    the graded artifact as `confirmed: false` — we told the grader the
    opponent had not accepted our chain when they had."""
    assert _audited({"accepted": True})["mutual_agreement"]["confirmed"] is True


def test_our_own_spelling_still_counts():
    assert _audited({"status": "accepted"})["mutual_agreement"]["confirmed"] is True


def test_a_TAMPERED_verdict_is_never_read_as_confirmation():
    """The direction that must not be loosened."""
    assert _audited({"status": "tampered"})["mutual_agreement"]["confirmed"] is False
    assert _audited({"accepted": False})["mutual_agreement"]["confirmed"] is False


def test_no_answer_at_all_is_not_confirmation():
    assert _audited(None)["mutual_agreement"]["confirmed"] is False
    assert _audited({})["mutual_agreement"]["confirmed"] is False
