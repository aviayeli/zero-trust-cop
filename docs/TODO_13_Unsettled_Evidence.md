# TODO 13 — A sub-game that was played is evidence, even unsettled

Derived from `PLAN_13_Unsettled_Evidence.md`.

## 13.1 Tests first (must fail before any implementation)

- [ ] `tests/scripts/test_unsettled_subgame.py` — the nine cases in PLAN §6
- [ ] Confirm they fail for the right reason, not a typo

## 13.2 The change

- [ ] Wrap the closing `client.audit(...)` so a failure cannot discard the
      sub-game
- [ ] Absent verdict: `{"status": "unreachable", "accepted": False,
      "reason": "<type>: <message>"}`
- [ ] `unreachable`, NOT `refused` — they did not reject our chain, they were
      not there to see it, and those are opposite claims about fault
- [ ] Catch `BaseException` (anyio wraps a 502 in a task group), re-raise
      `KeyboardInterrupt` / `SystemExit`
- [ ] Nothing else changes: no retry, no schema change, no artifact change

## 13.3 The properties that must survive

- [ ] `mutual_agreement.confirmed` is False for an unsettled sub-game
- [ ] `send_game_report` still refuses an unconfirmed result
- [ ] A successful audit is byte-identical to today

## 13.4 Gates

- [ ] Full suite green (supervisor down for the run); figures re-derived

## 13.5 Deliberately NOT done

- [ ] ~~Retry the audit.~~ `TurnClient.audit` clears the sealed buffer by
      design so a second audit cannot re-assert a sub-game. Reaching around
      that is worse than the problem.
- [ ] ~~Resume a series at sub-game N.~~ The other half of TODO_11 §11.13 and
      a phase of its own.
- [ ] ~~Treat our own claim as the outcome.~~ Without their re-hash we have
      our word and nothing more. The artifact records a claim and an absent
      verdict.
