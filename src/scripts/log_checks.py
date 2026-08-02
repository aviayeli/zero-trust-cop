"""The individual integrity checks behind a ``Verified OK`` verdict.

Split out of ``replay_match.py`` so each check has room to be thorough. The
audit found the replay compared only the FINAL state, so a fabricated
per-turn trajectory certified clean (V1); indices (V2) and turn counts (V3)
went unchecked; and hostile field types crashed the verifier (V4).

Every check APPENDS to a shared failures list rather than raising, so one bad
field cannot mask the rest of the report.
"""

from engine.game_loop import GameEpisode
from mcp_server.crypto import verify
from mcp_server.directions import decode, is_wire_move
from mcp_server.identity import verify_signature

from scripts.log_shape import PEER_ROLES


def _safe_verify(entry) -> bool:
    """A hostile digest must fail the check, not crash it (V4).

    ``compare_digest`` raises on non-ASCII, which would otherwise let an
    attacker choose a traceback over a verdict.
    """
    try:
        return verify(
            entry["state"], entry["move"], entry["intent"],
            entry["nonce"], entry["h_commit"],
        )
    except (TypeError, KeyError, ValueError):
        return False


def check_commitments(log, failures) -> None:
    """Re-derive every digest from what was actually revealed."""
    for index, turn in enumerate(log["turns"]):
        for role, entry in turn["submissions"].items():
            if not _safe_verify(entry):
                failures.append(
                    f"turn {index} {role}: commitment does not match reveal"
                )


def _safe_signature(public_key, role, turn_number, entry) -> bool:
    try:
        return verify_signature(
            public_key, role, turn_number, entry["h_commit"], entry["signature"]
        )
    except (TypeError, KeyError, ValueError):
        return False


def check_signatures(log, public_keys, failures) -> None:
    """Re-verify every signature against the turn it claims to belong to."""
    for index, turn in enumerate(log["turns"]):
        for role, entry in turn["submissions"].items():
            if role not in public_keys:
                failures.append(f"turn {index} {role}: no public key")
                continue
            if not _safe_signature(public_keys[role], role, turn.get("turn"), entry):
                failures.append(f"turn {index} {role}: signature invalid")


def _compare_turn(index, recorded, result, turn_count, failures) -> None:
    """Compare ONE replayed turn against what the log recorded for it."""
    expected = {
        "cop_position": tuple(result.cop_position),
        "thief_position": tuple(result.thief_position),
        "captured": result.captured,
        "turn_count": turn_count,
    }
    for key, value in expected.items():
        logged = recorded.get(key)
        if isinstance(value, tuple) and isinstance(logged, (list, tuple)):
            logged = tuple(logged)
        if logged != value:
            failures.append(
                f"turn {index}: replay disagrees on {key}: {logged!r} != {value!r}"
            )


def check_replay(log, config, failures) -> None:
    """Replay turn by turn, comparing EVERY result (V1) and the count (V3).

    Comparing only the final state let an attacker rewrite a match's middle.
    The count catches turns padded on after termination, where
    ``GameEpisode.step`` is a no-op and the state cannot move.
    """
    episode = GameEpisode(config)
    for index, turn in enumerate(log["turns"]):
        submissions = turn["submissions"]
        wire = [submissions[r]["move"] for r in PEER_ROLES]
        if not all(is_wire_move(move) for move in wire):
            failures.append(f"turn {index}: move outside the wire vocabulary")
            continue
        result = episode.step(*(decode(move) for move in wire))
        if result is None:
            failures.append(f"turn {index}: replay produced no result")
            continue
        _compare_turn(index, turn["result"], result, episode.turn_count, failures)

    if len(log["turns"]) != episode.turn_count:
        failures.append(
            f"turn count: log lists {len(log['turns'])}, "
            f"replay reached {episode.turn_count}"
        )
