# PRD 09 — The push dialect (ali-ahm1 / reference-v3 family)

## Problem

Our peer and ali-ahm1's peer cannot exchange a single move, and the reason is
architectural rather than cosmetic.

**Ours is a gate.** The opponent CALLS us: `submit_commitment(role, turn,
h_commit, signature)` then `reveal_move(role, turn, state, move, intent,
nonce, signature)`, and polls `get_observation` / `get_match_status`. A
`CommitmentBook` holds both halves and the turn resolves only when both sides
have revealed.

**Theirs is pure push.** Every tool they serve is `receive_*` and every one
takes `role` as an argument — one peer serving both roles, no polling tool of
any kind. Read from their live `tools/list` on 2026-08-24:

    receive_step0(role, declaration, signature)
    receive_commit(role, step, h_commit)
    receive_reveal(role, step, move, hint, intent)
    receive_ack(role, step)
    receive_capture_claim(role, claimed)
    receive_final_audit(role, nonces)

They have stated they cannot drive our surface: *"our codebase has no client
methods that call submit_commitment, reveal_move, get_observation, or
get_match_status. Zero."* So the adaptation is ours to build.

## The scope they understated

They described this as an adapter that CALLS their tools. It is not: the
transport is symmetric, so their client will call `receive_*` **on us**, and
we serve none of those six names. This phase is therefore a full second
dialect — inbound tools, an outbound client, and a match loop — not a wrapper.

## What this dialect gives up

Both losses are inherent to their protocol, not to our implementation:

1. **No per-turn authentication.** `receive_commit` carries no `signature`.
   Our Ed25519 signature over `{role, turn, h_commit}` is what establishes
   WHO submitted a move — `crypto.py` is explicit that commit-reveal alone
   proves only that a reveal matches a commitment by *whoever holds the
   nonce*. On this path nothing binds a move to a peer identity.
2. **No per-turn commitment binding.** `receive_reveal` carries no `nonce`
   and no `state`. A reveal cannot be checked against its commitment while
   the sub-game is running; detection is deferred to the final audit.

Deferred detection is the reference-v3 model and is defensible. Accepting
UNAUTHENTICATED moves on our live wire is not, which is why FR5 gates it.

## The audit gap — open, and not ours to close alone

`receive_final_audit(role, nonces)` carries nonces and nothing else. To
re-hash their chain we need the PAYLOAD each `h_commit` sealed, and their
`receive_reveal` gives us only `(move, hint, intent)` — no `state`, no
position, no step-0 record. Unless their `nonces` entries carry the payloads,
the deferred audit cannot actually be computed, and this dialect would provide
**no verification at all** rather than late verification.

This is a question for ali-ahm1, recorded in TODO 9.5. Until it is answered,
FR4 requires the audit to report `unverifiable` explicitly. Reporting a clean
audit we did not compute would be worse than reporting none.

## Requirements

* **FR1** — Serve the six inbound `receive_*` tools, validated before any
  state change, with refusals that name the offending field.
* **FR2** — An outbound client that pushes our commit, reveal, ack and final
  audit to their endpoint, dropping `signature` from the commit and `nonce` /
  `state` from the reveal, per their signatures.
* **FR3** — Buffer every nonce we drop and emit them all through
  `receive_final_audit` at sub-game end.
* **FR4** — At final audit, re-hash whatever CAN be reconstructed and mark
  the rest `unverifiable`. Never report a pass that was not computed.
* **FR5** — The dialect is OPT-IN (`--dialect push`). Our own authenticated
  surface stays the default, and the unauthenticated tools are not registered
  unless the flag is given, so the live wire cannot silently widen.
* **FR6** — `step` is a per-sender counter, 1..`max_steps`, 35 moves EACH
  (agreed with ali-ahm1). Roles alternate per sub-game; SG1 is aviayeli
  police / ali-ahm1 thief.

## Non-goals

* The `_bl` variant tools (`receive_commit_bl`, `receive_reveal_bl`,
  `receive_audit_bl`) they also serve. Not requested, not agreed.
* Retiring our own dialect or the reference-v3 surface. Both stay.
* Making this the default for any counted game.

## Acceptance

* Every previously passing test still passes; new behaviour arrives with
  tests written first.
* No `.py` over 150 lines; no new tunable inlined as a literal.
* With the flag absent, `tools/list` is byte-identical to today's.
* README's self-checked figures remain accurate.
