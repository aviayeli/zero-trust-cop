# PLAN — Phase 3: Peer Identity & Computational Fairness

## Status

DRAFT, awaiting final Judge approval. Two blockers from the first draft are now
resolved: the tool surface is Option (a) (Conductor + Judge authorized the
supersession of `PRD_02` FR2), and Chapter 5.5 has been supplied, so FR6 is
planned rather than blocked.

## Design Principles Applied

- **Simplicity first**: one signing primitive, one canonical serialization, no
  key-management framework. Public keys are exchanged out of band.
- **Surgical changes**: `crypto.py` gains one extracted helper; `match_state.py`
  and `observations.py` are not touched.
- **Goal-driven**: every step below traces to an FR in `PRD_03_Security.md`.

## Precondition Discovered During Planning

`src/mcp_server/crypto.py` (Task 7) is **imported by nothing except its own
test**. `server.py`'s `make_move` still accepts a plaintext `direction` and
passes it straight to `MatchState.submit`. Therefore:

- Commit-reveal exists as a verified *primitive* but is not in the live protocol.
  Front-running is not yet prevented in the running server.
- Phase 3 must wire commit-reveal into the tool surface before, or together with,
  adding signatures. Signing a plaintext-direction submission would authenticate
  a message that still leaks the move.

This reordering is the main planning consequence and should be reviewed.

## Threat Model (explicit)

| Threat | Addressed by | Status after Phase 3 |
|---|---|---|
| Peer adapts its move after seeing the opponent's | commit-reveal, wired into tools | Closed |
| Outsider posts a move to the inbox | Ed25519 signature check | Closed |
| Peer forges a submission as its opponent | Ed25519 (asymmetric) | Closed |
| Signature replayed on a later turn | turn binding in signed payload | Closed |
| Eavesdropper reads moves in transit | nothing — stdio, unencrypted | **Open, out of scope** |
| Peer lies about its own local state | nothing — each peer owns its truth | **Open by design** |
| Peer runs different code than declared | Step-0 declaration (FR6) | **Declared, not enforced** |

## Canonical Serialization (single source)

`crypto.py` currently keeps `_canonical_payload` private and shaped to the
commit-reveal fields. Phase 3 extracts:

```
canonical_json(payload: dict) -> bytes    # sort_keys=True, separators=(",",":")
```

`_canonical_payload` becomes a thin caller of it, and `identity.py` uses the same
function. Two serializations of one logical payload is the exact drift class that
produced the Task 4.5 bug — one function, one wire format, enforced by test.

## Module Architecture

```
src/mcp_server/
  crypto.py       (existing) + canonical_json() extracted, public
  identity.py     (new)      keypair load, sign(), verify_signature()
  commitments.py  (new)      per-turn commitment buffer for the two-phase flow
  declaration.py  (new)      Step-0 artifact: probe host, read config, write JSON
  server.py       (edit)     retire make_move; add the two signed tools
```

`server.py` is at 119 of 150 lines, so the two-phase flow cannot be implemented
inline in the tool bodies. `commitments.py` exists to keep the wrappers thin: it
holds the commitment slots and the "both committed?" predicate, mirroring how
`match_state.py` owns the action buffer. The tool bodies stay delegation-only.

`identity.py` responsibilities, and nothing more:

- `load_signing_key(role, config_root=None)` — read the peer's own Ed25519
  private key. Path from env indirection, defaulting under `config/<role>/`.
  Missing/malformed key raises; never falls back to unauthenticated mode (FR1).
- `load_peer_public_key(role, config_root=None)` — the opponent's public key.
- `sign(signing_key, role, turn, h_commit) -> str` — signature over
  `canonical_json({"role":…, "turn":…, "h_commit":…})`, hex-encoded.
- `verify_signature(public_key, role, turn, h_commit, signature) -> bool` —
  returns False on any malformed input rather than raising (FR3).

Binding `turn` into the signed payload gives FR5 replay resistance for free.

## Key Storage & Workspace Separation

```
config/police/signing_key.pem      # private — GIT-IGNORED, never committed
config/police/peers/thief.pub      # opponent public key — committed is fine
config/thief/signing_key.pem       # private — GIT-IGNORED
config/thief/peers/police.pub
```

`.gitignore` must gain `*.pem` and `config/*/signing_key*` before any key is
generated, so a private key cannot be committed even accidentally. A
`*.pem.example` placeholder documents the format without carrying key material.

## Tool Surface — Option (a), APPROVED

`PRD_02` FR2's three-tool surface is superseded (PRD_03 FR7). `make_move` retires;
four tools remain. Both new tools are signature-gated.

```
submit_commitment(role, turn, h_commit, signature) -> dict
reveal_move(role, turn, move, intent, nonce, signature) -> dict
get_observation(role) -> dict          # unchanged
get_match_status() -> dict             # unchanged
```

Per-turn state machine, owned by `commitments.py`:

```
empty ──submit_commitment(A)──> half ──submit_commitment(B)──> both_committed
both_committed ──reveal_move(A)──> half_revealed ──reveal_move(B)──> resolved
                                                                      │
                                    MatchState.submit(cop, thief) ◄────┘
```

Ordering rules, each an explicit rejection case:

- `reveal_move` before both commitments are in → rejected. This is the rule that
  actually prevents front-running; without it the two-phase split is decorative.
- `submit_commitment` twice for one role in one turn → rejected, mirroring
  `PRD_02` FR7's reject-on-double-submit rather than overwriting.
- A reveal whose `(state, move, intent, nonce)` does not reproduce the stored
  `h_commit` under `crypto.verify` → rejected as a broken commitment.
- Only once both reveals validate does `MatchState.submit` run for both roles, so
  `match_state.py` and `observations.py` need no changes at all.

**Interop**: these schemas are the contract with the opposing group. Approved on
our side; their agreement is still an open item below.

## Step-0 Declaration Design (FR6)

`declaration.py` composes three sources and writes one file. Nothing is a literal.

- **Declared** (`group_name`, `members`, `repos`, `mcp_servers`): not derivable
  from the machine, so they come from a new tracked config file — proposed
  `config/declaration.json`, group-level rather than under `config/<role>/`,
  because the artifact names both peers.
- **Config-derived**: `token_budget` ← `network_and_league.token_budget_per_series`
  (200000), `num_games` ← `network_and_league.num_games` (1). Both already exist in
  `config/game.json`; re-declaring them would create two sources of truth.
- **Probed**: `hardware.*`, `timezone`, `github_commit_hash`.

Probe strategy and the format conventions 5.5 leaves as bare strings — recorded
here so the two peers agree, since divergent formatting would look like a
fairness discrepancy:

| Field | Method | Convention |
|---|---|---|
| `hardware.os` | `platform.platform()` | as returned |
| `hardware.cpu` | `platform.processor()`, falling back to `/proc/cpuinfo` `model name` | as returned; `platform.processor()` is often empty on Linux, hence the fallback |
| `hardware.ram` | `os.sysconf` `SC_PAGE_SIZE` × `SC_PHYS_PAGES` | `"<N> GB"`, integer GiB, rounded down |
| `hardware.gpu_vram` | `nvidia-smi --query-gpu=memory.total`; absent/failing → `"none"` | `"<N> GB"` or `"none"` |
| `timezone` | `datetime.now().astimezone().tzname()` | IANA-style name where available |
| `github_commit_hash` | `git rev-parse HEAD` via `subprocess` | full 40-char hex |

Failure posture: a probe that cannot answer records an explicit sentinel
(`"unknown"` / `"none"`) rather than omitting the key. All nine top-level keys must
be present so the artifact validates against 5.5 unconditionally.

`game_id` is not in the schema but is in the filename, so it is a required
explicit input (CLI argument alongside `--role`), never inferred or defaulted.

The written artifact is unsigned. `declaration.py`'s docstring must say so: it
records what a peer claims, and cannot detect a peer running a different commit.

## Dependency Addition

Ed25519 requires `cryptography` in `pyproject.toml`. First non-`mcp` runtime
dependency in the project. Approved in principle by the Conductor's Task 8
directive; to be recorded as a deliberate deviation from stdlib-only.

## Ordering / Dependency Chain

1. Extract `canonical_json` in `crypto.py` (test first; no behaviour change).
2. Add `cryptography` dependency.
3. `.gitignore` key patterns — **before** any keypair exists.
4. `identity.py` sign/verify against fixed test vectors.
5. Key loading with workspace separation.
6. `commitments.py` — the per-turn two-phase state machine, in isolation.
7. Wire the two signed tools into `server.py`; retire `make_move`; update the
   pinned wire-schema test to the newly approved schema.
8. `declaration.py` — Step-0 artifact (FR6). Independent of 1–7; can proceed in
   parallel since it touches no protocol code.

Steps 1–7 are one dependency chain. Step 8 is separable and should be its own
commit: identity/protocol and fairness-declaration are unrelated concerns, and
bundling them would make either hard to revert.

## Open Items for TODO_03

- ~~Tool surface option~~ — resolved: (a), approved.
- ~~Chapter 5.5 schema~~ — resolved: supplied, planned above.
- Does the peer's own local submission also require a signature (PRD FR4), or is
  the local path trusted by construction? Affects `server.py` control flow.
- Is `turn` sufficient replay binding, or should the prior state hash be bound
  too? Affects the signed payload shape and therefore interop. Note `crypto.commit`
  already binds `state`, so binding it in the signature too may be redundant.
- **Has the opposing group agreed to the FR7 schema change?** Still open, and it
  gates step 7 — shipping a unilateral protocol change breaks the match.
- Is `config/declaration.json` the right home for the declared fields, and should
  it be tracked (it names repos and members — no secrets, so tracking looks fine)?

## Approval Gate

No implementation until PRD_03 has final Judge approval and the `cryptography`
dependency is confirmed. Step 7 additionally gated on the opposing group's
agreement to the new tool schemas.
