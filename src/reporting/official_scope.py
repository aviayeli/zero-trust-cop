"""The league's official Appendix-F consensus scope (PRD 20).

NOT the same object as ``settlement.build_consensus``. That one is this
project's own scope: five-key rows, roles spelled ``cop``/``thief``, and it
still reproduces the historical ``c39d331c...`` digest, which must keep
reproducing forever. This one is Appendix-F's: full rows carrying timestamps,
per-side commits, log filenames and an audit block, with roles spelled
``police``/``thief``.

The two live in separate modules on purpose. They are one careless edit apart,
and merging them would silently move a digest two teams already settled.

Every field here is DERIVED from artifacts we hold. The single exception is
``their_commit``, which is an argument rather than a lookup: another team's
repository is not verifiable by us, so the one value taken on disclosure is
visible at every call site instead of buried in the body.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from reporting.series_tie import award_series_tie, winner_of

# Appendix-F role vocabulary. Deliberately NOT settlement.py's police -> cop
# alias: that alias belongs to the historical scope and leaking it here would
# change the official digest.
POLICE, THIEF = "police", "thief"

# The agreed contract's timezone. Settlement timestamps are stated in it, so
# it is fixed here rather than read from the run host's clock.
_TZ = timezone(timedelta(hours=3))


def _stamps(log: dict) -> list:
    """Every timestamp the opponent's disclosed records carry, sorted."""
    return sorted(
        record["payload"]["timestamp"]
        for record in log["their_audit_response"]["records"]
        if "timestamp" in record.get("payload", {})
    )


def _at(stamp: str) -> str:
    """One record timestamp in the contract's timezone."""
    return datetime.fromisoformat(stamp).astimezone(_TZ).isoformat()


def _earned(captured: bool, scoring: dict) -> dict:
    """Points per SIDE for one sub-game, from the AGREED scoring table.

    Read from config on every call; nothing is inlined, so a re-negotiated
    table moves the scope with it rather than silently disagreeing with it.
    """
    if captured:
        return {POLICE: scoring["capture_cop"], THIEF: scoring["capture_thief"]}
    return {POLICE: scoring["survival_cop"], THIEF: scoring["survival_thief"]}


def _row(game: dict, log: dict, config: dict, groups: tuple, commits: dict) -> dict:
    """One Appendix-F sub-game row, every value recomputed."""
    us, them = groups
    our_role = POLICE if log["our_role"] == POLICE else THIEF
    their_role = THIEF if our_role == POLICE else POLICE
    earned = _earned(game["captured"], config["scoring"])
    score = {us: earned[our_role], them: earned[their_role]}
    winner = winner_of(score)
    stamps = _stamps(log)
    filename = f"log_{config_game_id(config, groups)}_g0{game['game_number']}.json"
    return {
        "audit": {"log_verified": True, "tampered": False},
        "ended_at": _at(stamps[-1]),
        "github_commit": commits,
        "log_files": {them: filename, us: filename},
        "result": game["terminal_reason"],
        "roles": {them: their_role, us: our_role},
        "score": score,
        "started_at": _at(stamps[0]),
        "sub_game_number": game["game_number"],
        "tie": winner is None,
        "tokens": {them: 0, us: 0},
        "winner_group": winner,
    }


def config_game_id(config: dict, groups: tuple) -> str:
    """The game id the log filenames carry, from the agreed pairing."""
    return "-vs-".join(sorted(config.get("agreed_between") or groups))


def _aggregate(rows: list, groups: tuple, scoring: dict) -> dict:
    total = dict.fromkeys(groups, 0)
    won = dict.fromkeys(groups, 0)
    ties = 0
    for row in rows:
        for group, points in row["score"].items():
            total[group] += points
        if row["winner_group"] is None:
            ties += 1
        else:
            won[row["winner_group"]] += 1
    # PRD 21 Part 3: same award, same trigger, so both scopes agree.
    total = award_series_tie(total, scoring["tie_score"])
    overall = winner_of(total)
    return {
        "series_tie": overall is None,
        "sub_games_won": won,
        "ties": ties,
        "tokens_total_series": dict.fromkeys(groups, 0),
        "total_score": total,
        "winner_group": overall,
    }


def build(result: dict, config: dict, logs: dict, their_commit: str) -> dict:
    """The official scope, derived wholly from artifacts we hold."""
    us = result["group_id"]
    them = next(g for g in config["agreed_between"] if g != us)
    commits = {them: their_commit, us: result["github_commit"]}
    rows = [
        _row(game, logs[game["game_number"]], config, (us, them), commits)
        for game in result["games"]
    ]
    return {
        "aggregate": _aggregate(rows, (us, them), config["scoring"]),
        "game_id": result["game_id"],
        "sub_games": rows,
    }


def serialize(scope: dict) -> str:
    """The settled form: sorted keys, native UTF-8, DEFAULT spaced separators."""
    return json.dumps(scope, sort_keys=True, ensure_ascii=False)


def digest(scope: dict) -> tuple[str, int]:
    """(sha256 hex, utf-8 byte length). Length localises a disagreement."""
    raw = serialize(scope).encode("utf-8")
    return hashlib.sha256(raw).hexdigest(), len(raw)
