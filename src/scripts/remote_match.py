"""Play one match against ANOTHER GROUP's peer over its published tunnel.

``match_loop.play_match`` owns both halves of the game: it prepares both
peers' submissions and broadcasts them to both servers, so every reveal comes
back resolved. That is correct for a local simulation and wrong for league
play, where the opposing group produces its own signed moves and we must not
invent them.

What stays the same is mirrored local truth (D2): our submission still goes to
BOTH servers, and both are cross-examined every turn. What changes is that a
turn may settle without telling us — the gate answers ``resolved`` only to the
second revealer — so the outcome is polled for rather than assumed
(``remote_sync``).
"""

from scripts.board_agreement import verify_board_agreement
from scripts.match_loop import DivergenceError, divergence
from scripts.remote_sync import (
    RemoteMatchError,
    await_turn_count,
    observed_result,
    refuse,
    reveal_when_accepted,
)

__all__ = ["RemoteMatchError", "play_remote_match", "push_submission"]

ENGINE_ROLE = {"police": "cop", "thief": "thief"}
_OTHER_PEER = {"police": "thief", "thief": "police"}


async def push_submission(submission, connections, deadline_sec, poll_sec):
    """Commit to every peer, THEN reveal to every peer.

    The phase separation is the anti-front-running property: a reveal that
    went out before the commitments were placed would let the other side pick
    its move knowing ours. Each peer enforces it independently, which is why
    the reveal may have to wait for the opponent's commitment to arrive.

    Returns:
        The resolved payloads, which may be none, some or all of the peers.

    Raises:
        RemoteMatchError: a peer refused the commitment or the reveal.
        TechnicalLossError: a peer never unblocked the reveal.
    """
    for index, peer in enumerate(connections):
        outcome = await peer.submit_commitment(
            submission.role, submission.turn,
            submission.h_commit, submission.signature,
        )
        refuse(outcome, "submit_commitment", index)

    resolved = []
    for index, peer in enumerate(connections):
        outcome = await reveal_when_accepted(
            peer, index, submission, deadline_sec, poll_sec
        )
        if outcome.get("status") == "resolved":
            resolved.append(outcome)
    return resolved


async def _settle(turn, resolved, connections, engine_roles, config, poll_sec):
    """Establish what the turn actually was, whoever the gate told.

    Waiting for the laggards is not politeness: the next turn's commitment
    carries turn N+1, and a server still on N answers ``wrong_turn``.
    """
    if len(resolved) == len(connections):
        clash = divergence(resolved)
        if clash is not None:
            raise DivergenceError(f"turn {turn}: {clash}")
        return resolved[0]

    statuses = await await_turn_count(
        connections, turn + 1, config.watchdog_timeout_sec, poll_sec
    )
    if resolved:
        return resolved[0]
    return await observed_result(connections, engine_roles, statuses)


async def play_remote_match(
    client, local, remote, board, config, poll_interval_sec
):
    """Play to termination against a remote peer; return the turn history.

    ``client`` produces ONLY our own role's submissions. ``local`` is our own
    running peer and ``remote`` is the opposing group's, reached at the
    ``opponent_url`` its operators published.

    Raises:
        DivergenceError: the two peers' engines disagreed.
        RemoteMatchError: a peer refused a submission.
        TechnicalLossError: a peer stopped answering (rulebook forfeit).
    """
    own_peer = client.peer_role
    engine_roles = (ENGINE_ROLE[own_peer], ENGINE_ROLE[_OTHER_PEER[own_peer]])
    connections = (local, remote)

    await verify_board_agreement(
        connections, board.barrier_count, config, engine_roles
    )

    positions = {
        "police": tuple(config.cop_start),
        "thief": tuple(config.thief_start),
    }
    history = []
    turn = 0

    while True:
        submission = client.prepare(
            turn, positions[own_peer], positions[_OTHER_PEER[own_peer]], board
        )
        resolved = await push_submission(
            submission, connections,
            config.watchdog_timeout_sec, poll_interval_sec,
        )
        agreed = await _settle(
            turn, resolved, connections, engine_roles, config, poll_interval_sec
        )

        history.append({"turn": turn, "submissions": [submission], "result": agreed})
        positions = {
            "police": tuple(agreed["cop_position"]),
            "thief": tuple(agreed["thief_position"]),
        }
        turn += 1

        if agreed["is_terminated"]:
            return history
