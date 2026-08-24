"""Drive one sub-game on the push dialect (PRD_09 FR3, TODO 9.4).

Lockstep without a gate. Each step we push our commit and then our reveal,
and wait for theirs to land in the store their pushes fill. Nothing checks
their reveal against their commit while this runs -- on this wire the nonces
do not exist yet -- so the only verification is the audit at the end, through
``submit_audit``, whose records carry the payload beside the nonce and are
therefore actually recomputable.

Commit strictly precedes reveal at every step. That ordering is the one
property of simultaneity this dialect still gives us: revealing first would
hand the opponent our move before they have sealed theirs.

``step`` is a PER-SENDER counter. Each side numbers its own chain
1..``max_steps``, so ``max_steps: 35`` means 35 moves EACH -- agreed with
ali-ahm1 on 2026-08-24, and worth restating here because two peers reading it
as rounds versus half-turns desync with nothing to diagnose.
"""

from __future__ import annotations

from secrets import token_hex

from mcp_server import interop

# Nonce length in bytes (128 bits), matching mcp_server.crypto. The nonce is
# what hides the move: the move set has five elements, so a predictable nonce
# lets an opponent brute-force our commitment before we reveal.
_NONCE_BYTES = 16

# Polls to wait for one of their steps before declaring the peer stalled.
# A match that blocks forever is worse than one that fails: the operator
# cannot tell a slow opponent from a dead one.
_DEFAULT_MAX_POLLS = 600


async def _await_step(store, step: int, wait, max_polls: int):
    """Block until their commit AND reveal for ``step`` have both landed.

    Raises:
        TimeoutError: the step never arrived. Named with the step so the
            operator knows how far the sub-game got.
    """
    for _ in range(max_polls):
        if step in store.commits and step in store.reveals:
            return store.reveals[step]
        await wait()
    raise TimeoutError(
        f"opponent never completed step {step}: "
        f"commit={'yes' if step in store.commits else 'no'}, "
        f"reveal={'yes' if step in store.reveals else 'no'}"
    )


async def play_sub_game(
    client, store, choose, advance, max_steps: int, wait,
    max_polls: int = _DEFAULT_MAX_POLLS,
) -> dict:
    """Play one sub-game and disclose our nonces at the end.

    Args:
        client: a ``PushClient`` pointed at the opponent.
        store: our ``PushStore``, filled by their inbound pushes.
        choose: ``(step) -> (move, hint, intent)`` -- our policy.
        advance: async ``(step, our_move, their_move) -> dict`` -- our
            engine. Awaited because ``MatchState.submit`` resolves a turn
            behind an asyncio.Lock, which is what guarantees exactly one
            engine step per turn (FR8). A truthy ``terminated`` ends the
            sub-game.
        max_steps: our own step budget, moves by US.
        wait: awaited between polls while their step is outstanding.

    Returns:
        A summary: steps played, terminal reason, and the audit they returned.
    """
    steps_played, terminal = 0, None

    for step in range(1, max_steps + 1):
        move, hint, intent = choose(step)
        payload = {"step": step, "move": move, "hint": hint, "intent": intent}
        nonce = token_hex(_NONCE_BYTES)

        await client.commit(step, interop.commit(payload, nonce), nonce, payload)
        await client.reveal(step, move=move, hint=hint, intent=intent)

        theirs = await _await_step(store, step, wait, max_polls)
        outcome = await advance(step, move, theirs["move"])
        steps_played = step

        if outcome.get("terminated"):
            terminal = outcome.get("terminal_reason")
            break

    # What WE believe happened. A claim, not a verdict: their re-hash of our
    # records settles the sub-game, never this.
    result_claim = {
        "outcome": terminal or "max_steps_reached",
        "steps": steps_played,
    }
    audit = await client.final_audit(result_claim)
    return {
        "steps": steps_played,
        "terminal_reason": terminal,
        "result_claim": result_claim,
        "their_audit_response": audit,
    }
