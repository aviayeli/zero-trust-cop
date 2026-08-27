# TODO 20 — Confirming a settlement reached off the wire

Executes PLAN 20. Strict TDD: every task writes a failing test first,
confirms it fails for the stated reason, then writes the minimum to pass.

## T1 — the scope builder

- [ ] **T1.1 red** `tests/unit/test_official_scope.py::test_the_derived_scope_matches_the_settled_digest`
      Build the scope from `logs/evidence/ZeroOne0-vs-aviayeli/` and assert
      3997 bytes and sha256 `5077306a...0373`. Must fail with
      `ModuleNotFoundError: reporting.official_scope`.
- [ ] **T1.2 green** `src/reporting/official_scope.py` with `build`,
      `serialize`, `digest`. No opponent-supplied value read anywhere except
      the `their_commit` argument.
- [ ] **T1.3 red** `test_the_score_comes_from_the_agreed_config`
      Halve `config["scoring"]["capture_cop"]`; the scope must change. Fails
      if any score was copied rather than recomputed.
- [ ] **T1.4 red** `test_roles_are_police_and_thief_never_cop`
      Assert `"cop"` appears in no roles map. Guards the Appendix-F
      vocabulary against `settlement.py`'s `police -> cop` alias leaking in.
- [ ] **T1.5** confirm `official_scope.py` is <= 150 lines.

## T2 — verification

- [ ] **T2.1 red** `tests/scripts/test_settle_official.py::test_a_wrong_digest_refuses`
      A claimed sha that differs by one character returns a refusal naming the
      digest, and `confirmed` stays false.
- [ ] **T2.2 red** `test_a_wrong_byte_length_refuses_and_says_length`
      Reason mentions length, not digest — the localisation PLAN 20 asks for.
- [ ] **T2.3 red** `test_a_tampered_record_refuses_before_any_digest_check`
      Corrupt one commit in one log; refusal cites the record, not the digest.
- [ ] **T2.4 green** `verify` in `src/scripts/settle_official.py`, checks in
      the PLAN's order: six sub-games, records re-hash, length, digest.

## T3 — recording it

- [ ] **T3.1 red** `test_a_refusal_leaves_the_artifact_byte_identical`
      sha256 the artifact file before and after a failed confirm; equal.
- [ ] **T3.2 red** `test_a_match_sets_confirmed_and_records_provenance`
      `confirmed is True`, and `official_settlement` carries sha256,
      byte_length, serialization, method and channel.
- [ ] **T3.3 red** `test_the_historical_digest_survives_the_write`
      `mutual_agreement.sha256` still `c39d331c...` afterwards.
- [ ] **T3.4 green** `confirm` writes the block from PLAN 20.
- [ ] **T3.5** confirm `settle_official.py` is <= 150 lines.

## T4 — the override guard

- [ ] **T4.1 red** `test_no_cli_argument_can_set_confirmed_without_the_comparison`
      Walk the argparse parser; assert no option matches
      `force|override|assume|yes|confirm[-_]?only|skip`. Fails the day someone
      adds a convenience flag.
- [ ] **T4.2** assert `verify` has no default that makes its digest argument
      optional.

## T5 — apply it to the real series

- [ ] **T5.1** Run against `logs/aviayeli/result_ZeroOne0-vs-aviayeli.json`
      with ZeroOne0's published `5077306a...0373` / 3997.
- [ ] **T5.2** Confirm `confirmed: true` and the historical sha preserved.
- [ ] **T5.3** Re-run `sha256sum -c` on the published evidence bundle — the
      nine evidence files must be UNCHANGED; only the working result artifact
      is rewritten.
- [ ] **T5.4** Full suite green; documented test/file counts updated in
      README and PLAN.md, which the self-check tests enforce.

## Out of scope

Sending any email. Reporting stays a separate, explicitly authorised step and
nothing in this TODO invokes `send_game_report`.
