# TODO 21 — executes PLAN 21

Strict TDD throughout: write the failing test, confirm it fails for the stated
reason, then write the minimum to pass.

## T1 — Appendix F compliance

- [ ] **T1.1 red** `test_every_shipped_config_obeys_appendix_f` — fails with
      `ModuleNotFoundError: engine.appendix_f`
- [ ] **T1.2 red** `test_a_lowered_permanent_value_is_named_in_the_failure`
      (`min_games_to_pass: 1` → message names field, 1, 2, קבוע)
- [ ] **T1.3 red** `test_zero_below_a_floor_fails` (`max_barriers: 0`)
- [ ] **T1.4 red** `test_raising_a_minimum_is_permitted` (`max_barriers: 20`)
- [ ] **T1.5 red** `test_the_unmandated_pheromone_field_is_not_checked`
- [ ] **T1.6 green** `src/engine/appendix_f.py`
- [ ] **T1.7** module ≤ 150 lines

## T2 — sender and result_claim

- [ ] **T2.1 red** `test_sender_accepts_a_role_or_a_group_id`
- [ ] **T2.2 red** `test_sender_still_refuses_empty_and_non_strings`
- [ ] **T2.3 red** `test_result_claim_accepts_a_string_or_an_object`
- [ ] **T2.4 red** `test_escape_maps_to_survival`
- [ ] **T2.5 red** `test_case_and_whitespace_do_not_change_a_claim`
- [ ] **T2.6 red** `test_an_unknown_outcome_is_refused_not_guessed`
- [ ] **T2.7 red** `test_normalisation_never_touches_a_hashed_preimage`
      — THE boundary test (FR2.0)
- [ ] **T2.8 green** `src/mcp_server/wire_vocab.py`
- [ ] **T2.9 green** swap the two rules in `wire_v3_session.py`
- [ ] **T2.10** confirm `wire_v3.py`'s turn-level sender rule is UNCHANGED
- [ ] **T2.11** confirm we still send exactly three audit keys (FR2.5)

## T3 — series tie award

- [ ] **T3.1 red** `test_a_level_series_awards_tie_score_to_both`
- [ ] **T3.2 red** `test_a_three_three_split_with_unequal_points_gets_no_award`
      — the corrected trigger; keying on 3–3 would fail here
- [ ] **T3.3 red** `test_a_four_two_split_with_equal_points_does_get_the_award`
- [ ] **T3.4 red** `test_tie_score_comes_from_the_agreed_config`
- [ ] **T3.5 red** `test_the_two_settled_digests_still_reproduce`
      — `c39d331c...` and `5077306a...`/3997 (FR3.5)
- [ ] **T3.6 green** `award_series_tie`, applied in both aggregates
- [ ] **T3.7** confirm `settlement.py` and `official_scope.py` ≤ 150; if either
      crosses, extract the shared aggregate rather than bend the ceiling

## T4 — close out

- [ ] **T4.1** full suite green
- [ ] **T4.2** `ruff check .` clean
- [ ] **T4.3** documented test/file counts updated (self-enforced)
- [ ] **T4.4** published evidence bundle still passes `sha256sum -c`, 9/9

## Out of scope

Replaying a series, editing filed artifacts, sending email.
