"""Recover a turn's outcome that the wire never handed us.

Against a remote opponent, ``SubmissionGate.reveal_move`` answers ``resolved``
only to the SECOND revealer. Whenever ours arrives first we are told
``waiting`` and the turn settles later, out of band, when the opponent's
reveal reaches the same server. There is no tool to fetch that reply after the
fact, so the outcome is reassembled from what every peer will still state:
its status, and its own role's position.

Split from ``remote_match`` because it is the only part that spends WALL
CLOCK time, and because the 150-line limit leaves the loop no room for it.
"""

import anyio

from mcp_server.http_peer import TechnicalLossError
from scripts.match_loop import DivergenceError

# The fields every peer must agree on before we believe a reconstructed turn.
# Positions are excluded on purpose: a peer states only its OWN (FR3), so
# there is nothing to cross-check there — which is why they are assembled
# from both peers rather than compared between them.
STATUS_FIELDS = ("turn_count", "is_terminated", "terminal_reason")

# Not a failure: a peer refuses EVERY reveal until BOTH commitments are in
# (``commitments.py``), and we control only our own half of that pair.
PENDING_COMMITMENT = "reveal_before_commit"


class RemoteMatchError(RuntimeError):
    """A peer refused a submission, so the two sides are no longer in step.

    Distinct from DivergenceError, which reports engines that disagree about
    a state they both accepted. This is a REFUSAL — a wrong turn, a bad
    signature, a forfeited match — and playing on after one would append
    turns that only our own server ever saw.
    """


def refuse(outcome, call, peer_index):
    """Raise if a peer answered with an error payload instead of a status."""
    if "error" in outcome:
        raise RemoteMatchError(
            f"peer {peer_index} refused {call}: {outcome['error']} "
            f"({outcome.get('message', 'no detail')})"
        )


async def reveal_when_accepted(
    peer, index, submission, deadline_sec, poll_interval_sec
):
    """Reveal to one peer, waiting out the opponent's missing commitment.

    The local runner never meets this case: it pushes BOTH commitments
    before any reveal, so the pair is always complete. Against a remote
    opponent the other commitment arrives on their schedule, and a reveal
    sent before it does is refused rather than queued.

    Raises:
        RemoteMatchError: the peer refused for any OTHER reason.
        TechnicalLossError: the commitment never arrived.
    """
    with anyio.move_on_after(deadline_sec) as scope:
        while True:
            outcome = await peer.reveal_move(
                submission.role, submission.turn, submission.state,
                submission.move, submission.intent, submission.nonce,
                submission.signature,
            )
            if outcome.get("error") != PENDING_COMMITMENT:
                refuse(outcome, "reveal_move", index)
                return outcome
            await anyio.sleep(poll_interval_sec)
    if scope.cancelled_caught:
        raise TechnicalLossError(
            f"peer {index} never received the opponent's commitment for "
            f"turn {submission.turn} within {deadline_sec} seconds"
        )


def status_divergence(statuses):
    """Return the first field the peers disagree about, or None."""
    reference, *others = statuses
    for other in others:
        for field in STATUS_FIELDS:
            mine, theirs = reference.get(field), other.get(field)
            if mine != theirs:
                return f"{field}: {mine!r} != {theirs!r}"
    return None


async def await_turn_count(connections, target, deadline_sec, poll_interval_sec):
    """Block until every peer reports ``target`` turns, or forfeit the match.

    A terminated match stops advancing, so termination ends the wait too —
    otherwise the last turn of every game would burn the whole watchdog
    window before being recognised.

    Raises:
        TechnicalLossError: the deadline passed with a peer still behind.
    """
    with anyio.move_on_after(deadline_sec) as scope:
        while True:
            statuses = [await peer.get_match_status() for peer in connections]
            if all(
                status["turn_count"] >= target or status["is_terminated"]
                for status in statuses
            ):
                return statuses
            await anyio.sleep(poll_interval_sec)
    if scope.cancelled_caught:
        raise TechnicalLossError(
            f"a peer did not reach turn {target} within {deadline_sec} seconds; "
            "the opponent stopped answering and the match is forfeit"
        )


async def observed_result(connections, engine_roles, statuses):
    """Rebuild the resolved-turn payload from each peer's own account.

    ``captured`` is derived rather than read: no status field carries it, but
    ``terminal_reason`` is 'capture' exactly when it happened.

    Raises:
        DivergenceError: the peers do not agree on the turn they just played.
    """
    clash = status_divergence(statuses)
    if clash is not None:
        raise DivergenceError(f"peers disagree after the turn resolved: {clash}")

    positions = {}
    for peer, engine_role in zip(connections, engine_roles):
        observed = await peer.get_observation(engine_role)
        positions[engine_role] = tuple(observed["position"])

    status = statuses[0]
    return {
        "status": "resolved",
        "cop_position": positions["cop"],
        "thief_position": positions["thief"],
        "captured": status["terminal_reason"] == "capture",
        "turn_count": status["turn_count"],
        "is_terminated": status["is_terminated"],
        "terminal_reason": status["terminal_reason"],
    }
