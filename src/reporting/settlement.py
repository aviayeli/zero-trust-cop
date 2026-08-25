"""The settlement consensus both teams must reach byte-identically.

Two separate things have to be right, and only the second is about bytes.

**Scope** -- what the signature is computed OVER. A whole-report-minus-the-
signature preimage is per-side BY CONSTRUCTION: our timestamps, token counts
and hardware probe sit inside it, so two honest teams computing it can never
produce equal hashes. The interoperable scope is the trimmed symmetric
outcome below: everything two honest teams must agree on, and nothing they may
legitimately differ on. Sub-game rows carry FIVE keys -- ``tie`` is derivable
from ``winner_group is None`` and stays out of the preimage.

**Serialization** -- ``interop.report_consensus_signature``, the release's one
SPACED canonical form, computed before the signature key is inserted.

The KEY SET is the league's; what we put under those keys is our reading of
our own match, and the opponent must reach the same values from their side --
which is exactly what ``test_settlement`` pins by building both sides.
"""

from __future__ import annotations

from mcp_server import interop

# The five keys the hashed sub-game row carries. NOT six: `tie` belongs to the
# document row, never to the preimage -- every hash ever settled live
# reproduces only under these five.
CONSENSUS_ROW_KEYS = ("result", "roles", "score", "sub_game_number", "winner_group")

_ROLES = ("cop", "thief")

# Our peer/wire role is "police"; the agreed contract and the book both say
# "cop" (`cop_start`, `capture_cop`). The role names sit INSIDE the signed
# preimage, so the contract's vocabulary is the one that has to go in -- our
# internal name would put a word the opponent never writes into the hash.
_ROLE_ALIASES = {"police": "cop"}


def _roles_to_groups(group_id: str, opponent_id: str, our_role: str) -> dict:
    """Which group played which side -- shared, so both peers agree on it."""
    our_role = _ROLE_ALIASES.get(our_role, our_role)
    if our_role not in _ROLES:
        raise ValueError(f"our_role must be one of {_ROLES}, got {our_role!r}")
    other = _ROLES[0] if our_role == _ROLES[1] else _ROLES[1]
    return {our_role: group_id, other: opponent_id}


def _sub_game_score(game: dict, scoring: dict, roles: dict) -> dict:
    """Points per group for one sub-game, from the AGREED scoring table.

    Every value is read from ``config["scoring"]``; nothing here is inlined,
    so a re-negotiated table moves the settlement with it.
    """
    if game["captured"]:
        earned = {"cop": scoring["capture_cop"], "thief": scoring["capture_thief"]}
    else:
        earned = {"cop": scoring["survival_cop"], "thief": scoring["survival_thief"]}
    return {roles[role]: points for role, points in earned.items()}


def _winner(score: dict) -> str | None:
    """The higher-scoring group, or None on a tie (which is what makes the
    document row's ``tie`` derivable rather than worth signing)."""
    ranked = sorted(score.items(), key=lambda pair: pair[1], reverse=True)
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None
    return ranked[0][0]


def _roles_for(game: dict, group_id: str, opponent_id: str,
               series_roles: dict) -> dict:
    """The side-to-group map for THIS sub-game.

    Both teams agreed the sides alternate every sub-game on reference-v3, and
    one series-level mapping scores half of them for the wrong group -- inside
    the SIGNED preimage, where it surfaces only as two teams failing to
    reproduce each other's hash. A row may therefore declare the side we
    played that sub-game.

    A row that declares nothing keeps the series mapping exactly, so every
    fixed-role settlement ever signed still reproduces. Validation and the
    police -> cop alias come from ``_roles_to_groups``, so a row cannot be
    validated more loosely than the series.
    """
    declared = game.get("our_role")
    if declared is None:
        return series_roles
    return _roles_to_groups(group_id, opponent_id, declared)


def _sub_game_row(game: dict, scoring: dict, roles: dict) -> dict:
    score = _sub_game_score(game, scoring, roles)
    return {
        "sub_game_number": game["game_number"],
        "roles": roles,
        "result": game["terminal_reason"],
        "winner_group": _winner(score),
        "score": score,
    }


def _aggregate(rows: list, groups: tuple) -> dict:
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
    winner = _winner(total)
    return {
        "total_score": total,
        "sub_games_won": won,
        "ties": ties,
        "winner_group": winner,
        "series_tie": winner is None,
    }


def build_consensus(
    result: dict, config: dict, group_id: str, opponent_id: str, our_role: str
) -> dict:
    """The signed preimage: a pure function of facts both peers hold.

    Nothing per-side may enter it. The opponent builds the same structure from
    their own artifacts -- passing their own group as ``group_id`` and their
    own role -- and must reach byte-identical output.
    """
    series_roles = _roles_to_groups(group_id, opponent_id, our_role)
    scoring = config["scoring"]
    rows = [
        _sub_game_row(
            game, scoring,
            _roles_for(game, group_id, opponent_id, series_roles),
        )
        for game in result["games"]
    ]
    return {
        "game_id": result.get("game_id") or interop.game_id(group_id, opponent_id),
        "aggregate": _aggregate(rows, (group_id, opponent_id)),
        "sub_games": rows,
    }


def sign_consensus(consensus: dict) -> dict:
    """Sign-then-insert: the signature is absent from its own preimage."""
    return interop.sign_report(consensus)
