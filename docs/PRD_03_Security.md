# PRD 03 — Peer Identity & Computational Fairness (Phase 3)

## Status

DRAFT — awaiting final Judge approval. Two prior blockers are resolved: Chapter
5.5 supplied (FR6), and the tool-surface change authorized (FR7, superseding
`PRD_02` FR2). `PLAN_03_Security.md` and `TODO_03_Security.md` are written from
this document. No implementation may begin until the Judge approves all three.

## Objective

Close the unauthenticated `make_move` inbox identified during Phase 2, so a peer
accepts opponent submissions only from the cryptographically verified opponent,
and record a per-match Step-0 declaration that fixes each peer's code revision
and hardware for after-the-fact fairness audit.

## Scope

In scope:

- Ed25519 keypair identity per peer, with strict workspace separation (a peer's
  private key never leaves its own `config/<role>/` directory).
- Signature generation and verification over the commit-reveal payload already
  defined in `src/mcp_server/crypto.py` (Task 7, commit `f8a5b9a`).
- Wiring commit-reveal into the live protocol via a two-phase tool surface
  (FR7), which supersedes `PRD_02` FR2. Task 7 shipped the primitive but nothing
  imports it, so front-running is not yet prevented in the running server.
- Enforcement of signature checks on every submission tool.
- A Step-0 `declaration_<game_id>.json` artifact written at match start (FR6).

Out of scope (explicitly deferred):

- Transport encryption. Signatures prove authorship, not confidentiality; the
  MCP transport remains stdio and unencrypted.
- Key distribution/PKI. Public keys are exchanged out of band before a match;
  this PRD does not define a discovery or revocation protocol.
- Reputation, scoring, or league-table effects of a failed verification beyond
  rejecting the submission.

## Source of Truth

- Commit-reveal payload and canonical JSON form: `src/mcp_server/crypto.py`.
- Peer roles, config separation: `PLAN_02_MCP_Server.md`, `PRD_02_MCP_Server.md`
  FR1, FR3–FR5. **`PRD_02` FR2 (fixed three-tool surface) is superseded by FR7
  below**, on explicit Conductor + Judge authorization.
- Step-0 declaration schema: Chapter 5.5 "Step-0 and Computational Fairness" of
  the course constitution (`police_thief_p2p.pdf`), supplied by the Conductor and
  reproduced verbatim in FR6. The schema in FR6 is authoritative; if it disagrees
  with the PDF, the PDF wins and FR6 must be corrected.

## Functional Requirements

### FR1 — Peer Keypair Identity

- Each peer owns one Ed25519 keypair. The private key is read from the peer's own
  `config/<role>/` directory (or a path/env indirection to it) and is never read
  from, written to, or logged by the opposing peer's workspace.
- Private key material must never be committed. The repository must contain only
  public keys and/or `.example` placeholders.
- A missing or malformed key is a startup error, not a silent fallback to
  unauthenticated operation.

### FR2 — Submission Signing

- A peer signs the canonical byte payload binding, at minimum, its `role`, the
  turn it is acting on, and the `h_commit` it is submitting.
- The signed payload must reuse the single canonical JSON serialization already
  used by commit-reveal. Two serializations of the same logical payload is a
  defect: it is the drift class that caused the Task 4.5 bug.

### FR3 — Signature Verification on Submission Tools

- `submit_commitment` and `reveal_move` (FR7) each reject any submission whose
  signature does not verify against the claimed role's known public key.
- A rejected submission must not mutate `MatchState`, must not consume the role's
  slot for the turn, and must not advance the episode.
- Rejection returns a structured error payload consistent with the existing
  `observations.build_move_error` shape.

### FR4 — Own-Role vs Opponent-Role Origin

- A peer must not accept a submission claiming its OWN role from a remote source.
  Only the local peer may act as itself.
- Requirement to be settled in PLAN_03: whether this is enforced by a separate
  local-only path, or by requiring every submission (including the peer's own) to
  carry a valid signature under a distinct key.

### FR5 — Replay Resistance

- A signature valid for one turn must not be replayable on a later turn. Binding
  the turn number (and/or prior state hash) into the signed payload is required.

### FR6 — Step-0 Computational Fairness Declaration

At match start a `declaration_<game_id>.json` artifact is written, locking the
group's identity, both repos, both MCP endpoints, the hardware profile, and the
exact code revision. Schema per Chapter 5.5, exactly:

```json
{
  "group_name": "string",
  "members": ["string"],
  "repos":       { "cop": "string URL", "thief": "string URL" },
  "mcp_servers": { "cop": "string URL", "thief": "string URL" },
  "hardware": {
    "os": "string", "cpu": "string", "ram": "string", "gpu_vram": "string"
  },
  "github_commit_hash": "string (output of `git rev-parse HEAD`)",
  "timezone": "string",
  "token_budget": "integer",
  "num_games": "integer"
}
```

Field provenance — no value in this file may be a literal in Python source:

| Field | Source |
|---|---|
| `group_name`, `members`, `repos`, `mcp_servers` | declared config (not machine-derivable) |
| `hardware.os`, `cpu`, `ram`, `gpu_vram` | probed from the host at write time |
| `github_commit_hash` | `git rev-parse HEAD` |
| `timezone` | probed from the host |
| `token_budget` | `config/game.json` → `network_and_league.token_budget_per_series` |
| `num_games` | `config/game.json` → `network_and_league.num_games` |

Additional requirements:

- The artifact is **group-level, not peer-level**: one file names both the cop and
  thief repos and endpoints. It therefore sits outside the per-peer workspace
  separation of FR1, and both peers must emit byte-identical content for a given
  `game_id`. Divergence between the two peers' declarations is itself a
  fairness signal and must be detectable.
- The declaration is **unsigned and unenforced**. It is an honesty artifact: it
  records what a peer *claims* to be running. It cannot detect a peer running code
  other than the declared commit. Any actual enforcement is out of scope, and this
  limitation must be stated in the module docstring so the file is never mistaken
  for a proof of fairness.
- Ambiguities in 5.5 to be resolved in `PLAN_03` and recorded there, since the
  chapter types these as bare strings: the unit/format convention for `ram` and
  `gpu_vram`, the form of `timezone`, and the behaviour when no GPU is present.
- `game_id` is not part of the schema but appears in the filename, so it must be
  supplied explicitly at match start rather than inferred.

### FR7 — Two-Phase Tool Surface (supersedes `PRD_02` FR2)

`PRD_02` FR2 fixed the tool surface at exactly three tools. That constraint was a
Phase 2 scoping decision, not a protocol invariant, and it cannot express
"commit before either side reveals" — so it is superseded here on explicit
Conductor + Judge authorization.

- `make_move` is retired. It accepted a plaintext `direction`, which leaks the
  move to the receiving peer before the opponent has committed.
- `submit_commitment(role, turn, h_commit, signature)` — phase one. Buffers a
  commitment only; reveals nothing about the move.
- `reveal_move(role, turn, move, intent, nonce, signature)` — phase two. Accepted
  only after both roles' commitments are in for that turn. The revealed values
  must reproduce the stored `h_commit` via `crypto.verify`, or the submission is
  rejected as a broken commitment.
- `get_observation` and `get_match_status` are unchanged.
- This is a **breaking interop change**. The tool input schemas are the contract
  with the opposing group, and `test_server.py` pins them deliberately. The
  opposing group must agree to the new schema before either side ships it.

## Non-Functional Requirements

- Every Python file stays at or under 150 lines (project constitution).
- Strict TDD: a failing test precedes every implementation change.
- No hardcoded tunables or secrets in Python source. Key paths and any security
  parameters come from config or environment.
- Adding Ed25519 requires a new dependency (`cryptography`, providing
  `Ed25519PrivateKey`). This is an approved deviation from the stdlib-only
  posture held through Task 7 and must be recorded in `pyproject.toml`.

## Acceptance Criteria

- [ ] A submission signed by the correct peer key verifies and is buffered.
- [ ] A submission with a tampered payload, a tampered signature, or a signature
      from the wrong key is rejected and mutates nothing.
- [ ] A signature captured on turn N is rejected when replayed on turn N+1.
- [ ] A submission claiming the peer's own role from a remote origin is rejected.
- [ ] No private key material appears anywhere in tracked files.
- [ ] `reveal_move` is rejected when the revealed values do not reproduce the
      stored `h_commit`, and when it arrives before both commitments are in.
- [ ] A revealed move cannot be changed after commitment — the Task 7 primitive
      is exercised through the live tool surface, not just its unit tests.
- [ ] `declaration_<game_id>.json` validates against the FR6 schema exactly:
      all nine top-level keys present, correct nesting, `token_budget` and
      `num_games` as integers rather than strings.
- [ ] `github_commit_hash` equals `git rev-parse HEAD` at write time.
- [ ] No FR6 value is a literal in Python source; declared fields come from
      config and probed fields from the host.
- [ ] Full suite green; no Python file exceeds 150 lines.

## Known Limitation This Phase Removes

Phase 2 shipped an inbox any caller could post to as either role. A pre-shared
symmetric secret would only partly fix this: both peers holding one key means
either can forge the other, so it authenticates match membership, not peer
identity. Ed25519 is chosen specifically so a peer cannot forge its opponent.

## Next Steps (Document Lifecycle)

1. ~~Supply Chapter 5.5~~ — supplied; FR6 written from it.
2. ~~Decide the tool surface~~ — Option (a) approved; FR7 supersedes `PRD_02` FR2.
3. Final Judge approval of this PRD and the accompanying PLAN/TODO.
4. Confirm the opposing group has agreed to the FR7 schema change.
5. Only then implement, strict TDD.
