# PLAN 13 — A sub-game that was played is evidence, even unsettled

Derived from `PRD_13_Unsettled_Evidence.md`. Approved shape before any code.

## 1. One try/except, and nothing else

The whole change is the last three lines of `play_sub_game`:

```python
our_chain = client.records
verdict = await client.audit(result_claim)     # raises -> everything lost
return {...}
```

becomes a call that cannot take the sub-game down with it. Nothing else in
the loop, the runner, the writer or the artifacts changes. That is deliberate:
the further this reaches, the harder it is to be sure a settled sub-game still
behaves identically (FR5).

## 2. What an absent verdict looks like

```python
{"status": "unreachable", "accepted": False, "reason": "<type>: <message>"}
```

Three properties, each load-bearing:

* **`status` is not `"accepted"`** and **`accepted` is `False`**, so
  `reference_artifacts._accepted` returns False in both spellings it reads.
  That is what keeps `mutual_agreement.confirmed` False (FR3) and what keeps
  `send_game_report` refusing to report it.
* **`status` is `"unreachable"`, not `"refused"`.** They did not refuse our
  chain; they were not there to see it. A grader reading the artifact should
  be able to tell "they rejected our evidence" from "we never got an answer",
  because those are opposite claims about who is at fault.
* **`reason` names the exception**, so the artifact carries the cause rather
  than a bare flag.

## 3. Why the caught type is BaseException

anyio delivers a peer's 502 wrapped in a task group, so it arrives as a
`BaseExceptionGroup`, which does not subclass `Exception` — the same trap that
made `connect_and_play` fail to retry and cost a live window on 2026-08-24.
`except Exception` here would silently not apply to the exact failure this
phase exists to survive.

`KeyboardInterrupt` and `SystemExit` are re-raised (FR6), matching
`connect_and_play` and `netcheck._fatal`.

## 4. What deliberately does NOT change

| | why |
| --- | --- |
| the audit is not retried | the buffer is cleared by design so a second audit cannot re-assert a sub-game |
| the series still continues | a dead opponent fails the next handshake and ends the run there, which is right — the point is only that the *banked* sub-game survives |
| `our_chain` still copied before the audit | it already rescues the chain from the audit's own clear; this phase rescues it from the audit's exception |
| the result claim | still ours, still a claim, still settled only by their re-hash |

## 5. Modules

| module | change | budget |
| --- | --- | --- |
| `src/scripts/claims_match_loop.py` | the try/except and the absent-verdict shape | 116 → ~130 |

One file. If the verdict builder does not fit, it becomes a module-level
helper in the same file rather than growing the function.

## 6. Test plan (written first)

`tests/scripts/test_unsettled_subgame.py`:

1. an audit that raises still returns a summary, with every step intact
2. …and our sealed chain intact — the thing actually being rescued
3. the verdict names the cause and says `unreachable`, not `refused`
4. `reference_artifacts._accepted` rejects it in both spellings
5. a result built from it has `mutual_agreement.confirmed == False`
6. `send_game_report` refuses that result (the FR3 end-to-end)
7. an anyio-style `BaseExceptionGroup` is survived, not just an `Exception`
8. `KeyboardInterrupt` still propagates
9. a SUCCESSFUL audit produces exactly today's summary, key for key

(9) is the guard on the whole phase: this must be invisible to a healthy run.

## 7. Order of work

PRD → PLAN → TODO → tests (failing, confirmed) → `claims_match_loop` →
README figures → full suite green.

The suite binds 8801/8802, so the supervisor comes down for that one run.
