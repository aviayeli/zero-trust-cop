# TODO 10 — Playing a sub-game on reference-v3

Derived from `PLAN_10_Reference_v3_Play.md`. Strict TDD: a failing test first,
every step. An item is checked only when the test proving it passes.

## 10.1 The smell trail (FR6)

- [x] **Test first**: the thief's grid keys are `'r,c'` strings and every
      intensity is a NUMBER; the field decays; the police's grid is `{}`.
- [x] `src/mcp_server/smell_trail.py` — wraps the existing `PheromoneField`
      so no new decay maths is written, and reads the strongest cell out of
      an inbound grid.

## 10.2 The turn message (FR1)

- [x] **Test first**: a built message passes the REAL
      `wire_v3.validate_turn_message`; optional fields appear only when set.
- [x] `src/mcp_server/turn_message.py` — `build_turn` and `sealed_payload`,
      the latter in the kit's `grid=7x7;self=[4, 3];barriers=[]` spelling.

## 10.3 Our piece and our claims (FR3-FR5)

- [x] **Test first**: an illegal move resolves to STAY; the police claims its
      own new cell; a claimed thief answers `caught` honestly; a thief on
      another cell answers `false`; `win_claim` appears on the threshold step.
- [x] `src/mcp_server/claims_side.py`.

## 10.4 The outbound client (FR1, FR7)

- [x] **Test first**: the only tools called are `receive_turn` and
      `submit_audit`; every sealed step is buffered and reaches the audit,
      asserted BY COUNT; an empty audit is refused.
- [x] `src/mcp_server/turn_client.py`.

## 10.5 The sub-game loop (FR2, FR3)

- [x] **Test first**: their turn lands in the inbox and is read by step;
      capture terminates AFTER our answer has gone out; survival terminates
      at the budget; a peer that never sends raises TimeoutError naming the
      step.
- [x] `src/scripts/claims_match_loop.py`.

## 10.6 The series (alternating sides)

- [x] **Test first**: six sub-games, sides alternating, inbox and piece reset
      between them, one audit per sub-game.
- [x] `src/scripts/claims_runner.py`, reusing `push_runner.role_schedule`.
- [x] `src/scripts/run_reference_match.py` — the live entry point.

## 10.7 The audit cross-check (FR8)

- [x] **Test first**: a record that re-hashes against itself but whose
      `commit` differs from the digest pushed at that step is a MISMATCH.
- [x] `src/mcp_server/reference_tools.py` — compare against the inbox.

## 10.8 Sent to ali-ahm1

- [x] Asked where the opponent's move comes from mid-sub-game. **ANSWERED:**
      nowhere — they are fully claims-based, same model, no extension key.
      10.3 and 10.5 stand as built.
- [x] Asked who emits `smell_grid`. **ANSWERED, and we were wrong:** both
      peers emit, under a CHEBYSHEV kernel. Fixed in 10.11.

## 10.9 Found while building — recorded

- [x] `submit_audit` re-hashed each record against its OWN commit and nothing
      else, so a chain rewritten wholesale after the sub-game — payload,
      nonce and commit together — passed cleanly. The digests they pushed were
      already in `inbox`; comparing against them is what makes the seal
      binding, and it is now `mcp_server/audit_check.py` (FR8).
- [x] `reference_tools.py` split at the judge/transport seam rather than
      growing to 141 lines. The verdict logic is `audit_check`.
- [x] The push dialect is left registered and untouched. It is opt-in, an
      opponent may still speak it, and this phase's finding is that we must
      stop CALLING it — not that it must be removed.

## 10.10 Known gaps, stated rather than hidden

- [ ] **Swap-capture is not adjudicated on this wire.** Our local resolver
      counts two agents exchanging cells as a capture; nothing in a
      TurnMessage can observe it. Both peers' sealed chains disclose every
      position at audit, so it is visible after the fact and unscorable
      during play.
- [ ] **A capture claimed on the FINAL step is answered by the audit, not by
      a turn.** There is no step left to carry the `claim_response`.
- [x] ~~The thief's smell semantics are our reading, not a confirmed term.~~
      **Confirmed and corrected 2026-08-24 — see 10.11.**
- [ ] **The falloff CURVE is still ours.** We emit
      `emit_intensity * (radius + 1 - chebyshev_distance) / (radius + 1)`,
      i.e. 0.9 / 0.6 / 0.3. The agreed terms pin the intensity, the decay and
      the grid size but not the shape of the ramp between them. Not
      launch-blocking: both peers read the grid by argmax, and the argmax is
      the current cell under any monotone falloff. Stated to ali-ahm1.

## 10.11 Corrected after ali-ahm1's reply (2026-08-24)

- [x] **Test first**: both sides emit a non-empty trail centred on their own
      cell; the kernel is a full 25-cell Chebyshev box with the four corners
      present; the edge clips to 9 cells and never wraps.
- [x] `smell_trail.py` no longer wraps `PheromoneField`. The two kernels are
      now different functions and the split is the point: `PheromoneField` is
      our BELIEF model, baked into the trained tables' state layout, and
      changing it would silently invalidate every shipped Q-value; this is a
      negotiated DISCLOSURE term. Neither may quietly become the other.
- [x] `Side` emits for both roles, opening deposit on the start cell, so the
      very first turn discloses a trail rather than an empty field.
- [x] `tests/mcp_server/test_claims_side.py` split at the 150-line limit;
      claims and answers now live in `test_claims_answers.py`.

## 10.12 Found in the first live connection (2026-08-24)

- [x] **We dialled ourselves.** `--opponent-url` was set to
      `luxury-pregnancy-wilder.ngrok-free.dev`, which is OUR OWN tunnel to
      port 8802. The ngrok inspector settles it: 36 `receive_turn` calls
      reaching our police peer, every one carrying `sender: "police"`. Both
      peers answer the same tool names, so nothing refused anything.
- [x] **And the loop let it pass.** `_await_turn` matched on `step` alone, so
      our own turn satisfied the wait for theirs and a full 35-step sub-game
      completed against a mirror — audits clean, outcome plausible, opponent
      never involved. A one-second misconfiguration became a phantom result.
- [x] **Test first**: our own turn in our own inbox raises at once, naming
      `--opponent-url`; a genuine opponent turn is still read.
- [x] `_await_turn` now takes the side we are playing and refuses a turn
      whose `sender` is ours. There is no legitimate route for that message,
      so it is a loud error rather than a timeout five minutes later.
- [ ] `config/*/game.toml` still carries `opponent_url = "https://REPLACE-ME-
      ali-ahm1-*.ngrok-free.dev/mcp"`. The runner takes the URL on the command
      line so this did not block the run, but it is the second place the
      wrong endpoint can hide.

## 10.13 Settled in the pre-launch exchange (2026-08-24)

- [x] **`negotiate` is now sent, before the first push of EVERY sub-game.**
      Nothing ever sent one: our server verified theirs from the reference-v3
      phase and our runner opened a session and started pushing. It looked
      sound because our own `receive_turn` does not gate on a handshake.
      Theirs does one layer in — ali-ahm1 confirmed their server queues turns
      ungated while their GAME LOOP will not read that queue until negotiate
      completes, so a turn pushed first is ignored rather than refused, which
      from our side is indistinguishable from a slow peer.
- [x] `src/mcp_server/negotiate_client.py` runs the three checks we already
      apply inbound, in the direction we never ran them: their signature over
      their terms, their terms against ours (naming the first differing
      value), and the PAIRING. Every failure raises: playing on past a
      refused handshake pushes a whole sub-game into a queue nobody reads.
- [x] `reference_surface` / `dialects` / `server` now expose the identity
      source, so the runner opens a handshake with the same declaration the
      server answers one with, rather than rebuilding it and drifting.
- [x] **Decay is SUBTRACTIVE on the wire** (`v - decay_per_step`, clamped),
      agreed with ali-ahm1 as `subtractive_chebyshev_v1`. Ours was geometric.
      `strategy.pheromones.PheromoneField` KEEPS the geometric form — that is
      the belief model behind the trained tables, not a disclosure term.
- [ ] **`subtractive_chebyshev_v1` is an agreement, not a citation.** The
      vendored CORE fixtures carry `decay_per_step: 0.1` as a VALUE and
      define no recurrence anywhere; nothing in them names that identifier.
      Recorded as agreed-with-the-opponent rather than as pinned-by-the-kit.
      Ask ali-ahm1 which kit document registers it.

## 10.14 Found while making the decay subtractive

- [ ] **The argmax of a received grid does NOT name the opponent's current
      cell.** Deposits accumulate and a neighbour is one Chebyshev step away,
      so walking (3,3) -> (3,4) leaves both cells at exactly 1.4. The
      geometric form broke that tie by 0.03, which was luck rather than a
      property — and we told ali-ahm1 the argmax was reliable before the
      decay was settled. `claims_runner._observer` still deposits the argmax:
      it is a belief HINT and nothing treats it as a position, but a real
      estimator over the whole received field is the honest next step.
