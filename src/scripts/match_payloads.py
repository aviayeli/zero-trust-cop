"""Assemble the per-game log and series result payloads.

Split from ``match_log.py`` at the payload/writer seam: that module reached the
150-line limit once the two match ids became DERIVED rather than passed in.
This half decides WHAT the artifacts say; ``match_log`` decides where they are
written and what they are named.

SCHEMA CAVEAT: Appendix F of ``police_thief_p2p.pdf`` is not in this
repository. Only the four FILENAMES come from the specification; the field
layout below is this project's own design and must be reconciled with the real
appendix before submission.
"""

from mcp_server.declaration import github_commit
from mcp_server.repos import load_repos

ARTIFACT_VERSION = 1
ARTIFACT_KINDS = ("declaration", "config", "log", "result")
_SUBMISSION_FIELDS = ("h_commit", "signature", "state", "move", "intent", "nonce")


def _plain(value):
    """Make positions JSON-safe without changing their meaning."""
    if isinstance(value, tuple):
        return list(value)
    return value


def _submission_record(submission) -> dict:
    return {field: getattr(submission, field) for field in _SUBMISSION_FIELDS}


def _turn_record(entry) -> dict:
    """One turn: both peers' commitments and reveals, plus the outcome."""
    return {
        "turn": entry["turn"],
        "submissions": {
            submission.role: _submission_record(submission)
            for submission in entry["submissions"]
        },
        "result": {key: _plain(value) for key, value in entry["result"].items()},
    }


def build_log(ids, game_number, history, group_id, barriers=()) -> dict:
    """Assemble the replayable per-game log payload.

    ``barriers`` is recorded because the log must be replayable on its own:
    a verifier holding only this file and the peers' public keys cannot be
    assumed to hold the seed that generated the board (PLAN.md §4.3).
    """
    return {
        "artifact_version": ARTIFACT_VERSION,
        "game_uid": ids["game_uid"],
        "game_id": ids["game_id"],
        "game_number": game_number,
        "group_id": group_id,
        "barriers": [list(cell) for cell in sorted(barriers)],
        "turns": [_turn_record(entry) for entry in history],
    }


def build_result(ids, game_number, history, group_id) -> dict:
    """Assemble the series result payload.

    ``mutual_agreement`` is not a courtesy flag: play_match compares both
    peers' independent engines on every turn and raises DivergenceError on
    any disagreement, so a history that reached here is itself the evidence.
    """
    final = history[-1]["result"]
    return {
        "artifact_version": ARTIFACT_VERSION,
        "game_uid": ids["game_uid"],
        "game_id": ids["game_id"],
        "group_id": group_id,
        "github_commit": github_commit(),
        "repos": load_repos(),
        "mutual_agreement": {
            "confirmed": True,
            "turns_cross_checked": len(history),
            "method": "per-turn comparison of both peers' independent engines",
        },
        "games": [
            {
                "game_number": game_number,
                "turns": len(history),
                "captured": final["captured"],
                "terminal_reason": final["terminal_reason"],
                "cop_position": _plain(final["cop_position"]),
                "thief_position": _plain(final["thief_position"]),
            }
        ],
    }
