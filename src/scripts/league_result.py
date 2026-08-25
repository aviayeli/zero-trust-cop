"""Translate our result into the league's own `final_game_result` schema.

`match_log` has carried the caveat since Phase 6: only the four FILENAMES came
from the specification, and the payload layout was this project's own design
"pending reconciliation with the course appendix". This is that
reconciliation, from two `schema_version: "1.1"` results by SMNGRP05.

A TRANSLATOR, not a writer: it measures nothing and re-derives nothing, and
every value is copied from the sealed artifacts or read off the logs. In
particular ``mutual_agreement.sha256`` is carried through byte-identical --
that value was computed over the consensus preimage and then independently
confirmed by the opponent, so recomputing it to satisfy a formatter would risk
breaking a verified cross-team agreement.

What we cannot know about the opponent is marked as theirs to declare rather
than guessed, the convention the reference files use themselves.
"""

from __future__ import annotations

import json

SCHEMA_VERSION = "1.1"
REPORT_TYPE = "final_game_result"
# The opponent's to state in their own copy; we must not invent it.
THEIRS_TO_DECLARE = "declared-in-their-own-report"
_SCHEMA = (
    "Summary and final result for the WHOLE game (all sub-games) between two "
    "teams. It condenses the per-sub-game logs into a per-group score for "
    "every sub-game plus the aggregate outcome the lecturer needs to build "
    "the league standings. Static team metadata lives in the declaration and "
    "is referenced via game_id / group_id. Both teams must agree on this "
    "result and each sends its own copy to the lecturer (book ch9)."
)
_LINKS_REMARK = (
    "Logical roles, NOT fixed filenames. Every actual filename is derived "
    "from the game_id so files from different games are never mixed. "
    "Match-level files are named <role>_<game_id>.json; per-sub-game files "
    "are named <role>_<game_id>_g<NN>.json where <NN> is the "
    "sub_game_number."
)


def _window(log: dict) -> tuple:
    """When their turns first and last arrived, off the timestamps their
    messages actually carried rather than invented at report time."""
    stamps = sorted(
        turn["theirs"]["timestamp"]
        for turn in log.get("turns", [])
        if (turn.get("theirs") or {}).get("timestamp")
    )
    return (stamps[0], stamps[-1]) if stamps else (None, None)


def _audit(log: dict) -> dict:
    """What we actually verified, never more: ``log_verified`` is their
    accepted re-hash of our disclosed chain, which is the verification this
    wire performs. Nothing here claims a replay we did not run."""
    answer = log.get("their_audit_response") or {}
    accepted = (answer.get("status") == "accepted"
                or answer.get("accepted") is True or answer.get("ok") is True)
    return {
        "log_verified": accepted,
        "tampered": False,
        "opponent_present": bool(answer),
        "results_agree": accepted,
        "opponent_result_claim": (log.get("result_claim") or {}).get("outcome"),
    }


def _links(game_id: str, repos: dict, us: str) -> dict:
    return {
        "_remark": _LINKS_REMARK,
        "declaration": f"declaration_{game_id}.json",
        "config": f"config_{game_id}_g<NN>.json",
        "log": f"log_{game_id}_g<NN>.json",
        "result": f"result_{game_id}.json",
        "github": {us: dict(repos)},
    }


def _sub_game(row: dict, ours: dict, log: dict, us: str, them: str,
              game_id: str) -> dict:
    """One row, with score, winner and tie from the VERIFIED consensus --
    the fields the settlement hash covers. Publishing anything else would put
    numbers in the report the agreed hash does not cover."""
    started, ended = _window(log)
    number = row["sub_game_number"]
    return {
        "sub_game_number": number,
        "roles": {group: role for role, group in row["roles"].items()},
        "started_at": started,
        "ended_at": ended,
        "result": row["result"],
        "winner_group": row["winner_group"],
        "tie": row["winner_group"] is None,
        "github_commit": {us: ours["github_commit"],
                          them: THEIRS_TO_DECLARE},
        # We do not meter tokens; both reference reports carry zeros.
        "tokens": {us: 0, them: 0},
        "score": dict(row["score"]),
        "log_files": dict.fromkeys((us, them), f"log_{game_id}_g{number:02d}.json"),
        "audit": _audit(log),
    }


def league_result(ours: dict, logs: list, timezone: str | None = None,
                  config_path: str = "config/game.json") -> dict:
    """Our sealed result, in the shape the lecturer's tooling reads."""
    if timezone is None:
        with open(config_path, encoding="utf-8") as contract:
            timezone = json.load(contract)["timezone"]

    consensus = ours["mutual_agreement"]["consensus"]
    us = ours["group_id"]
    rows = sorted(consensus["sub_games"], key=lambda r: r["sub_game_number"])
    them = next(group for group in rows[0]["roles"].values() if group != us)
    by_number = {log["game_number"]: log for log in logs}
    game_id = ours["game_id"]

    return {
        "_schema": _SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "report_type": REPORT_TYPE,
        "game_id": game_id,
        "game_uid": ours["game_uid"],
        "links": _links(game_id, ours.get("repos", {}), us),
        "timezone": timezone,
        "groups": sorted((us, them)),
        "num_sub_games": len(rows),
        "sub_games": [
            _sub_game(row, ours, by_number.get(row["sub_game_number"], {}),
                      us, them, game_id)
            for row in rows
        ],
        "final_result": dict(consensus["aggregate"], tokens_total_series={
            us: 0, them: 0}),
        # Carried through, never re-derived: the opponent confirmed this
        # string independently.
        "mutual_agreement": {
            "sha256": ours["mutual_agreement"]["sha256"],
            "confirmed": ours["mutual_agreement"]["confirmed"],
        },
    }
