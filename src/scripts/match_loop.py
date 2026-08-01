"""Drive one local P2P match: commit everywhere, then reveal everywhere.

Mirrored local truth (D2): every peer's server keeps its OWN GameEpisode, so
each submission is broadcast to both. The two engines advance independently
and are compared every turn — which is the point, since neither peer trusts
the other's engine. A disagreement is raised, never absorbed.
"""

_OTHER = {"police": "thief", "thief": "police"}
_COMPARED = (
    "turn_count",
    "cop_position",
    "thief_position",
    "captured",
    "is_terminated",
)


class DivergenceError(RuntimeError):
    """The peers' independent engines disagreed about the game state."""


def _normalise(value):
    """Positions arrive as tuples in-process and as lists over JSON."""
    return tuple(value) if isinstance(value, (list, tuple)) else value


def divergence(payloads):
    """Return a description of the first disagreement between peers, or None."""
    reference, *others = payloads
    for other in others:
        for field in _COMPARED:
            mine, theirs = _normalise(reference.get(field)), _normalise(other.get(field))
            if mine != theirs:
                return f"{field}: {mine!r} != {theirs!r}"
    return None


async def exchange_turn(turn, submissions, connections):
    """Broadcast BOTH commitments to every peer, THEN both reveals.

    The phase separation is the property being exercised: a reveal sent before
    both commitments were in would let the second peer choose its move after
    seeing the first one.
    """
    commitments = []
    for connection in connections:
        for submission in submissions:
            commitments.append(
                await connection.submit_commitment(
                    submission.role, turn, submission.h_commit, submission.signature
                )
            )

    reveals = []
    for connection in connections:
        for submission in submissions:
            reveals.append(
                await connection.reveal_move(
                    submission.role,
                    turn,
                    submission.state,
                    submission.move,
                    submission.intent,
                    submission.nonce,
                    submission.signature,
                )
            )
    return commitments, reveals


async def play_match(clients, connections, board, config):
    """Play to termination; return the per-turn record of the whole match.

    Raises:
        DivergenceError: the peers' engines disagreed.
        RuntimeError: a turn failed to resolve on every peer.
    """
    positions = {
        "police": tuple(config.cop_start),
        "thief": tuple(config.thief_start),
    }
    history = []
    turn = 0

    while True:
        submissions = [
            clients[role].prepare(
                turn, positions[role], positions[_OTHER[role]], board
            )
            for role in ("police", "thief")
        ]

        _, reveals = await exchange_turn(turn, submissions, connections)

        resolved = [entry for entry in reveals if entry.get("status") == "resolved"]
        if len(resolved) != len(connections):
            raise RuntimeError(f"turn {turn} did not resolve on every peer: {reveals}")

        clash = divergence(resolved)
        if clash is not None:
            raise DivergenceError(f"turn {turn}: {clash}")

        agreed = resolved[0]
        history.append({"turn": turn, "submissions": submissions, "result": agreed})
        positions = {
            "police": _normalise(agreed["cop_position"]),
            "thief": _normalise(agreed["thief_position"]),
        }
        turn += 1

        if agreed["is_terminated"]:
            return history
