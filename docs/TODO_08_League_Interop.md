# TODO 08 — League interop conformance

Derived from `PRD_08_League_Interop.md`. Every item was implemented test-first.

## 8.1 Shared constructions — complete

- [x] **Test first**: `tests/mcp_server/test_interop_vectors.py`, bound to the
      kit's CORE fixtures vendored at `tests/fixtures/interop/` — canonical
      form, commit, terms signature, both match ids, consensus signature.
      Fixtures are data; nothing imports or executes the kit.
- [x] **Implement** `src/mcp_server/interop.py` (129 lines): both canonical
      forms, `commit`, `terms_signature`, `game_id`, `game_uid`,
      `report_consensus_signature`, `sign_report`.
- [x] Pin the two SUPERSEDED commit forms as explicitly-not-ours, so a
      regression cannot pass silently.

## 8.2 The commit cutover — complete

- [x] **Test first**: `tests/mcp_server/test_crypto_reference_form.py`.
- [x] `canonical_json` gains `ensure_ascii=False`.
- [x] `commit` emits `canonical({state, move, intent}) | nonce`.
- [x] Positional 5.3 concatenation demoted to a gated legacy verify builder,
      alongside the older nonce-sealed form. `tests/unit/test_positional_digest.py`
      repurposed to prove both stay verifiable and neither is emitted.
- [x] §10.2 closed: the canonical form delimits fields that concatenation ran
      together, and the test asserts the old collision directly.

## 8.3 Derived match ids — complete

- [x] **Test first**: `tests/mcp_server/test_terms_extraction.py`,
      `tests/unit/test_game_uid.py`.
- [x] `src/mcp_server/terms.py`: the flat 14-key terms extraction, plus
      `opponent_of` reading the contract's `agreed_between` pair — so the
      opponent id comes from the agreed contract, not a command-line label.
- [x] `config/game.json` gains `pheromone_min_center_intensity`, an agreed term
      that was absent. Loud `KeyError` rather than a default: a silently
      defaulted term hashes to a uid the opponent cannot reach.
- [x] `match_log.derive_ids`; artifacts now named after the sorted pair.
- [x] Regression pinned: a uid from the whole config, not the extracted terms,
      is self-consistent across our own four files and fails only the
      cross-team join.
- [x] `match_log.py` split at the payload/writer seam into
      `match_payloads.py` on reaching the 150-line limit.
- [x] CLI: `--game-id` replaced by `--opponent-id` + `--write-artifacts`. The
      old flag could only express the wrong thing.

## 8.4 Settlement consensus — complete

- [x] **Test first**: `tests/unit/test_settlement.py` (scope) and
      `test_settlement_signature.py` (serialization + wiring).
- [x] `src/reporting/settlement.py`: the trimmed symmetric outcome — five-key
      sub-game rows (`tie` is derivable and stays out of the preimage) and the
      signed aggregate. Scores read from `config["scoring"]`.
- [x] Both peers build the same preimage from their own side; the test
      constructs both and asserts byte equality.
- [x] Wired into `mutual_agreement` as `consensus` + `sha256` — the first thing
      in that block an opponent can independently recompute. Omitted without a
      role: two of our own peers settle nothing.
- [x] Our wire role `police` translated to the contract's `cop`, since role
      names sit inside the signed preimage.

## 8.5 Open — needs the opposing group, not more code

- [x] Confirm `axis_origin_corner` spelling with the pairing (`"topleft"` here,
      `"top-left"` in the kit's example vectors). A term whose VALUE must match
      exactly; our engine validates the literal, so this is a joint decision.
- [x] Confirm `pheromone_min_center_intensity = 0.5` is the pairing's value.
- [x] `tokens_total_series` is not tracked anywhere in this repo.
- [x] Run one real cross-group match. Conformance against fixtures is evidence,
      not proof — §10.7 remains open until a match with another group runs.
