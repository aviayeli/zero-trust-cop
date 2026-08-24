# PRD 10 — Playing a sub-game on reference-v3

## Problem

We can HANDSHAKE on reference-v3 and we can AUDIT on it. We cannot PLAY on it.

`reference_surface.py` has said so since the surface was written: "Driving a
full sub-game on this surface needs a match loop that plays on claims rather
than reveals; that is a separate phase." This is that phase, and it is now
blocking a live series against ali-ahm1.

Three defects, in order of depth:

1. **We call a tool their loop never reads.** `push_client.commit()` pushes
   `receive_commit(role, step, h_commit)`. That tool is not on the
   reference-v3 surface at all; a move travels in `receive_turn`, with the
   digest under the message's `commit` key. ali-ahm1 reported this on
   2026-08-24; their server accepts `receive_commit` and their game loop
   never looks at it.

2. **Our own `receive_turn` writes to a list nobody reads.** Inbound turns
   land in `reference_surface`'s `inbox`; the push loop polls `PushStore`.
   Two disconnected inboxes, so fixing (1) alone would deliver their turns
   into a container no code consults.

3. **The wire carries no move, and our loop demands one.** `TurnMessage` is
   `{step, sender, hint, smell_grid, commit, timestamp}` plus four optional
   claim fields. There is no `move`: the move stays sealed until
   `submit_audit` at sub-game end. `push_match_loop` waits for a reveal and
   feeds the opponent's move into `MatchState.submit`, which resolves BOTH
   pieces. On this wire that move never arrives, so the sub-game stalls at
   step 1 no matter how the routing is fixed.

(3) is the real finding, and it changes the game model rather than a call
site. reference-v3 is an asymmetric-information protocol: **each peer
simulates only its own piece**, and capture is settled by claim and honest
answer, not by a shared resolver.

## Requirements

* **FR1** — Outbound half-turns go through `receive_turn(message=…)` carrying
  a conformant `TurnMessage`. Nothing on this wire calls `receive_commit` or
  `receive_reveal`.
* **FR2** — Inbound `receive_turn` messages are readable by step by the match
  loop, so a turn that arrives is a turn that is seen.
* **FR3** — A sub-game runs with our piece resolved locally and the
  opponent's position UNKNOWN. Our engine's two-piece resolver is not used on
  this wire; nothing fabricates their move.
* **FR4** — Capture is adjudicated by claim: the police attaches
  `capture_claim` (the cell it has just moved onto), the thief answers on its
  next turn with `claim_response = {claim, caught}`, answered HONESTLY —
  the sealed payload carries `position`, so a lie is detectable at audit.
* **FR5** — The thief attaches `win_claim = {"type": "survival"}` on the
  `survival_threshold` step.
* **FR6** — BOTH peers transmit their own accumulated decaying trail as
  `smell_grid`, every turn, under a CHEBYSHEV kernel of `smell_grid_size`.
  Every intensity is a NUMBER (a stringified one is refused by a conformant
  receiver) and every parameter comes from `config/game.json`'s `pheromones`
  block, never a literal. The wire kernel is a separate function from
  `strategy.pheromones.PheromoneField`'s Manhattan diamond: that one is our
  BELIEF model and is baked into the trained tables' state layout, this one
  is a negotiated disclosure term.
* **FR7** — The sub-game closes with `submit_audit`, records
  `{payload, nonce, commit}`, one per step we played.
* **FR8** — Our inbound `submit_audit` cross-checks each record's `commit`
  against the digest that peer actually PUSHED at that step. Re-hashing a
  record against itself proves only internal consistency: it would pass a
  chain that was rewritten wholesale after the fact.

## Non-goals

* Retiring the push dialect (`receive_commit` / `receive_reveal`). It stays
  registered behind `--dialect push` for a peer that speaks it; we simply
  stop CALLING it.
* Swap-capture. Our local resolver counts two agents exchanging cells as a
  capture. Nothing on this wire can observe it, so it is not adjudicated
  here, and that is stated rather than silently dropped.
* Mining the verbal channel. Their `hint` is free text up to 15 words, not
  our policy's direction vocabulary, so it feeds no belief update this phase.

## Both open questions — RESOLVED with ali-ahm1, 2026-08-24

1. **Where does the opponent's move come from mid-sub-game?** Nowhere. They
   confirmed they are fully claims-based: no move field is extracted
   mid-game, belief is updated from the opponent's `smell_grid` and `hint`,
   capture is settled by `capture_claim` + `claim_response` and verified at
   `submit_audit`. FR3 and FR4 stand as built.

2. **Who emits `smell_grid`?** BOTH, and our first build was wrong. We had
   the thief emitting and the police sending `{}`, reading the pheromone
   field as a scent only an evader leaves. Their SPEC §5 reading — "each peer
   emits its own" — is the better one and the fixture agrees in its own
   vocabulary: the field is REQUIRED on every TurnMessage from either sender.
   A peer sending `{}` is conformant and plays as a one-sided disclosure,
   silent about itself and fully informed about the other; with the sides
   swapping every sub-game that is worth a series. They also pinned the
   kernel as CHEBYSHEV 5×5 where ours was a 13-cell Manhattan diamond —
   twelve corner cells we were not disclosing. Both corrected under FR6.

   Nothing here is sealed: `smell_grid` is not part of the committed payload,
   so this cost a difference in what each side learns and could never have
   surfaced as a false tamper verdict.

## Acceptance

* Every previously passing test still passes; new behaviour arrives with a
  failing test first.
* No `.py` over 150 lines; no new tunable inlined as a literal.
* A full six-sub-game series runs against a scripted opponent with sides
  alternating, terminating on capture and on survival, with a clean mutual
  audit both ways.
