"""The four artifacts a reference-v3 series leaves on disk (PRD_10 10.19).

A live series used to print to stdout and leave nothing behind, which is no
use to the lecturer's checker. This writes the four standard names under
``logs/<group_id>/``, all tied together by one DERIVED ``game_uid``.

The log deliberately does NOT reuse the native dialect's turn record. That one
carries a per-turn ``signature`` and the opponent's revealed ``move``,
``state`` and ``nonce``; on this wire none of them exist -- ``receive_turn``
is unsigned, and their move stays sealed until ``submit_audit``. Padding a
graded artifact with nulls to fit a schema would assert fields no message
ever carried, so a turn here records what the wire actually held: our sealed
record, the digest they pushed, and what each side claimed.

Only the payload shape is new. Where the files land and what they are called
is ``reference_writer``, which defers to ``match_log`` so a reference-v3
series leaves artifacts indistinguishable in shape and location from a native
one.
"""

from __future__ import annotations

from mcp_server.declaration import github_commit
from mcp_server.repos import load_repos
from scripts.match_payloads import ARTIFACT_VERSION

_CAPTURE = "capture"


def _turn_record(ours: dict, theirs: dict | None) -> dict:
    """One step, from both sides, with nothing invented for either.

    ``theirs`` is None when their chain is shorter than ours -- a sub-game
    that ended on our own final push. Recorded as absent rather than as an
    empty turn.
    """
    record = {"step": ours["payload"]["step"], "ours": dict(ours)}
    if theirs is not None:
        record["theirs"] = {
            key: theirs[key] for key in ("commit", "hint", "smell_grid",
                                         "timestamp", "sender")
            if key in theirs
        }
        for claim in ("capture_claim", "claim_response", "win_claim"):
            if theirs.get(claim) is not None:
                record["theirs"][claim] = theirs[claim]
    return record


def build_log(ids: dict, summary: dict, group_id: str, barriers) -> dict:
    """One sub-game, replayable from this file and the public keys alone."""
    by_step = {turn.get("step"): turn for turn in summary["their_turns"]}
    return {
        "artifact_version": ARTIFACT_VERSION,
        "game_uid": ids["game_uid"],
        "game_id": ids["game_id"],
        "game_number": summary["sub_game"],
        "group_id": group_id,
        "wire_shape": "reference-v3",
        "our_role": summary["role"],
        "barriers": [list(cell) for cell in sorted(barriers)],
        "result_claim": summary["result_claim"],
        "their_audit_response": summary.get("their_audit_response"),
        # THEIR disclosed chain and our verdict on it (PRD 22). Distinct from
        # `their_audit_response`, which is their RECEIPT for our payload. A
        # list, empty when none arrived: absent and empty must not look alike.
        "their_disclosed_audits": list(summary.get("their_disclosed_audits") or []),
        "handshake_counter_signed": summary.get("handshake_counter_signed"),
        "turns": [
            _turn_record(record, by_step.get(record["payload"]["step"]))
            for record in summary["our_chain"]
        ],
    }


def _accepted(reply) -> bool:
    """Whether they accepted our chain, in EITHER spelling.

    Three spellings are live: we answer ``status: "accepted"``, rstabcde
    answer ``accepted: true``, ZeroOne0 answer ``ok: true``. Reading only our
    own key recorded a clean mutual audit as ``confirmed: false`` -- twice,
    against two different groups. Reading only our own key
    recorded a clean mutual audit in the graded artifact as
    ``confirmed: false`` -- telling the grader the opponent had rejected our
    chain when they had accepted it.

    Silence is NOT acceptance, and neither is an explicit no: only a positive
    verdict counts, in either vocabulary.
    """
    if not isinstance(reply, dict):
        return False
    return (reply.get("status") == "accepted"
            or reply.get("accepted") is True
            or reply.get("ok") is True)


def build_result(ids: dict, summaries: list, group_id: str) -> dict:
    """The series result. ``our_role`` rides on every row because the sides
    SWAP each sub-game, and settlement scores a row on the side it was
    played (``reporting.settlement._roles_for``)."""
    return {
        "artifact_version": ARTIFACT_VERSION,
        "game_uid": ids["game_uid"],
        "game_id": ids["game_id"],
        "group_id": group_id,
        "github_commit": github_commit(),
        "repos": load_repos(),
        "wire_shape": "reference-v3",
        "mutual_agreement": {
            # NOT the native dialect's claim. Nothing here compared two
            # engines per turn: on this wire each peer resolves its own piece
            # and the evidence is the opponent's re-hash of our disclosed
            # chain at the end of each sub-game.
            "confirmed": all(_accepted(s.get("their_audit_response"))
                             for s in summaries),
            "sub_games_audited": len(summaries),
            "method": "opponent re-hash of each side's sealed chain at submit_audit",
            "handshake_counter_signed": all(
                s.get("handshake_counter_signed") for s in summaries
            ),
        },
        "games": [
            {
                "game_number": s["sub_game"],
                "our_role": s["role"],
                "turns": s["steps"],
                "captured": s["terminal_reason"] == _CAPTURE,
                "terminal_reason": s["terminal_reason"],
            }
            for s in summaries
        ],
    }
