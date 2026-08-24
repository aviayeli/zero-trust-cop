"""Drive one sub-game on reference-v3 (PRD_10 FR2-FR5).

This loop plays on CLAIMS, not on reveals. Their turn carries a digest and
never a move, so there is no second move to feed a resolver: we walk OUR
piece, they walk theirs unseen, and capture is settled by the police's
``capture_claim`` and the thief's honest ``claim_response``.

That is the whole difference from ``push_match_loop``, and it is not a
routing detail. A loop that waits for the opponent's move on this wire waits
forever, however correctly it is addressed.

Two orderings are load-bearing:

* We push our turn BEFORE checking whether we were caught, so a caught
  thief's answer reaches the wire. The answer is the police's only
  notification; stopping first leaves it hunting a thief that already knows.
* Their claim for step n is answered in step n+1. A claim on the FINAL step
  therefore goes unanswered on the wire and is settled at ``submit_audit``,
  where both chains disclose the positions they sealed.
"""

from __future__ import annotations

import time

from mcp_server.turn_message import build_turn, sealed_payload
from scripts.claims_guards import DEFAULT_MAX_POLLS, accepted, await_turn

async def play_sub_game(client, inbox, side, choose, barriers, max_steps: int,
                        wait, observe=None, progress=None,
                        max_polls: int = DEFAULT_MAX_POLLS) -> dict:
    """Play one sub-game and disclose our sealed chain at the end.

    Args:
        client: a ``TurnClient`` pointed at the opponent.
        inbox: the list our ``receive_turn`` appends their turns to.
        side: our ``Side`` -- our piece, our smell, our claims.
        choose: ``(step) -> (move, hint, intent)`` -- our policy.
        barriers: the derived layout, sealed into every ``state`` string so a
            record is replayable without the seed that generated the board.
        max_steps: our own step budget, moves by US.
        wait: awaited between polls while their step is outstanding.
        observe: optional ``(their_turn) -> None`` -- where belief is updated.
        progress: optional ``(dict) -> None``, called once per step with what
            we pushed and when theirs landed. Four aborted series were argued
            from the opponent's inbound traffic alone, because our own side
            printed nothing until a series ended -- which for a series that
            never ends is nothing at all. Diagnostics only: the loop plays
            identically without it.

    Returns:
        A summary: steps played, terminal reason, our claim, their verdict.
    """
    terminal, steps_played = None, 0

    for step in range(1, max_steps + 1):
        move, hint, intent = choose(step)
        position = side.walk(move)
        commit, _ = client.seal(sealed_payload(
            side.config, step, position, move, intent, hint, barriers
        ))
        message = build_turn(step, side.sender, hint, side.smell_grid(),
                             commit, **side.extras(step))
        accepted(await client.turn(message), step)
        steps_played = step
        pushed_at = time.time()

        # After the push, never before: the answer we just sent is the only
        # notification the opponent gets.
        if side.caught:
            terminal = "capture"
            break

        # Re-send the SAME sealed turn while they stay silent: identical
        # bytes and digest, tolerated by the at-least-once contract, and it
        # stops their start time from having to match ours to the second.
        theirs = await await_turn(
            inbox, step, wait, max_polls, side.sender,
            repush=lambda: client.turn(message),
        )
        if progress is not None:
            progress({"step": step, "phase": "pushed", "move": move,
                      "pushed_at": pushed_at,
                      "theirs": round(time.time() - pushed_at, 2)})
        side.read(theirs)
        if observe is not None:
            observe(theirs)

        if side.captured_them:
            terminal = "capture"
            break

    # A capture on the final step has no turn left to answer in; our own
    # `caught` flag still knows, and the audit is where it is proven.
    terminal = terminal or ("capture" if side.caught else "survival")

    # What WE believe happened. A claim, not a verdict: their re-hash of our
    # records settles the sub-game, never this.
    result_claim = {"outcome": terminal, "steps": steps_played}
    # Copied BEFORE the audit, which clears the buffer by design so a second
    # audit cannot re-assert a sub-game. Without this copy a finished series
    # holds nothing but numbers and there is no log left to write.
    our_chain = client.records
    verdict = await client.audit(result_claim)
    return {
        "steps": steps_played,
        "terminal_reason": terminal,
        "result_claim": result_claim,
        "their_audit_response": verdict,
        "our_chain": our_chain,
        "their_turns": [dict(turn) for turn in inbox],
    }
