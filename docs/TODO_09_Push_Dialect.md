# TODO 09 — The push dialect

Derived from `PRD_09_Push_Dialect.md`. Strict TDD: a failing test first, every
step. Items are checked only once the test that proves them passes.

## 9.1 Inbound validation

- [x] **Test first**: `tests/mcp_server/test_push_messages.py` — one case per
      field per message, plus the two seam cases the reference-v3 work already
      established: an unknown key is TOLERATED, a missing required key is
      REFUSED rather than defaulted.
- [x] `src/mcp_server/push_messages.py` — pure validators for the six inbound
      shapes. Refusal strings name the field, never a bare "invalid".
- [x] `role` is validated against the contract vocabulary, not ours: they say
      `police` / `thief` on the wire.

## 9.2 The inbound tools

- [x] **Test first**: `tests/mcp_server/secure/test_push_surface.py` — the six
      tools appear ONLY with the dialect enabled, and a refusal changes no
      state.
- [x] `src/mcp_server/push_tools.py` — register the six, backed by a per-turn
      store that keeps their commits, reveals and (at the end) their nonces.
- [x] `receive_ack` and `receive_capture_claim` touch no engine state.

## 9.3 The gate (FR5) — the item that must not be skipped

- [x] **Test first**: with no flag, `tools/list` is byte-identical to today's
      eight names; with `--dialect push`, and only then, the six appear.
- [x] `--dialect push` on the server CLI, defaulting OFF.
- [x] The refusal path is documented in the module docstring: this surface
      accepts UNAUTHENTICATED submissions, which is exactly what our own
      dialect exists to prevent.

## 9.4 Outbound client + match loop

- [x] **Test first**: against a fake peer, assert the exact argument sets —
      `receive_commit` WITHOUT `signature`, `receive_reveal` WITHOUT `nonce`
      and `state`.
- [x] `src/mcp_server/push_client.py` — the outbound half.
- [x] `src/scripts/push_match_loop.py` — drive a sub-game: commit, reveal,
      ack, capture claim, then final audit.
- [x] **Test first**: every dropped nonce is buffered and ALL of them reach
      `receive_final_audit`. A nonce that is dropped and not buffered destroys
      our own evidence, so this is asserted by count, not by spot check.

## 9.5 The audit, honestly (FR4)

- [x] **Test first**: given nonces we cannot rebuild a preimage for, the audit
      reports `unverifiable` — NOT `accepted`. This is the test that stops us
      shipping a green light we never computed.
- [x] Re-hash whatever is reconstructable with `interop.commit`.
- [ ] **BLOCKED — needs ali-ahm1**: what do the `nonces` entries carry, and
      what payload does their `h_commit` seal? Without the payload schema the
      deferred audit cannot be computed at all. Asked 2026-08-24; until it is
      answered this dialect provides no verification, only play.

## 9.5b Found while building — fixed

- [x] The match loop first derived its nonce from `id(payload)`, a memory
      address. The nonce is the ONLY thing hiding our move over a five-element
      move set, so a derivable one lets the opponent brute-force the
      commitment before we reveal. Now `secrets.token_hex(16)`, matching
      `mcp_server.crypto`, and pinned by a test asserting unpredictability and
      no repeats across sub-games.
- [x] Our own audit entries carry `{step, nonce, payload}`, not bare nonces —
      we send what we are asking ali-ahm1 for, so our chain stays auditable
      even if theirs is not.
- [x] `server.py` split: `mcp_server/cli.py` (entry point) and
      `mcp_server/dialects.py` (which surfaces exist and which are opt-in).
      The documented `python -m mcp_server.server --role police` still works.

## 9.6 Open questions already answered

- [x] `step` is a per-sender counter, 35 moves EACH — confirmed by ali-ahm1.
- [x] Roles alternate per sub-game; SG1 aviayeli=police, ali-ahm1=thief.
- [x] Their peer serves both roles on ONE endpoint, role passed per call.
      Ours are two peers on two ports; role is the endpoint.
