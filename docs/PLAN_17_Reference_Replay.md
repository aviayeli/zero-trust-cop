# PLAN 17 — An offline verifier for a reference-v3 log

Derived from `PRD_17_Reference_Replay.md`.

## 1. Dispatch on the shape the log declares

Our reference-v3 logs carry `wire_shape: "reference-v3"`; native ones do not.
So `main` reads the file, dispatches, and the two verifiers never meet:

```
log.get("wire_shape") == "reference-v3"  ->  reference_replay.verify(log)
otherwise                                ->  verify_log(...)     (unchanged)
```

That keeps FR2 structural rather than a promise: the native path is not
edited, and a native log cannot reach the new code.

## 2. What the new verifier checks, in order

| # | check | why it is not ceremony |
| --- | --- | --- |
| 1 | steps contiguous and ascending from 1 | a fabricated middle hides in a gap |
| 2 | every `ours` record re-hashes to its own commit | the seal; this is the load-bearing one |
| 3 | every sealed move is legal on the log's own barriers | a rewritten payload that re-hashes is still refutable by the board |
| 4 | the sealed positions form a connected walk | a payload edited to a legal-looking move still has to be reachable from the previous cell |
| 5 | `result_claim.steps` equals the turns actually recorded | a claim of a longer game than was played |

Check 2 uses `interop.commit`, the same function that sealed the record, and
check 3 reuses `engine.barriers`. Nothing is reimplemented.

## 3. The verdict must undersell itself (FR4)

```
Verified OK (reference-v3)
  35 sealed records re-hashed, steps 1-35 contiguous
  NOT COVERED: the opponent's disclosed chain is not in this file; it was
  judged live at submit_audit and their verdict is recorded as
  their_audit_response.
```

A marker reading `Verified OK` must not conclude that both chains were
re-verified offline. Stating the gap is the difference between evidence and a
claim.

## 4. Modules

| module | holds | budget |
| --- | --- | --- |
| `src/scripts/reference_replay.py` | the five checks and the verdict | <=150 |
| `src/scripts/replay_match.py` | the dispatch, four lines | 126 -> ~132 |

## 5. Test plan (written first)

`tests/scripts/test_reference_replay.py`, driven by the REAL graded logs:

1. all six graded logs verify
2. the verdict names how many records were re-hashed
3. it states what was not covered (FR4)
4. a payload edited in a copy is refused, naming the step
5. a nonce edited in a copy is refused
6. a missing step is refused as a gap
7. an illegal move is refused against the log's own barriers
8. a discontinuous walk is refused
9. `replay_match` dispatches on `wire_shape` and exits 0 on a graded log
10. a native log still takes the native path unchanged (FR2)

## 6. Order of work

PRD -> PLAN -> TODO -> tests -> `reference_replay` -> dispatch -> figures ->
suite green.
