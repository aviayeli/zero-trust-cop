# PRD 16 — Emit the result in the league's own schema

## Problem

Our `result_<game_id>.json` is this project's own design. The code has said so
since Phase 6, in `match_log.py`:

> *SCHEMA CAVEAT: Appendix F of `police_thief_p2p.pdf` is not in this
> repository. Only the four FILENAMES come from the specification; the field
> layout of the config/log/result payloads is this project's own design and
> must be reconciled with the real appendix before submission.*

The README repeats it as a known limitation. That reconciliation has now
arrived: two result files from SMNGRP05, both `schema_version: "1.1"`,
`report_type: "final_game_result"`, describing themselves as the aggregate
"the lecturer needs to build the league standings".

Our layout does not match it anywhere that matters. The lecturer's tooling
will look for `final_result.total_score` and `sub_games[].score`; ours holds
the same numbers under `mutual_agreement.consensus.aggregate.total_score` and
`consensus.sub_games[].score`. A grader's parser gets nothing.

Every value the schema wants, we already have. This is a mapping, not new
measurement.

## Requirements

* **FR1** — `result_<game_id>.json` is emitted in the league schema:
  `schema_version`, `report_type`, `links`, `timezone`, `groups`,
  `num_sub_games`, `sub_games[]`, `final_result`, `mutual_agreement`.
* **FR2** — **The agreed hash is not disturbed.** `mutual_agreement.sha256`
  is carried through byte-identical. It was computed over the consensus
  preimage and independently confirmed by the opponent; re-deriving or
  re-serialising it would break a verified cross-team agreement.
* **FR3** — Every per-sub-game `score`, `winner_group` and `tie` comes from
  that same verified consensus, so the published numbers are the ones the
  hash covers.
* **FR4** — `started_at` / `ended_at` are derived from the timestamps their
  turns actually carried, not invented.
* **FR5** — Values we cannot know about the opponent are marked as theirs to
  declare, never guessed. Their commit is `declared-in-their-own-report`, the
  convention SMNGRP05 used for the same gap.
* **FR6** — The audit block reports what we actually verified. `log_verified`
  reflects their accepted re-hash of our chain; nothing claims a verification
  we did not perform.
* **FR7** — Our own richer artifact is preserved as evidence, not discarded.
* **FR8** — `timezone` is configured, not inlined.
* **FR9** — No file over 150 lines; a failing test before every line.

## Out of scope

* Re-playing the series. The match is over, the artifacts are sealed and the
  hash is agreed; this reformats what was recorded.
* Changing `log_*`, `config_*` or `declaration_*`. Only the result's shape
  was shown to be wrong.
* Inventing a token count. Both reference files carry zeros and we do not
  meter tokens.

## Acceptance

* The emitted result validates against the observed schema key-for-key.
* `mutual_agreement.sha256` equals the value bb-ai-12 independently confirmed.
* `final_result.total_score` sums the per-sub-game scores.
* The pre-existing artifact is still on disk under `logs/evidence/`.
