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

- [ ] Test first: assert `crypto.canonical_json({...})` returns sorted-key,
      whitespace-free UTF-8 bytes, and that `commit`/`verify` still produce the
      Task 7 digests unchanged (regression guard on the wire format).
- [ ] Run tests, confirm RED (`canonical_json` does not exist).
- [ ] Implement: extract `canonical_json(payload: dict) -> bytes` as public;
      reduce `_canonical_payload` to a caller of it. No behaviour change.
- [ ] Run tests, confirm GREEN and the full suite unchanged at 119.
- [ ] Confirm `crypto.py` still under 150 lines.

## 2. Add the Ed25519 dependency

- [ ] Add `cryptography` to `pyproject.toml` dependencies; refresh `uv.lock`.
- [ ] Confirm the import works in the venv and the full suite still passes.
- [ ] Record in the commit message that this is the first non-`mcp` runtime
      dependency and a deliberate deviation from the stdlib-only posture.

## 3. Git-ignore key material BEFORE any key exists

- [ ] Add `*.pem` and `config/*/signing_key*` to `.gitignore`.
- [ ] Add `config/police/signing_key.pem.example` and the thief equivalent,
      containing a format comment only — never real key material.
- [ ] Verification: generate a throwaway keypair, run `git status`, confirm the
      private key is untracked; then delete the throwaway.
- [ ] Grep the repo to confirm no private key block is tracked. Pin the audit to the
      five-dash PEM delimiter, which is what a real key file always contains:
      `grep -rn '\-\-\-\-\-BEGIN' config/ src/ tests/ docs/` (or `git grep -n -e '-----BEGIN'`,
      which excludes `.venv/` by construction). Do NOT grep the bare phrase
      `BEGIN PRIVATE KEY`: the `.pem.example` placeholders legitimately describe the
      PEM format in prose, so that form returns permanent false positives — and an
      audit with known false hits is one people learn to ignore.

## 4. `identity.py` — sign / verify

- [ ] Test first, against fixed test vectors (a checked-in test keypair, NOT a
      match key):
  - [ ] `sign` returns a hex signature that `verify_signature` accepts.
  - [ ] Tampering with `role`, `turn`, or `h_commit` → False.
  - [ ] A signature from a different key → False.
  - [ ] A malformed/garbage signature → False, does NOT raise (PRD FR3).
  - [ ] A signature valid for turn N → False when replayed at turn N+1 (FR5).
  - [ ] The signed bytes come from `crypto.canonical_json` (one wire format).
- [ ] Run tests, confirm RED (module does not exist).
- [ ] Implement `src/mcp_server/identity.py`: `sign`, `verify_signature`, over
      `canonical_json({"role":…, "turn":…, "h_commit":…})`.
- [ ] Run tests, confirm GREEN; full suite green.
- [ ] Confirm `identity.py` under 150 lines.

## 5. Key loading with workspace separation

- [ ] Test first:
  - [ ] `load_signing_key("police")` resolves under `config/police/`, and the
        thief's resolves under `config/thief/` — paths differ (workspace
        separation, mirroring `peer_config_path` in `server.py`).
  - [ ] A missing key raises; there is NO unauthenticated fallback (FR1).
  - [ ] A malformed key file raises rather than returning None.
  - [ ] Env indirection overrides the default path.
- [ ] Run tests, confirm RED.
- [ ] Implement `load_signing_key` / `load_peer_public_key`.
- [ ] Run tests, confirm GREEN; full suite green.
- [ ] Confirm still under 150 lines; split `keys.py` out of `identity.py` if the
      limit is threatened (do not let the file breach and fix later).

## 6. `commitments.py` — the two-phase state machine

Built and tested in isolation, before any `server.py` edit, so the ordering rules
are verified without FastMCP in the way.

- [ ] Test first:
  - [ ] A first `commit` for a turn leaves state "half"; the second reaches
        "both_committed".
  - [ ] A second commitment from the SAME role in one turn is rejected and does
        not overwrite the first (mirrors `PRD_02` FR7).
  - [ ] A reveal attempted before both commitments are in is **rejected** — the
        rule that actually prevents front-running.
  - [ ] A reveal whose `(state, move, intent, nonce)` fails `crypto.verify`
        against the stored `h_commit` is rejected as a broken commitment.
  - [ ] Both valid reveals → "resolved", exposing both action tokens exactly once.
  - [ ] Turn rollover clears commitment slots; a stale commitment from turn N is
        not usable at turn N+1.
- [ ] Run tests, confirm RED (module does not exist).
- [ ] Implement `src/mcp_server/commitments.py`. It must NOT call
      `MatchState.submit` itself — it reports "resolved" and the caller drives
      the engine, keeping the layering that Phase 2 established.
- [ ] Run tests, confirm GREEN; full suite green.
- [ ] Confirm under 150 lines.

## 7. Wire the two signed tools into `server.py` — GATED on interop agreement

- [ ] BLOCKER: confirm the opposing group has agreed to the FR7 schemas. Do not
      ship a unilateral protocol change.
- [ ] Test first:
  - [ ] The tool surface is exactly `submit_commitment`, `reveal_move`,
        `get_observation`, `get_match_status`; `make_move` is GONE.
  - [ ] Update the pinned wire-schema test to the new input schemas —
        deliberately, as an approved supersession of `PRD_02` FR2, recorded as
        such in the test docstring so it does not read as an incidental edit.
  - [ ] A correctly signed commitment is accepted; a tampered or mis-signed one
        is rejected, `MatchState` is NOT mutated, the role's slot is NOT
        consumed, and the episode does NOT advance (FR3).
  - [ ] A submission claiming the peer's OWN role from a remote origin is
        rejected (FR4).
  - [ ] A signature valid at turn N replayed at turn N+1 is rejected (FR5).
  - [ ] End-to-end: two signed commitments then two valid reveals advance the
        episode exactly one turn, and the Task 7 primitive is exercised through
        the live tool surface rather than only its unit tests.
- [ ] Run tests, confirm RED.
- [ ] Implement. Tool bodies stay delegation-only: signature checks live in
      `identity.py`, ordering in `commitments.py`, resolution in `MatchState`.
- [ ] Run tests, confirm GREEN; full suite green.
- [ ] Confirm `server.py` under 150 lines — at 119 this is tight. Extract a
      helper module rather than breaching the limit.

## 8. Step-0 Computational Fairness Declaration (FR6) — separate commit

- [ ] Create `config/declaration.json` holding only the non-derivable declared
      fields: `group_name`, `members`, `repos.cop/thief`, `mcp_servers.cop/thief`.
      No secrets, so it is tracked.
- [ ] Test first:
  - [ ] The output has all nine top-level keys from the FR6 schema, with the
        exact nesting for `repos`, `mcp_servers`, and `hardware`.
  - [ ] `token_budget` and `num_games` are **integers**, not strings, and equal
        `config/game.json`'s `token_budget_per_series` (200000) and `num_games` (1)
        — proving they are not re-declared in a second source of truth.
  - [ ] `github_commit_hash` matches `git rev-parse HEAD`, full 40-char hex.
  - [ ] Declared fields come from `config/declaration.json`, verified by pointing
        the loader at a temp config and seeing the values change.
  - [ ] `hardware.ram` matches the documented `"<N> GB"` convention.
  - [ ] With no GPU present, `hardware.gpu_vram` is `"none"` — the key is present,
        never omitted.
  - [ ] A failed probe yields an explicit sentinel, not a missing key.
  - [ ] The file is written as `declaration_<game_id>.json` and `game_id` is a
        required input — no default, no inference.
  - [ ] The emitted JSON round-trips through `json.load` and validates key-for-key
        against the schema.
- [ ] Run tests, confirm RED.
- [ ] Implement `src/mcp_server/declaration.py`. Its docstring MUST state that the
      artifact is unsigned and unenforced — it records what a peer claims and
      cannot detect a peer running a different commit.
- [ ] Run tests, confirm GREEN; full suite green.
- [ ] Confirm under 150 lines; split the host-probing helpers into a separate
      module if the limit is threatened.
- [ ] Verify both peers emit byte-identical content for the same `game_id`, since
      divergence is itself a fairness signal (PRD FR6).

## 9. Cross-cutting verification

- [ ] Full suite green; report the exact count and confirm no test was lost.
- [ ] No Python file over 150 lines (repo-wide check, `src/` and `tests/`).
- [ ] No private key material tracked; `git status` clean of secrets.
- [ ] Confirm `match_state.py` and `observations.py` were not modified — Phase 3
      touches identity and wiring only.
- [ ] Update `TODO_02_MCP_Server.md`'s stale Task 4 checkboxes, which still show
      unchecked despite `server.py` shipping in `4013a48`.
