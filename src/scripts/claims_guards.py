"""What the wire said, judged before the loop acts on it (PRD_10 10.5).

Split from ``claims_match_loop`` at the play/judge seam. The loop decides what
to send; these two decide whether what came back may be believed. Both exist
because of a live failure, not a design instinct:

* ``await_turn`` matched on ``step`` alone, so a self-dial fed us our own
  turns and a full sub-game completed against a mirror -- clean audits,
  plausible outcome, opponent never involved.
* the push response was DISCARDED, so a peer refusing every turn looked
  exactly like one that was merely quiet, and we waited out the poll budget
  instead of reporting the reason they had already handed us.

Both now fail loudly and name the cause. PRD_12 adds a third: a stalled wait
says so per re-push instead of printing nothing at all.
"""

from __future__ import annotations

# Polls to wait for one of their steps before declaring the peer stalled. A
# match that blocks forever is worse than one that fails.
DEFAULT_MAX_POLLS = 600


def _stall(inbox, step: int, attempt: int) -> dict:
    """What tells a desync from a dead peer: ``inbox_depth`` 0 is "they never
    reached us", non-zero is "they did, and we are not matching it"."""
    return {
        "step": step,
        "attempt": attempt,
        "inbox_depth": len(inbox),
        "inbox_steps": [m.get("step") for m in inbox],
        "senders": sorted({m.get("sender") for m in inbox if m.get("sender")}),
    }


async def await_turn(inbox, step: int, wait, max_polls: int, ours: str,
                     repush=None, repush_every: int = 20,
                     on_repush=None) -> dict:
    """Block until THEIR turn for ``step`` is in the inbox.

    ``ours`` is the side WE are playing, and matching on ``step`` alone was a
    real defect: point ``--opponent-url`` at our own tunnel and every turn we
    push lands back in our own inbox with a matching step, so the loop
    consumed it as the opponent's and completed a whole sub-game against a
    mirror -- audits clean, outcome plausible, opponent never involved.

    ``repush`` re-sends OUR turn for this step every ``repush_every`` polls
    while they stay silent. We used to push once: if their loop was not
    reading yet -- their process starts, plays and exits on its own schedule
    -- our turn sat in a queue nobody drained and both sides waited out their
    budgets. Re-sending the SAME sealed turn is free (identical bytes,
    identical digest, and the receiver must tolerate a repeat under the kit's
    at-least-once contract) and turns a coordination problem into a retry.

    A repush that RAISES is swallowed -- their endpoint may be down for the
    seconds we retry into, which is a reason to keep waiting, not to end the
    sub-game. ``on_repush`` is a diagnostic and is swallowed for the same
    reason, more strongly: it must never be able to end a graded series.

    Raises:
        RuntimeError: our OWN turn is in our own inbox. There is no
            legitimate route for that, so it is raised at once rather than
            left to surface as a timeout minutes later.
        TimeoutError: their turn never arrived, named with the step and what
            the inbox holds, so a desync reads as a desync.
    """
    attempts = 0
    for poll in range(max_polls):
        for message in inbox:
            if message.get("sender") == ours:
                raise RuntimeError(
                    f"our own turn (sender {ours!r}, step {message.get('step')}) "
                    "came back in our own inbox: --opponent-url is pointing at "
                    "one of OUR tunnels, not at the opponent's. Both peers "
                    "answer the same tool names, so a self-dial plays a full "
                    "sub-game and audits clean."
                )
            if message.get("step") == step:
                return message
        if repush is not None and poll and poll % repush_every == 0:
            attempts += 1
            if on_repush is not None:
                # Swallowed like the re-push itself: a diagnostic that can end
                # a graded series is worse than no diagnostic.
                try:
                    on_repush(_stall(inbox, step, attempts))
                except Exception:
                    pass
            try:
                await repush()
            except Exception:
                pass
        await wait()
    raise TimeoutError(
        f"opponent never sent step {step}; inbox holds steps "
        f"{sorted(m.get('step') for m in inbox)}"
    )



def _accepted(reply, step: int) -> None:
    """Raise if they said no to this turn.

    The push response used to be discarded, so a peer refusing every turn
    looked exactly like a peer that was merely quiet -- and we waited out the
    poll budget instead of reporting the reason they had already given us.

    Only an EXPLICIT no counts. ali-ahm1 answers ``{"accepted": true}`` with
    no ``status`` at all, so treating an unfamiliar shape as a refusal would
    stall a healthy series; treating an explicit refusal as noise is how a
    fixable message goes unread.

    Raises:
        RuntimeError: they refused, quoting their own reason.
    """
    if not isinstance(reply, dict):
        return
    refused = reply.get("status") == "refused" or reply.get("accepted") is False
    if refused:
        raise RuntimeError(
            f"opponent refused our step {step}: "
            f"{reply.get('reason', 'no reason given')}"
        )


def accepted(reply, step: int) -> None:
    """Raise if they said no to this turn.

    The push response used to be discarded, so a peer refusing every turn
    looked exactly like a peer that was merely quiet -- and we waited out the
    poll budget instead of reporting the reason they had already given us.

    Only an EXPLICIT no counts. ali-ahm1 answers ``{"accepted": true}`` with
    no ``status`` at all, so treating an unfamiliar shape as a refusal would
    stall a healthy series; treating an explicit refusal as noise is how a
    fixable message goes unread.

    Raises:
        RuntimeError: they refused, quoting their own reason.
    """
    if not isinstance(reply, dict):
        return
    refused = reply.get("status") == "refused" or reply.get("accepted") is False
    if refused:
        raise RuntimeError(
            f"opponent refused our step {step}: "
            f"{reply.get('reason', 'no reason given')}"
        )
