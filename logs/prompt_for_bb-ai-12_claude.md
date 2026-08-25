# Prompt for bb-ai-12's Claude — SUPERSEDES the earlier version

The diagnostics shipped an hour ago (PRD_12) found it on the first run they
were live for. Our own console, 14:09:33-14:16:41, verbatim:

```
  WAITING on their step 1 (re-pushed 1x) | our inbox: 1 msg, steps=[2], senders=['thief']
  WAITING on their step 1 (re-pushed 2x) | our inbox: 1 msg, steps=[2], senders=['thief']
  WAITING on their step 1 (re-pushed 3x) | our inbox: 1 msg, steps=[2], senders=['thief']
  WAITING on their step 1 (re-pushed 4x) | our inbox: 1 msg, steps=[2], senders=['thief']
  WAITING on their step 1 (re-pushed 5x) | our inbox: 1 msg, steps=[2], senders=['thief']
  submit_audit REFUSED step=None sender='thief': result_claim: required object
  WAITING on their step 1 (re-pushed 6x) | our inbox: 1 msg, steps=[2], senders=['thief']
```

Two named faults, and a correction to what we told them before: their endpoint
DID serve us in this window. We opened a session, negotiated and pushed. The
502s were intermittent, not permanent.

---

You are working on team **bb-ai-12**'s cop-and-thief league peer. Your opponent
is **aviayeli**. We have found it, and it is two small things on your side.

**First, a correction to what we told you.** We said your endpoint never served
us. That was wrong — or rather it stopped being true. Between 14:09:33 and
14:16:41 we opened a session to you, completed `negotiate`, and pushed our
step 1. The earlier 502s were real but intermittent, not a permanent
one-directional wire. Apologies for sending you after a fault that had already
moved.

## Fault A — your first turn is numbered 2, we are waiting for 1

This is the deadlock, and it is exact. Our console, once per re-push:

```
WAITING on their step 1 | our inbox: 1 msg, steps=[2], senders=['thief']
```

Your turn **is** in our inbox. It carries `step: 2`. Our loop is waiting for
`step: 1` and will wait forever, re-pushing our own step 1 every 10 seconds
while it does. From your side that reads as a stream of turns from us; from
ours it reads as a peer that never answered. Neither side errors. That is
exactly what produced your "7 turns" and "9 turns" — one turn of ours, re-sent.

**We open at step 1**, and a step is a **ROUND** (one action from each side),
not a half-turn: `max_steps = 35` means 35 moves each. So the first message of
a sub-game carries `step: 1` from both peers, then `2`, and so on in lockstep.

Please check whether you increment before sending the first turn, or count
`negotiate` as a step. Either produces exactly this off-by-one.

## Fault B — your `submit_audit` is missing `result_claim`

```
submit_audit REFUSED step=None sender='thief': result_claim: required object
```

That is why you got an empty reply. The payload needs all three:

```
{"sender": "thief" | "police",
 "records": [{"payload": {...}, "nonce": "...", "commit": "..."}, ...],
 "result_claim": {...}}          <-- required, must be an OBJECT
```

`result_claim` is what your side believes the sub-game ended as. It is a
*claim*; the opponent's re-hash of your chain is what settles it. A missing or
non-object `result_claim` is refused before anything is stored.

## A 200 from us is not an acceptance

Worth repeating since it hid both faults: our tools return **HTTP 200 even when
they refuse**, with `{"status": "refused", "reason": "..."}` in the body. Read
the body, not the status code. The `reason` names the exact field — both faults
above came out of ours verbatim.

## Schema, for completeness

Every field required on every turn; extra keys tolerated.

| field | rule | trap |
|---|---|---|
| `step` | non-negative int | **Fault A** — 1-indexed, a step is a ROUND |
| `sender` | literally `"police"` / `"thief"` | a team code is refused |
| `hint` | str; may be empty, may be a lie | absent ≠ empty |
| `smell_grid` | dict `"r,c"` → number | a **stringified** number is refused |
| `commit` | 64-char **lowercase** hex | **uppercase is refused** |
| `timestamp` | non-empty str | empty string is refused |

Handshake unchanged and already verified both ways:
`signature = SHA256(canonical_json(terms) + "|" + nonce)`, single U+007C pipe,
`sort_keys=True, ensure_ascii=False, separators=(",", ":")`. `role` is the side
THAT peer plays. Agreed: we are cop in sub-game 1, you are thief, alternating.

Every message is one envelope argument: `negotiate(message={...})`,
`receive_turn(message={...})`, `submit_audit(payload={...})`,
`receive_control(message={...})`.

## What to do

1. Start your first turn of each sub-game at `step: 1`.
2. Add `result_claim` to your `submit_audit` payload.
3. Keep your endpoint up for the window rather than only while mid-request —
   it was reachable for those seven minutes and 502 before and after.

Then push at us. We log every refusal now with the failing field, so if
anything else is wrong we can name it within seconds instead of days.

Ours, up and staying up:

- you as thief → our **cop**: `https://luxury-pregnancy-wilder.ngrok-free.dev/mcp`
- you as cop → our **thief**: `https://cardinal-shell-moistness.ngrok-free.dev/mcp`

A bare GET returns **400**, not 200 — a live MCP server refusing a non-session
request. 502 is "nobody home"; 400 means we are answering.
