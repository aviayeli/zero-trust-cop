# TODO — Phase 3: Peer Identity & Computational Fairness

## Status

DRAFT. No box below may be started until `PRD_03_Security.md` has final Judge
approval and the `cryptography` dependency is confirmed. Strict TDD throughout: a
failing test precedes every implementation change, and the RED run is recorded in
the checklist note.

Order follows `PLAN_03`'s dependency chain. Tasks 1–3 are prerequisites with no
protocol impact. Task 7 is additionally gated on the opposing group agreeing to
the new tool schemas. Task 8 (Step-0) is independent of 1–7 and gets its own
commit — identity and fairness-declaration are unrelated concerns.

## 1. Extract the single canonical serialization

- [x] Test first: assert `crypto.canonical_json({...})` returns sorted-key,
      whitespace-free UTF-8 bytes, and that `commit`/`verify` still produce the
      Task 7 digests unchanged (regression guard on the wire format).
- [x] Run tests, confirm RED (`canonical_json` does not exist).
- [x] Implement: extract `canonical_json(payload: dict) -> bytes` as public;
      reduce `_canonical_payload` to a caller of it. No behaviour change.
- [x] Run tests, confirm GREEN and the full suite unchanged at 119.
- [x] Confirm `crypto.py` still under 150 lines.

## 2. Add the Ed25519 dependency

- [x] Add `cryptography` to `pyproject.toml` dependencies; refresh `uv.lock`.
- [x] Confirm the import works in the venv and the full suite still passes.
- [x] Record in the commit message that this is the first non-`mcp` runtime
      dependency and a deliberate deviation from the stdlib-only posture.

## 3. Git-ignore key material BEFORE any key exists

- [x] Add `*.pem` and `config/*/signing_key*` to `.gitignore`.
- [x] Add `config/police/signing_key.pem.example` and the thief equivalent,
      containing a format comment only — never real key material.
- [x] Verification: generate a throwaway keypair, run `git status`, confirm the
      private key is untracked; then delete the throwaway.
- [x] Grep the repo to confirm no private key block is tracked. Pin the audit to the
      five-dash PEM delimiter, which is what a real key file always contains:
      `grep -rn '\-\-\-\-\-BEGIN' config/ src/ tests/ docs/` (or `git grep -n -e '-----BEGIN'`,
      which excludes `.venv/` by construction). Do NOT grep the bare phrase
      `BEGIN PRIVATE KEY`: the `.pem.example` placeholders legitimately describe the
      PEM format in prose, so that form returns permanent false positives — and an
      audit with known false hits is one people learn to ignore.

## 4. `identity.py` — sign / verify

- [x] Test first, against fixed test vectors (a checked-in test keypair, NOT a
      match key):
  - [x] `sign` returns a hex signature that `verify_signature` accepts.
  - [x] Tampering with `role`, `turn`, or `h_commit` → False.
  - [x] A signature from a different key → False.
  - [x] A malformed/garbage signature → False, does NOT raise (PRD FR3).
  - [x] A signature valid for turn N → False when replayed at turn N+1 (FR5).
  - [x] The signed bytes come from `crypto.canonical_json` (one wire format).
- [x] Run tests, confirm RED (module does not exist).
- [x] Implement `src/mcp_server/identity.py`: `sign`, `verify_signature`, over
      `canonical_json({"role":…, "turn":…, "h_commit":…})`.
- [x] Run tests, confirm GREEN; full suite green.
- [x] Confirm `identity.py` under 150 lines.

## 5. Key loading with workspace separation

- [x] Test first:
  - [x] `load_signing_key("police")` resolves under `config/police/`, and the
        thief's resolves under `config/thief/` — paths differ (workspace
        separation, mirroring `peer_config_path` in `server.py`).
  - [x] A missing key raises; there is NO unauthenticated fallback (FR1).
  - [x] A malformed key file raises rather than returning None.
  - [x] Env indirection overrides the default path.
- [x] Run tests, confirm RED.
- [x] Implement `load_signing_key` / `load_peer_public_key`.
- [x] Run tests, confirm GREEN; full suite green.
- [x] Confirm still under 150 lines; split `keys.py` out of `identity.py` if the
      limit is threatened (do not let the file breach and fix later).

## 6. `commitments.py` — the two-phase state machine

Built and tested in isolation, before any `server.py` edit, so the ordering rules
are verified without FastMCP in the way.

- [x] Test first:
  - [x] A first `commit` for a turn leaves state "half"; the second reaches
        "both_committed".
  - [x] A second commitment from the SAME role in one turn is rejected and does
        not overwrite the first (mirrors `PRD_02` FR7).
  - [x] A reveal attempted before both commitments are in is **rejected** — the
        rule that actually prevents front-running.
  - [x] A reveal whose `(state, move, intent, nonce)` fails `crypto.verify`
        against the stored `h_commit` is rejected as a broken commitment.
  - [x] Both valid reveals → "resolved", exposing both action tokens exactly once.
  - [x] Turn rollover clears commitment slots; a stale commitment from turn N is
        not usable at turn N+1.
- [x] Run tests, confirm RED (module does not exist).
- [x] Implement `src/mcp_server/commitments.py`. It must NOT call
      `MatchState.submit` itself — it reports "resolved" and the caller drives
      the engine, keeping the layering that Phase 2 established.
- [x] Run tests, confirm GREEN; full suite green.
- [x] Confirm under 150 lines.

## FR4 resolution (was an open item in PLAN_03)

FR4 asked that a submission claiming the peer's OWN role "from a remote source" be
rejected. Over stdio there is no transport distinction: the peer's own client and
the opponent both reach the same tool surface, so "remote origin" is not
observable and cannot be enforced as written.

Resolved: **key possession is the authority, not transport origin.** Every
submission — including the peer's own — must carry a signature that verifies
against the claimed role's public key. Only the police peer holds the police
private key, so only it can submit as police; the thief cannot forge that role
without stealing the key. This is precisely what choosing Ed25519 over a shared
secret bought us (PRD_03 "Known Limitation This Phase Removes"), and it makes FR4
a property of the signature check rather than a separate origin test.

Consequence: the server needs the PUBLIC key of both roles. Its own comes from
`load_signing_key(own_role).public_key()` — no extra file — and the opponent's
from `load_peer_public_key(own_role, peer_role)`.

## 7a. `submissions.py` — the authenticated submission pipeline

Split out from the original Step 7 because that step could not fit one change:
`server.py` is at 119/150 and `test_server.py` at 147/150, and making
`create_app` load keys breaks all 12 of its existing `create_app()` calls at once.
7a is the logic, testable in isolation with injected collaborators and touching no
existing test. 7b is the wiring.

- [x] Test first, with an injected fake/real `MatchState`, a real `CommitmentBook`,
      and real Ed25519 keys generated in-test:
  - [x] A correctly signed commitment is accepted.
  - [x] A commitment with a tampered payload or a signature from the WRONG key is
        rejected; `MatchState` is NOT mutated, the role's slot is NOT consumed,
        and the episode does NOT advance (FR3).
  - [x] **Turn is taken from the engine, not the caller.** A submission whose
        `turn` does not equal `MatchState.turn_count` is rejected before the
        commitment book is touched. This closes Step 6's two gaps: a reveal
        mislabelled with a future turn, and a peer wiping in-progress state by
        committing at an arbitrary higher turn.
  - [x] **The signature binds the turn.** A signature valid at turn N is rejected
        at turn N+1 (FR5) — verify this through the pipeline, not only through
        `identity` unit tests, since `crypto.verify` does NOT cover turn and the
        signature is the only thing that does.
  - [x] A reveal before both commitments are in is rejected (front-running).
  - [x] A reveal that fails `crypto.verify` against the stored `h_commit` is
        rejected as a broken commitment.
  - [x] Both valid reveals drive `MatchState.submit` exactly once per role and
        advance the episode exactly one turn.
  - [x] Rejections return the `observations.build_move_error` shape (FR3).
- [x] Run tests, confirm RED.
- [x] Implement `src/mcp_server/submissions.py`. It orchestrates only:
      signature check (`identity`) → turn check against `MatchState.turn_count` →
      ordering (`commitments`) → resolution (`MatchState.submit`) → payload
      shaping (`observations`). It must not re-implement any of them.
      The peer→engine role mapping is INJECTED by the caller, not redeclared.
- [x] Run tests, confirm GREEN; full suite green.
- [x] Confirm under 150 lines.

## 7b. Wire the tool surface into `server.py` — GATED on interop agreement

- [x] BLOCKER: confirm the opposing group has agreed to the FR7 schemas. Do not
      ship a unilateral protocol change.
- [x] Refactor first, as its own reviewable change: `server.py` imports
      `PEER_ROLES` from `identity` instead of declaring its own copy. Two tuples
      that must agree is the drift shape that caused the Task 4.5 bug; if they
      diverged, `server.py` would accept a role `identity` rejects.
- [x] Test first:
  - [x] The tool surface is exactly `submit_commitment`, `reveal_move`,
        `get_observation`, `get_match_status`; `make_move` is GONE.
  - [x] Update the pinned wire-schema test to the new input schemas —
        deliberately, as an approved supersession of `PRD_02` FR2, recorded as
        such in the test docstring so it does not read as an incidental edit.
  - [x] `create_app` RAISES when the peer's signing key is missing — no
        unauthenticated fallback (FR1). This is a behaviour change: every
        existing `create_app()` test must now supply a `config_root` containing
        generated keys.
  - [x] End-to-end through the live tools: two signed commitments then two valid
        reveals advance the episode exactly one turn, exercising the Task 7
        primitive through the real surface rather than only its unit tests.
- [x] Run tests, confirm RED.
- [x] Implement. Tool bodies stay delegation-only — all logic lives in
      `submissions.py` from 7a.
- [x] Confirm `server.py` under 150 lines.
- [x] `test_server.py` is at 147/150. Adding a keys fixture and the new
      end-to-end tests WILL breach it — split it (e.g.
      `test_server_tools.py`) rather than letting it grow past the limit.

## 8. Step-0 Computational Fairness Declaration (FR6) — separate commit

- [x] Create `config/declaration.json` holding only the non-derivable declared
      fields: `group_name`, `members`, `repos.cop/thief`, `mcp_servers.cop/thief`.
      No secrets, so it is tracked.
- [x] Test first:
  - [x] The output has all nine top-level keys from the FR6 schema, with the
        exact nesting for `repos`, `mcp_servers`, and `hardware`.
  - [x] `token_budget` and `num_games` are **integers**, not strings, and equal
        `config/game.json`'s `token_budget_per_series` (200000) and `num_games` (1)
        — proving they are not re-declared in a second source of truth.
  - [x] `github_commit_hash` matches `git rev-parse HEAD`, full 40-char hex.
  - [x] Declared fields come from `config/declaration.json`, verified by pointing
        the loader at a temp config and seeing the values change.
  - [x] `hardware.ram` matches the documented `"<N> GB"` convention.
  - [x] With no GPU present, `hardware.gpu_vram` is `"none"` — the key is present,
        never omitted.
  - [x] A failed probe yields an explicit sentinel, not a missing key.
  - [x] The file is written as `declaration_<game_id>.json` and `game_id` is a
        required input — no default, no inference.
  - [x] The emitted JSON round-trips through `json.load` and validates key-for-key
        against the schema.
- [x] Run tests, confirm RED.
- [x] Implement `src/mcp_server/declaration.py`. Its docstring MUST state that the
      artifact is unsigned and unenforced — it records what a peer claims and
      cannot detect a peer running a different commit.
- [x] Run tests, confirm GREEN; full suite green.
- [x] Confirm under 150 lines; split the host-probing helpers into a separate
      module if the limit is threatened.
- [x] Verify both peers emit byte-identical content for the same `game_id`, since
      divergence is itself a fairness signal (PRD FR6).

## 9. Cross-cutting verification

- [x] Full suite green; report the exact count and confirm no test was lost.
- [x] No Python file over 150 lines (repo-wide check, `src/` and `tests/`).
- [x] No private key material tracked; `git status` clean of secrets.
- [x] Confirm `match_state.py` and `observations.py` were not modified — Phase 3
      touches identity and wiring only.
- [x] Update `TODO_02_MCP_Server.md`'s stale Task 4 checkboxes, which still show
      unchecked despite `server.py` shipping in `4013a48`.
