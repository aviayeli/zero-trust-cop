# TODO 16 — Emit the result in the league's own schema

## 16.1 Tests first
- [ ] `tests/scripts/test_league_result.py` — the ten cases in PLAN §5,
      driven by the real graded artifacts rather than fixtures

## 16.2 The translator
- [ ] `src/scripts/league_result.py`, <= 150 lines, pure translation
- [ ] `mutual_agreement.sha256` carried through byte-identical
- [ ] scores/winners/ties taken from the VERIFIED consensus rows
- [ ] `started_at`/`ended_at` from real turn timestamps
- [ ] opponent's commit marked `declared-in-their-own-report`
- [ ] `timezone` from `config/game.json`

## 16.3 Apply and verify
- [ ] Rewrite `logs/aviayeli/result_aviayeli-vs-bb-ai-12.json` in place
- [ ] Confirm the sha256 still equals the value bb-ai-12 confirmed
- [ ] Our richer original preserved under `logs/evidence/`
- [ ] Full suite green; figures re-derived

## 16.4 Deliberately NOT done
- [ ] ~~Re-derive the consensus hash.~~ It is agreed with the opponent. A
      recomputation that differed by a byte would break a verified agreement
      to satisfy a formatter.
- [ ] ~~Guess the opponent's commit, token count or games played.~~ Marked as
      theirs to declare, the convention the reference files themselves use.
- [ ] ~~Reformat log/config/declaration.~~ Only the result was shown wrong.
