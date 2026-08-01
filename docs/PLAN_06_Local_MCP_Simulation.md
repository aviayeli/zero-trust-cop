# PLAN — Phase 6: Local P2P MCP Simulation

## Status

DRAFT for review. **No `PRD_06` exists.** The constitution requires
`PRD.md → PLAN.md → TODO.md` in order. Phase 5 already ran without a `PRD_05`
— `PLAN_05` said its content "should be promoted into one before
implementation" and that never happened. This plan records the same gap
rather than repeating it silently: if it is approved, promote it into
`PRD_06` before any implementation begins.

Phase 6 removes the external dependency that blocked Step 7b. Rather than
waiting for the opposing group to agree the FR7 schemas, both peers are run
locally against each other over a real transport.

## Objective

Play a complete cop-vs-thief match between two independent local MCP peers,
over a real wire, with commit-reveal and signatures actually in force, using
the Q-tables trained in Phase 5 — and produce a match log that a replay
verifier can independently confirm.

## What exists today — VERIFIED, not assumed

Each claim below was checked against the tree, because the central risk in
this phase is assuming a component is wired when it is only built.

| Component | State |
|---|---|
| `crypto.py` — commit/verify digests | Built, tested, **not reachable over the wire** |
| `commitments.py` — `CommitmentBook` | Built, tested, **not reachable over the wire** |
| `identity.py` — Ed25519 sign/verify | Built, tested, **not reachable over the wire** |
| `submissions.py` — `SubmissionGate` | Built, tested, **never imported by `server.py`** |
| `match_state.py` — buffer, lock, timeout | Wired and live |
| `agent_core.py` — `AgentPolicy` | Built, tested, **never imported by `server.py`** |
| `QValues.load()` | Implemented; **called only by tests** |
| Match log | **Does not exist** |
| Replay verifier | **Does not exist** |

### Gap 1 — the live tool surface has no security at all

`server.py` imports only `match_state` and `observations`. Its three tools
are `get_observation`, `make_move`, and `get_match_status`, and `make_move`
is:

```python
async def make_move(role: str, direction: str) -> dict:
    outcome = await match_state.submit(role, direction)
```

A **plaintext direction**, submitted straight to the engine. There is no
commitment, no reveal, no signature, and — separately — no check that the
caller is the role it claims to be. `get_observation` compares `role` against
the peer's own role; `make_move` does not. On today's surface either peer can
submit moves *as its opponent*.

This is exactly the shape `PLAN_05` warned about for `crypto.py`: verified in
isolation, believed to be protecting something, wired to nothing. Phase 6
cannot "validate commit-reveal over the wire" without first putting it there.
**That wiring is the bulk of this phase, and it is the work Step 7b deferred.**

### Gap 2 — no peer plays with a trained policy

Nothing in `src/mcp_server/` constructs an `AgentPolicy`, and nothing in
production calls `QValues.load()`. The Phase 5 tables are committed
deliverables that no running peer currently reads.

### Gap 3 — no match log and no verifier

Nothing writes a match record, nothing verifies one, and the string
`Verified OK` appears nowhere in the repository. Both the log format and the
verifier are new construction in this phase, not an existing tool to run.

## The architectural problem that must be decided first

`create_app` builds a **separate `GameEpisode` per peer**:

```python
episode = GameEpisode(config)
match_state = MatchState(episode, config.response_timeout_sec)
```

So two independent local truths exist. This is correct for a zero-trust
design — neither peer should have to trust the other's engine — but it means
the two episodes stay in agreement only if both observe the same moves, and
nothing today detects divergence.

`SubmissionGate` assumes the opposite shape: it holds public keys for **both**
roles and resolves the engine once **both** reveal, i.e. it reads like a match
host rather than one side of a P2P pair. That tension is unresolved in the
current code and must be settled before wiring.

Recommendation: **mirrored local truth**. Each peer runs the full pipeline for
both roles and advances its own episode; each turn both peers therefore
compute a state independently. Divergence is then detectable by comparing a
state digest each turn, and detecting it is a *feature* of the simulation, not
an error case to hide.

## Part A — put security on the wire

Register signed commit-reveal tools on the peer app, delegating to the
existing `SubmissionGate` (which already validates role, turn, signature,
commit-before-reveal, and direction). No new crypto is written; this is
wiring, and the tools are thin.

Two-phase ordering per turn: both peers `submit_commitment`, then both
`reveal_move`. A reveal before both commitments are in must be rejected by
the book, not by the caller's good manners.

`MatchState.turn_count` stays authoritative — a caller-supplied turn is
already rejected as `wrong_turn`, and that must survive the wiring.

## Part B — give each peer its trained policy

Construct one `AgentPolicy` per peer from that peer's private
`[strategy]` block, and load its `qtable_path` at startup. A missing or
version-mismatched table must fail loudly (`QValues.load` already raises on
`state_layout_version` mismatch) rather than silently playing from an empty
table — an untrained peer that looks trained is the worst outcome here.

Exploration must be **off** for competitive play. Training used epsilon; a
match should be greedy. This needs a decision (see D5) because
`select_action` reads the mutable `_epsilon`.

The `hint_max_words` cap is enforced by truncation in `AgentPolicy` before
the intent is committed, so the digest covers the truncated text. `PLAN_05`
open item 4 asked whether the cap is also a protocol rule enforced at the
tool surface; Phase 6 is where that is answered.

## Part C — two peers, one match, over a real transport

`FastMCP.run` accepts `stdio`, `sse`, or `streamable-http`; both a stdio
client and a streamable-http client are available in the installed `mcp`
package. The request asks for "one port/channel" per peer, which points at
`streamable-http` on two localhost ports. Ports are tunables and must come
from config, never literals in Python.

`run_local_mcp_match.py` starts both peers, drives a full match to
termination, and shuts them down cleanly — including on failure, so a crashed
match never leaves orphaned listeners.

This is where the properties training could not exercise finally get tested:
commit-reveal ordering, signature rejection, and the response timeout.

## Part D — match log and replay verifier

**Log.** Each peer writes its OWN log (zero-trust: a shared log would require
trusting whoever wrote it). Per turn: turn number, each role's commitment
digest, signature, revealed `(state, move, intent, nonce)`, and the resolved
positions.

**Verifier.** `Verified OK` must mean something specific and checkable:

1. every commitment digest re-derives from its revealed `(state, move,
   intent, nonce)` via `crypto.verify`;
2. every signature re-verifies against the peer's public key for that turn;
3. replaying the logged action sequence through a fresh `GameEpisode`
   reproduces the logged final state exactly (`GameEpisode.replay` already
   guarantees FR7 determinism);
4. the two peers' independent logs agree.

A verifier that only checks (3) would pass a match with forged signatures. A
verifier that cannot FAIL is worthless — it must be proven to reject a
tampered log, per the standard this project now holds guards to.

## Decisions needed before implementation

- **D1 — Transport.** `streamable-http` on two configured localhost ports
  (matches the request, real TCP), or stdio subprocesses (simpler, no ports,
  still real serialisation)? Recommendation: streamable-http.
- **D2 — Match topology.** Mirrored local truth (recommended) or one peer
  hosting the authoritative match?
- **D3 — Does `make_move` survive?** It is unauthenticated and bypasses
  commit-reveal entirely. Leaving it registered leaves the front-running hole
  open next to the fix. Recommendation: remove it, or gate it behind config.
- **D4 — Log location and tracking.** `data/` alongside the Q-tables, or a
  new `logs/` directory? Tracked as deliverables or ignored?
- **D5 — Exploration during a match.** Force epsilon to zero for competitive
  play, or play with the trained residual epsilon (~0.0135 after 2000 games)?
- **D6 — Barriers.** Phase 5's tables never saw an interior barrier because
  `GameEpisode.reset()` places none. If the simulation places barriers, the
  peers play a board their tables were not trained on. Recommendation: keep
  the board barrier-free for Phase 6 so the simulation tests the PROTOCOL,
  and treat barrier training as its own phase.

## Out of scope for Phase 6

- Interoperating with the opposing group's peer. This phase removes the
  *blocker*, not the eventual need: passing locally proves our two peers
  agree with each other, not that we match anyone else's schema reading.
- Retraining, reward shaping, or any change to the Q-tables.
- Any change to `config/game.json`, which remains the Step-0 contract.
- A vision radius (still D2 from `PLAN_05`).

## Approval gate

No implementation until this is promoted into `PRD_06` and D1–D6 are decided.
Part A is the prerequisite for Parts C and D: until commit-reveal and
signatures are actually on the wire, a "simulation" would be validating a
protocol the peers are not speaking.
