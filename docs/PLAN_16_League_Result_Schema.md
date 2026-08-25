# PLAN 16 — Emit the result in the league's own schema

Derived from `PRD_16_League_Result_Schema.md`.

## 1. A translator, not a new writer

`reference_artifacts.build_result` and `reporting.settlement.build_consensus`
stay untouched. The consensus they produce is the hash preimage, and that hash
is now agreed with the opponent — anything that re-derives it risks breaking a
verified agreement for cosmetic reasons.

So: one pure function, `league_result(ours, logs)`, taking our result dict and
the six sub-game logs, returning the league-shaped dict. It measures nothing;
every value is copied or read.

## 2. Where each field comes from

| league field | source |
| --- | --- |
| `game_id`, `game_uid` | ours, unchanged |
| `groups` | `sorted(consensus.sub_games[0].roles.values())` |
| `num_sub_games` | `len(ours["games"])` |
| `links.*` | derived from `game_id`, the convention the schema states |
| `links.github` | `repos` from our result (ours only; theirs is theirs to declare) |
| `timezone` | `config/game.json` (FR8) |
| `sub_games[].roles/score/winner_group/tie` | the VERIFIED consensus rows |
| `sub_games[].result` | `terminal_reason` from our games rows |
| `sub_games[].started_at/ended_at` | first/last `theirs.timestamp` in that log |
| `sub_games[].github_commit` | ours real; theirs `declared-in-their-own-report` |
| `sub_games[].tokens` | zeros — we do not meter |
| `sub_games[].audit` | what we verified: their audit response, tamper flag |
| `final_result.*` | `consensus.aggregate`, plus league bookkeeping |
| `mutual_agreement` | `sha256` and `confirmed`, carried through (FR2) |

## 3. The two examples disagree, so take the intersection

SMNGRP05's two files differ: the bb-ai-12 one has a six-field `audit` and no
`links.github`; the imreeyal one has a two-field `audit` and does have
`links.github`. Both are `schema_version: "1.1"`.

So the required core is what both carry, and the extra fields are tolerated
additions. We emit the core plus the extras we can support honestly —
`opponent_present`, `results_agree` and `opponent_result_claim` are real
information about this match and cost nothing to include.

## 4. Modules

| module | holds | budget |
| --- | --- | --- |
| `src/scripts/league_result.py` | the translation, and a `__main__` to rewrite a result in place | ≤150 |
| `config/game.json` | `timezone` | +1 |

Nothing else changes. `send_game_report` attaches whatever
`result_<game_id>.json` holds, so rewriting the file is the whole delivery
change.

## 5. Test plan (written first)

`tests/scripts/test_league_result.py`, driven by the REAL graded artifacts:

1. the top-level key set matches the schema exactly
2. `report_type` and `schema_version` are the league's literals
3. `mutual_agreement.sha256` is byte-identical to ours (FR2) — the one that
   must never drift
4. `num_sub_games` is 6 and `sub_games` has six rows numbered 1..6
5. each row's `score` equals the verified consensus row's score (FR3)
6. `final_result.total_score` equals the sum of the row scores
7. `started_at` / `ended_at` come from real turn timestamps and are ordered
8. the opponent's commit is marked as theirs to declare, not guessed (FR5)
9. `links.*` filenames derive from `game_id`
10. `timezone` comes from config, and is absent from source (FR8)

## 6. Order of work

PRD → PLAN → TODO → tests → `league_result` → rewrite the graded result →
verify the hash survived → figures → suite green → send.
