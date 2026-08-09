# TODO — Phase 6: Local P2P MCP Simulation

From `docs/PRD_06_Local_MCP_Simulation.md`, promoted from `PLAN_06` with the
D1–D3 rulings applied. The approval gate is **cleared for Steps 1–3**:
streamable HTTP on configured ports (D1), mirrored local truth (D2), and
`make_move` replaced by the secured surface (D3).

D5 is also ruled: match play is GREEDY, epsilon 0.0, configured via the
private `match_exploration_rate` key.

D7 is ruled: a stalled peer forfeits to `technical_loss`.
D4 is ruled: artifacts land under `logs/<group_id>/`.

D6 is ruled: barrier handling stays driven by `config/game.json`
(`max_barriers`), never by literals in Python.

Standing caveat, unchanged by that ruling: `GameEpisode.reset()` builds a
`Board` with an EMPTY barrier set and nothing calls `place_barrier()`, so no
barrier is ever placed and `max_barriers: 14` is currently an unapproached
cap. Matches and the Phase 5 tables therefore both assume a bare board.
Actually populating barriers is an engine change and its own phase.

Strict TDD throughout: a failing test precedes every implementation change,
and the RED must be confirmed before code is written. Each step is its own
commit. Every Python file at or under 150 lines, tests included.

Steps 1–4 are a dependency chain: the wire has no security until Step 1, so a
simulation before it would validate nothing. Steps 5–6 consume the match the
chain produces.

## 0. Promote to `PRD_06` and settle D1–D3 — DONE

- [x] Promote `PLAN_06` into `docs/PRD_06_Local_MCP_Simulation.md`.
- [x] Record the D1–D3 rulings: streamable HTTP on configured ports, mirrored
      local truth, and `make_move` replaced by the secured surface.
- [x] Add the transport ports to config as tunables (police 8801, thief 8802, (SUPERSEDED by PRD_07: cop 8802, thief 8801.)
      under a `[transport]` block; never literals in Python).

## 1. Put commit-reveal and signatures on the tool surface (the deferred 7b) — DONE

- [ ] Test first, against `create_app`'s returned tool callables:
  - [ ] A `submit_commitment` tool exists and rejects an invalid signature
        with `invalid_signature`.
  - [ ] It rejects a caller-supplied turn that is not
        `MatchState.turn_count` with `wrong_turn`.
  - [ ] A `reveal_move` tool rejects a reveal with no prior commitment
        (`reveal_before_commit`).
  - [ ] A reveal whose `(state, move, intent, nonce)` does NOT re-derive the
        committed digest is rejected — the anti-front-running property.
  - [ ] A signature valid at turn N is rejected when replayed at turn N+1.
  - [ ] A peer cannot submit as its opponent: the signed role must match the
        key that signed it.
  - [ ] Both peers must commit before either may reveal.
- [ ] Confirm RED, then wire `SubmissionGate` into `create_app`. Construct the
      `CommitmentBook`, load the peer public key from `config/<role>/peers/`,
      and register the tools. No new crypto — delegation only.
- [ ] Resolve D3: remove `make_move`, or gate it. Leaving an unauthenticated
      plaintext move tool beside the fix reopens the hole it closes.
- [ ] Confirm GREEN; every touched file at or under 150 lines. `server.py` is
      at 119 and will need splitting — put the tool registrations in their own
      module rather than growing it past the limit.

## 2. Load the trained policy into each peer — DONE (D5: greedy)

- [ ] Test first:
  - [ ] `create_app` builds an `AgentPolicy` for its own role.
  - [ ] The peer loads its `qtable_path` at startup and the loaded table is
        non-empty.
  - [ ] A missing table fails LOUDLY, not silently into an empty table.
  - [ ] A `state_layout_version` mismatch raises rather than loading.
  - [ ] Per D5, a competitive peer's effective epsilon is what the ruling
        says — assert it directly, do not infer it from behaviour.
  - [ ] The intent is truncated to `hint_max_words` BEFORE the commitment
        digest is computed, so the digest covers the truncated text.
- [ ] Confirm RED, then implement. Tests must not write to `data/`; point
      `qtable_path` under `tmp_path`.
- [ ] Confirm GREEN; confirm `src/engine/` still imports neither `strategy`
      nor `agent` (the Step 5 guard should catch any regression).

## 3. `src/scripts/run_local_mcp_match.py` — the two-peer harness — DONE except timeouts

- [ ] Test first:
  - [ ] Both peers start on their configured ports/channels and both answer
        `get_match_status`.
  - [ ] A full match runs to termination and the terminal reason is one of
        `capture` / `max_moves_reached`.
  - [ ] Every turn goes through commit → commit → reveal → reveal, in that
        order; assert the ordering, not just the outcome.
  - [ ] Both peers are torn down even when the match raises — no orphaned
        listeners after a failure.
  - [ ] **NOT DONE — reopened as a real gap.** `response_timeout_sec` guards
        `MatchState`'s action buffer, but under commit-reveal that buffer is
        never half-filled: `SubmissionGate.reveal_move` submits BOTH moves at
        once only after both peers reveal. Verified empirically — a peer that
        commits and then goes silent leaves the book at `half_revealed` with
        the action buffer EMPTY, so the lazy expiry never fires and the turn
        stalls forever. Closing this needs a timeout on `CommitmentBook`, which
        is new scope and a protocol question (what does a forfeited commitment
        phase resolve to?). Tracked as D7.
  - [ ] A tampered reveal from a hostile client is rejected over the wire,
        proving the security is live in the running server and not merely
        unit-tested.
- [ ] Confirm RED, then implement. At or under 150 lines; extract the per-turn
      exchange into its own module if not.
- [ ] Confirm GREEN.

## 4. Match log — DONE (D4)

- [ ] Test first:
  - [ ] Each peer writes its OWN log (D2 mirrored truth).
  - [ ] Per turn the log records: turn, both commitment digests, both
        signatures, both revealed `(state, move, intent, nonce)`, and the
        resolved positions.
  - [ ] The log is sufficient to replay the match with no other input.
  - [ ] Log writes honour D4's location, and tests write only under
        `tmp_path`.
- [ ] Confirm RED, then implement. Confirm GREEN.

## 5. Replay verifier — and prove it can FAIL — DONE

- [ ] Test first. `Verified OK` requires ALL of:
  - [ ] every commitment digest re-derives from its revealed tuple;
  - [ ] every signature re-verifies for its turn;
  - [ ] replaying the logged actions through a fresh `GameEpisode` reproduces
        the logged final state;
  - [ ] the two peers' logs agree.
- [ ] **Guard the guard.** A verifier that always returns `Verified OK` is
      worthless. Assert it REJECTS each of, independently:
  - [ ] a flipped move in the log (replay diverges);
  - [ ] a forged signature (signature check fails);
  - [ ] a reveal edited so it no longer matches its commitment digest;
  - [ ] two peer logs that disagree.
- [ ] Confirm RED, then implement. Confirm GREEN.

## 6. Execute the simulation and commit the artifacts — DONE

- [ ] Run a full local match end to end, recording the seed.
- [ ] Verify the produced log reports `Verified OK`.
- [ ] Confirm the peers played from the trained tables — not empty ones.
- [ ] Commit the log per D4, recording the seed and the outcome so the match
      is reproducible and defensible.

## Out of scope for Phase 6

- Interop with the opposing group's peer. Passing locally proves our two
  peers agree with EACH OTHER, not that either matches another team's reading
  of the schema. This phase removes the blocker, not the eventual test.
- Retraining or any change to the Q-tables.
- Any change to `config/game.json`.
- Barrier placement during the match (D6) — the tables never saw an interior
  barrier, so adding one tests the protocol against an untrained policy.
