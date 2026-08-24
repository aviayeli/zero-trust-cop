"""The four artifacts a reference-v3 series leaves on disk (PRD_10 10.19).

Until now a live series printed to stdout and left nothing behind. A graded
run has to be readable by the lecturer's checker, which means the four
standard filenames under `logs/<group_id>/` and payloads that tie together
through one derived `game_uid`.

What the log may NOT do is borrow the native dialect's shape. That log records
a per-turn `signature` and the opponent's revealed `move`, `state` and
`nonce` — and on this wire none of those exist. `receive_turn` carries no
signature, and their move stays sealed until `submit_audit`. Filling them
with nulls to fit a schema would put fields into a graded artifact that no
message ever carried, so the record here is what the wire actually held:
our sealed chain, their pushed digests, and the audit each side returned.
"""

import json
from pathlib import Path

import pytest

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


@pytest.fixture
def summaries():
    return [_summary(1, "police"), _summary(2, "thief", outcome="survival")]


@pytest.fixture
def written(tmp_path, summaries):
    from scripts.reference_writer import write_series_artifacts

    return write_series_artifacts(tmp_path, summaries, group_id="aviayeli",
                                  opponent_id="ali-ahm1")


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_all_four_kinds_are_written(written):
    assert sorted(written) == ["config", "declaration", "log", "result"]


def test_one_log_per_sub_game(written, summaries):
    assert len(written["log"]) == len(summaries)
    assert all(Path(path).exists() for path in written["log"])


def test_every_artifact_carries_the_same_derived_uid(written):
    uids = {_load(written[kind])["game_uid"] for kind in ("declaration", "config", "result")}
    uids |= {_load(path)["game_uid"] for path in written["log"]}

    assert len(uids) == 1


def test_the_game_id_names_the_pair_not_us(written):
    assert _load(written["result"])["game_id"] == "ali-ahm1-vs-aviayeli"


def test_the_log_records_our_sealed_chain_with_its_nonces(written):
    turns = _load(written["log"][0])["turns"]

    assert [t["step"] for t in turns] == [1, 2]
    for turn in turns:
        ours = turn["ours"]
        assert interop.commit(ours["payload"], ours["nonce"]) == ours["commit"]


def test_the_log_records_the_digest_they_pushed_for_each_step(written):
    turns = _load(written["log"][0])["turns"]

    assert all(turn["theirs"]["commit"] == "b" * 64 for turn in turns)


def test_the_log_does_not_invent_a_signature_this_wire_never_carried(written):
    """`receive_turn` has no signature field. A null one would be a claim
    about a message that never existed."""
    turn = _load(written["log"][0])["turns"][0]

    assert "signature" not in turn["ours"] and "signature" not in turn["theirs"]


def test_the_log_does_not_invent_their_move(written):
    """Their move stays sealed until `submit_audit`. We record the digest we
    were given, never a move we were not."""
    turn = _load(written["log"][0])["turns"][0]

    assert "move" not in turn["theirs"]


def test_the_result_lists_every_sub_game_with_the_side_we_played(written):
    games = _load(written["result"])["games"]

    assert [g["game_number"] for g in games] == [1, 2]
    assert [g["our_role"] for g in games] == ["police", "thief"]


def test_captured_is_derived_from_the_terminal_reason(written):
    games = _load(written["result"])["games"]

    assert games[0]["captured"] is True
    assert games[1]["captured"] is False


def test_the_settlement_scores_each_sub_game_on_the_side_it_was_played(written):
    """The reason `our_role` rides on every game row."""
    rows = _load(written["result"])["mutual_agreement"]["consensus"]["sub_games"]

    assert rows[0]["roles"] == {"cop": "aviayeli", "thief": "ali-ahm1"}
    assert rows[1]["roles"] == {"cop": "ali-ahm1", "thief": "aviayeli"}


def test_the_consensus_is_signed_over_itself(written):
    agreement = _load(written["result"])["mutual_agreement"]

    assert agreement["sha256"] == \
        interop.report_consensus_signature(agreement["consensus"])
