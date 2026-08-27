# PLAN 22 — Persist the inbound audit

Implements PRD 22. No new module: the pieces already exist and are not wired.

## The wiring, end to end

```
reference_tools.submit_audit   verifies, appends to app.audits   [EXISTS]
claims_runner                  clears app.audits per sub-game    [ADD]
claims_runner                  harvests them into `closed`       [ADD]
reference_artifacts.build_log  writes the key into the log file  [ADD]
```

`claims_runner` already owns `app` and already clears `app.inbox` per
sub-game at line 79, for a reason PRD_14 FR4 spells out. The audit
accumulator gets the same treatment on the same line, so the two cannot drift.

## The persisted shape

```json
"their_disclosed_audits": [
  {"sender": "...", "records": [...], "result_claim": "...",
   "verdict": {"status": "accepted", "checked": 36, ...}}
]
```

A LIST, and present-but-empty when nothing arrived (FR4). `null` would be
indistinguishable from an older artifact written before this field existed,
and telling those apart is the entire point.

Records go in exactly as `submit_audit` received them (FR2). `submit_audit`
already deep-copies each record on append, so the stored payload cannot be
mutated afterwards by a later caller.

## Line budget

```
reference_tools.py     134   unchanged -- it already does this work
claims_runner.py       127   +3   clear, harvest
reference_artifacts.py 128   +1   one key in build_log
```

All well clear of 150. If any crosses, the harvest moves to a helper rather
than the ceiling being bent.

## Tests, red first

`tests/scripts/test_inbound_audit_persistence.py`

* an accepted inbound audit lands in the sub-game log ON DISK, with its
  records and our verdict -- the load-bearing case
* the persisted records are byte-identical to what was submitted (FR2)
* a sub-game with no inbound audit persists `[]`, not absent (FR4)
* a REFUSED audit is not persisted -- a verdict of cheating with the evidence
  kept is fine, but a refused payload never entered the record and must not
  start now
* the accumulator is cleared per sub-game: two sub-games do not share one
  audit (FR5)
* acceptance writes nothing to stdout (FR3)
