# TODO 17 — An offline verifier for a reference-v3 log

## 17.1 Tests first
- [ ] `tests/scripts/test_reference_replay.py` — the ten cases in PLAN §5,
      driven by the real graded logs

## 17.2 The verifier
- [ ] `src/scripts/reference_replay.py`, <= 150 lines
- [ ] Five checks: contiguity, re-hash, legality, connectivity, claimed length
- [ ] Re-hash via `interop.commit`; legality via `engine.barriers`
- [ ] The verdict STATES what it did not cover (FR4)

## 17.3 The dispatch
- [ ] `replay_match` routes on `wire_shape`; the native path untouched (FR2)
- [ ] Exit 0 verified / 1 refused (FR5)

## 17.4 Gates
- [ ] Full suite green; figures re-derived; every file <= 150 lines
- [ ] The six graded logs verify

## 17.5 Deliberately NOT done
- [ ] ~~Store their disclosed chain in the log.~~ That changes an artifact
      schema a graded submission already used, and `submit_audit` judged that
      chain live at the time.
- [ ] ~~Claim their chain was re-verified offline.~~ It is not in the file.
      Saying so is the whole point of FR4.
