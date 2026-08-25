# PRD 13 — A sub-game that was played is evidence, even unsettled

## Problem

`claims_match_loop.play_sub_game` ends like this:

```python
our_chain = client.records            # copied before the audit, deliberately
verdict = await client.audit(result_claim)
return {...}
```

If that `audit` call raises — their peer has gone, their tunnel 502s, the
session died — the exception propagates out of `play_sub_game`, out of
`play_series`, and out of the run. `summaries` is discarded, `on_sub_game` is
never called, and no log is written.

The cost is not theoretical. On 2026-08-25 against bb-ai-12 we played a full
35-turn sub-game, both sides pushing in lockstep, every turn sealed and
answered — and then their peer exited before our closing `submit_audit`
landed. All thirty-five sealed records were thrown away by an exception in the
last call of the sub-game. We had to play the whole thing again.

The adjacent risk was already seen. The line above `our_chain` says so:
*"Copied BEFORE the audit, which clears the buffer by design... Without this
copy a finished series holds nothing but numbers and there is no log left to
write."* The chain is rescued from the audit's own clear, and then lost anyway
to the audit's exception.

**An opponent hanging up first does not un-play a sub-game.** The moves were
made, the commitments were sealed, our chain is complete and self-consistent.
What is missing is their verdict on it — which is a different thing from the
game not having happened, and must be recorded as such rather than as nothing.

## Requirements

* **FR1** — A `submit_audit` that fails must not discard the sub-game. The
  summary is returned, with its steps, its terminal reason, our sealed chain
  and their turns intact.
* **FR2** — The failure is recorded IN the summary, naming the cause, so the
  artifact says plainly that no verdict was obtained. It must never look like
  an acceptance.
* **FR3** — An unsettled sub-game must not be laundered into a settled one.
  `mutual_agreement.confirmed` is `all(_accepted(...))` over the summaries, so
  an unsettled sub-game must make that `False` — and `send_game_report`
  already refuses to report an unconfirmed result. Both properties must
  survive this change unchanged.
* **FR4** — The series continues to the next sub-game if it can. A dead
  opponent will fail the next handshake and end the run there, which is
  correct; what must not happen is the run ending *before* the sub-game just
  played has been banked.
* **FR5** — A successful audit is completely unaffected: same verdict, same
  summary, same artifacts, byte for byte.
* **FR6** — An interrupt is still an interrupt. `KeyboardInterrupt` and
  `SystemExit` are not audit failures and must propagate.
* **FR7** — No file over 150 lines; a failing test before every line.

## Out of scope

* **Retrying the audit.** The opponent is gone; retrying into a dead endpoint
  buys a slower failure. `TurnClient.audit` clears the sealed buffer by
  design so a second audit cannot re-assert a sub-game, and reaching around
  that would be worse than the problem.
* **Resuming a series at sub-game N.** The other half of TODO_11 §11.13, and
  a separate phase. This one only stops us throwing away what we already
  have.
* **Claiming the result.** Without their re-hash we have our word for the
  outcome and nothing more. The artifact records a claim and an absent
  verdict, and the settlement consensus stays unconfirmed.

## Acceptance

* A sub-game whose closing audit raises still returns a summary carrying all
  its steps and its sealed chain, and `on_sub_game` still banks it.
* That summary's `their_audit_response` names the failure and is not
  accepted by `reference_artifacts._accepted`.
* A result built from it has `mutual_agreement.confirmed == False`, and
  `send_game_report` refuses it.
* A successful audit produces exactly what it produces today.
