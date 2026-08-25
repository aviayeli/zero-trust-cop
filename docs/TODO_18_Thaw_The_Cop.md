# TODO 18 — The cop must not be frozen by a signal it cannot verify

## 18.1 Tests first
- [ ] `tests/strategy/test_thaw.py` — cases 1-9 in PLAN §7
- [ ] `tests/strategy/test_thaw_replay.py` — case 10, the real g01 trajectory

## 18.2 The change
- [ ] `forbid` parameter in `_optimal_steps` / `manhattan_primary_action`
- [ ] `src/strategy/thaw.py`: falsified-belief rule + consecutive-STAY bound
- [ ] `AgentPolicy.decide` consults it; tables untouched (FR6)
- [ ] `max_consecutive_stay` in each role's `[strategy]` (FR5)
- [ ] Thief keeps STAY on its own believed cell (FR4)

## 18.3 Gates
- [ ] Full suite green; figures re-derived; every file <= 150 lines
- [ ] Replaying g01 shows no frozen run

## 18.4 Deliberately NOT done
- [ ] ~~Retrain on belief-derived state.~~ The deeper fix, recorded in
      FINDING_pheromone_carryover.md: 10,000 episodes and new committed
      deliverables, not a between-matches change.
- [ ] ~~Model their honesty on the smell channel.~~ A phase of its own.
- [ ] ~~Distrust their grid wholesale.~~ It is still the only signal we have;
      the fix is to stop resting on it once it is refuted.
