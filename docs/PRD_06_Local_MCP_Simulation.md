# PRD — Phase 6: Local P2P MCP Simulation

Promoted from `PLAN_06_Local_MCP_Simulation.md` with the D1–D3 rulings
applied. This is the authority for Phase 6; `PLAN_06` keeps the design
reasoning and the verified audit of what was already built.

## Purpose

Prove the wire protocol by playing a full match between two independent local
MCP peers, with commit-reveal and Ed25519 signatures actually in force and the
Phase 5 Q-tables driving the moves — then prove the match happened as claimed
by verifying its log.

This removes the external blocker on Step 7b. It does **not** remove the need
for interop testing: passing locally proves our two peers agree with each
other, not that either matches another team's reading of the schema.

## Approved decisions

- **D1 — Transport.** Streamable HTTP over configured local ports
  (police 8801, thief 8802 by default). Ports are tunables and live in config. (SUPERSEDED by PRD_07: cop 8802, thief 8801.)
- **D2 — Topology.** Mirrored local truth. Each peer keeps its own
  `GameEpisode` as ground truth and independently validates the opponent's
  signed commit-reveal disclosures every turn. Neither peer trusts the other's
  engine. Divergence is detected per turn, not assumed away.
- **D3 — Security on the wire.** The unauthenticated `make_move` tool is
  REPLACED. `crypto.py`, `commitments.py`, `identity.py` and `SubmissionGate`
  are wired onto the FastMCP surface, and `AgentPolicy` supplies moves from
  the trained tables.

Still open: **D4** (log location and tracking), **D5** (match-time
exploration), **D6** (barriers during the match).

## Functional requirements

### FR1 — Authenticated tool surface

- The peer app exposes `submit_commitment(role, turn, h_commit, signature)`
  and `reveal_move(role, turn, state, move, intent, nonce, signature)`.
- The plaintext `make_move(role, direction)` tool is REMOVED. Leaving it
  registered would leave the front-running hole open beside its own fix.
- `get_observation` and `get_match_status` are unchanged.
- Tool parameter names are part of the P2P wire contract, because FastMCP
  derives the public input schema from the signature. Renaming one is a
  protocol change.

**Acceptance**
- [ ] `make_move` is absent from the registered tools.
- [ ] Both new tools are registered and callable.

### FR2 — Authentication

- Every submission carries an Ed25519 signature over `{role, turn, h_commit}`
  in canonical JSON form.
- A submission whose signature does not verify against that role's public key
  is rejected with `invalid_signature`, and leaves no state behind.
- A peer cannot submit as its opponent: the claimed role must match the key
  that signed it.
- Each peer holds its own public key (derived from its private signing key)
  and its opponent's, loaded from `config/<role>/peers/<peer>.pub`.

**Acceptance**
- [ ] A commitment signed with the wrong key is rejected and NOT stored.
- [ ] A peer submitting under the opponent's role is rejected.

### FR3 — Two-phase ordering

- Both peers commit before either may reveal.
- A reveal arriving before both commitments is rejected with
  `reveal_before_commit`.
- A second commitment from the same role in one turn is rejected with
  `already_committed`.

**Acceptance**
- [ ] Reveal before both commitments is refused.
- [ ] The engine advances only after both reveals.

### FR4 — Commitment integrity

- A reveal whose `(state, move, intent, nonce)` does not re-derive the
  committed digest is rejected with `broken_commitment`.
- The intent is truncated to `hint_max_words` BEFORE the digest is computed,
  so the digest covers the truncated text.

**Acceptance**
- [ ] A reveal with a substituted move is rejected.

### FR5 — Replay resistance

- `MatchState.turn_count` is authoritative; a caller-supplied turn that
  disagrees is rejected with `wrong_turn`.
- A signature valid at turn N is rejected when replayed at turn N+1.

**Acceptance**
- [ ] A captured turn-N submission fails at turn N+1.

### FR6 — Trained policy

- Each peer constructs one `AgentPolicy` and loads its own `qtable_path` at
  startup.
- A missing table or a `state_layout_version` mismatch fails LOUDLY. A peer
  that silently plays from an empty table while appearing trained is the worst
  available outcome.

**Acceptance**
- [ ] A peer refuses to start on a missing or mismatched table.
- [ ] A started peer's table is non-empty.

### FR7 — Transport

- Peers run over streamable HTTP on configured ports; no port literal appears
  in Python source.
- Both peers are torn down even when the match raises, leaving no orphaned
  listeners.

**Acceptance**
- [ ] Both peers answer `get_match_status` over HTTP.
- [ ] A failed match leaves no listener bound.

### FR8 — Mirrored local truth

- Each peer advances its own `GameEpisode` from the revealed moves.
- Each turn, the peers' states are compared; a divergence is reported, not
  silently tolerated.

**Acceptance**
- [ ] Both peers report identical positions and turn counts each turn.
- [ ] An injected divergence is DETECTED.

### FR9 — Match log

- Each peer writes its own log. A single shared log would require trusting
  whoever wrote it.
- Per turn: turn number, both commitment digests, both signatures, both
  revealed tuples, and the resolved positions.
- The log alone is sufficient to replay the match.

**Acceptance**
- [ ] A match produces two logs, one per peer.

### FR10 — Replay verifier

`Verified OK` is reported only when ALL of the following hold:

1. every commitment digest re-derives from its revealed tuple;
2. every signature re-verifies for its turn;
3. replaying the logged actions through a fresh `GameEpisode` reproduces the
   logged final state;
4. the two peers' logs agree.

**Acceptance — the verifier must be able to FAIL**
- [ ] Rejects a flipped move in the log.
- [ ] Rejects a forged signature.
- [ ] Rejects a reveal edited to break its commitment.
- [ ] Rejects two peer logs that disagree.

## Non-functional requirements

- Every Python file at or under 150 lines, tests included.
- Strict TDD: a confirmed failing test precedes every implementation change.
- No hardcoded tunables: ports, timeouts and paths come from config.
- `src/engine/` gains no import of `strategy` or `agent` (Phase 5 Step 5 guard).
- Tests never write into `data/`, and never depend on the real gitignored
  `signing_key.pem` — they generate ephemeral keys under `tmp_path`.

## Out of scope

- Interop with the opposing group's peer.
- Retraining or any change to the Q-tables.
- Any change to `config/game.json`.
- A vision radius.
