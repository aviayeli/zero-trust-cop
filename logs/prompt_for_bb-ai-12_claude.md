# Prompt for bb-ai-12's Claude — hand this over as-is

Verified before writing (2026-08-25 14:12 local):

- our two peers: HTTP 400 to a bare GET = live MCP servers refusing a
  non-session request. Up since 14:0x and staying up.
- their endpoint: HTTP 502 x3 at 14:12:23-24 = tunnel up, nothing behind it.
- we have never completed a single bidirectional turn with them.

---

You are working on team **bb-ai-12**'s cop-and-thief league peer. Your
opponent is team **aviayeli**. Two attempts at sub-game 1 have failed and we
have jointly narrowed it down. Here is the state and what we need from your
side.

## Where it actually stands

We have **never completed one bidirectional turn**. Your peer reached ours and
pushed messages; ours has never once opened a session to yours. Two faults,
one on each side. Ours is fixed. Yours is not, and it is the blocker.

## Fault 1 — your endpoint does not serve us (blocking)

`https://comic-leverage-paprika.ngrok-free.dev/mcp` returns **HTTP 502** to us,
consistently. Probed 12:53:25-12:54:17 (6x), 13:31:50-51 (3x), 14:12:23-24
(3x). 502 is ngrok saying the tunnel is up but nothing is listening on the
local port behind it.

reference-v3 is **symmetric push**: both sides SERVE and both sides DIAL. We
push our half-turns to *your* `receive_turn` exactly as you push yours to ours.
A peer that only dials out can send but can never be sent to, and our match
loop cannot even enter its turn loop until it has opened a session to you.
That is why your turns landed in our inbox and nothing came back.

**Please check:** with your thief running, hit your own public URL **from
outside your machine** (not localhost). If it 502s, your peer is not bound to
the port your tunnel forwards to. Confirm the tunnel's upstream port equals the
port your peer actually binds, and that the peer stays bound for the whole
window rather than only while it is mid-request.

## Fault 2 — a 200 from us is not an acceptance (probable, and hidden)

Our `receive_turn` returns **HTTP 200 even when it refuses your message**. The
body carries `{"status": "refused", "reason": "<field>: <what was wrong>"}` and
the message is **not** stored. Your log of "all 200/202" is therefore not
evidence we accepted anything.

**Please check the response BODY**, not the status code, for every
`receive_turn` and `negotiate` call. If it says `refused`, the `reason` names
the exact field.

## Exact TurnMessage schema we validate against

Every field required on every turn. Unknown extra keys are tolerated.

| field | rule | the trap |
|---|---|---|
| `step` | non-negative int | see step semantics below |
| `sender` | literally `"police"` or `"thief"` | a team code here is refused |
| `hint` | str; may be empty, may be a lie | absent ≠ empty |
| `smell_grid` | dict of `"r,c"` → number | a **stringified** number is refused |
| `commit` | 64-char **lowercase** hex | **uppercase hex is refused** |
| `timestamp` | non-empty str | an empty string is refused |

Two silent killers there: **uppercase hex in `commit`**, and **numbers sent as
strings in `smell_grid`**. Both look fine to a human and both are refused.

**Step semantics.** A step is a ROUND — one action from each side — not a
half-turn. `max_steps = 35` means 35 moves *each*. We open at **step 1**. Our
loop waits for *your* message carrying the step number it is on; if you number
from 0, we will wait forever while you re-send happily and neither side errors.

## Handshake

- `negotiate(message={terms, nonce, signature, identity?, sub_game_number?, role?})`
- `signature = SHA256(canonical_json(terms) + "|" + nonce)` — single U+007C
  pipe; `canonical_json` is `sort_keys=True, ensure_ascii=False,
  separators=(",", ":")`. You have already verified this reproduces.
- `role` is **the side THAT peer is playing**, not the side of the peer being
  called. If we both declare the same role the handshake is refused.
- Agreed: **we are cop in sub-game 1, you are thief**, alternating after.
- All 14 terms must value-match. Already confirmed on both sides.

## Every message is ONE envelope argument

`negotiate(message={...})`, `receive_turn(message={...})`,
`submit_audit(payload={...})`, `receive_control(message={...})`. Flat
parameters fail schema validation on the caller's side before reaching us.

## Use us as an oracle

We just shipped a change that logs **every** inbound refusal server-side with
the tool, the reason, and the step and sender we refused. So if you push a turn
at us now and it is malformed, we can tell you the exact failing field within
seconds — something neither of us could do for the last two attempts.

## What to do

1. Fix the 502 — make your peer serve that URL while it runs.
2. Tell us when it is answering from outside, and we will run our read-only
   pre-flight against it. It opens no sub-game and pushes no turn: one
   `negotiate` at `sub_game_number = 0`, which appears in no schedule either
   side plays.
3. When both sides verify, we run the friendly dry-run: 2 sub-games, artifacts
   off, nothing reported.

Our endpoints, up now and staying up:

- you as thief → our **cop**: `https://luxury-pregnancy-wilder.ngrok-free.dev/mcp`
- you as cop → our **thief**: `https://cardinal-shell-moistness.ngrok-free.dev/mcp`

A bare GET on those returns **HTTP 400**, not 200. That is the MCP server
correctly refusing a non-session request — a live peer, not a broken one. 502
is the "nobody home" signal; 400 means we are answering.
