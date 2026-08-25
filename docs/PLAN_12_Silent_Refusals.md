# PLAN 12 — Making a refused turn and a stalled wait visible

Derived from `PRD_12_Silent_Refusals.md`. Approved shape before any code.

## 1. What this phase must not do

Nothing about acceptance changes. `wire_v3.validate_turn_message` and
`wire_v3_session.validate_audit_payload` are read by this phase and edited by
none of it, and every tool returns exactly the payload it returns today. If a
single test that pins the wire has to change, the change is wrong.

The re-push behaviour is likewise untouched. It is correct — identical bytes,
identical digest, safe under the kit's at-least-once contract — and it is the
reason a peer that starts late does not deadlock us. What is missing is not
different behaviour but a record of it.

## 2. The two blind spots, and where the light goes

```
THEIR turn arrives
  receive_turn -> validate -> REFUSED
                              |
                              +-- returns {"status":"refused", ...}   (unchanged)
                              +-- does NOT append to inbox            (unchanged)
                              +-- _LOG.warning(...)                   (NEW, FR1)

OUR turn is outstanding
  await_turn -> poll -> poll -> ... -> repush
                                       |
                                       +-- await repush()             (unchanged)
                                       +-- on_repush({...})           (NEW, FR4)
```

Both are strictly additive. Remove the two new lines and the system behaves
exactly as it does now, which is the property the tests pin.

## 3. Why logging, not printing, on the server side

`reference_tools` is a library module registering tools on someone else's
`FastMCP`. A `print` there writes to whatever stdout the host happens to have,
which in the test suite is pytest's capture and in a real run is the operator's
console — but it also cannot be switched off, filtered, or asserted on
cleanly. `logging` gives `caplog` in tests and a level in production, and the
codebase already uses it exactly this way in `reporting.email_sender`.

The live entry point is what makes those records visible: `reference_run`
configures a stderr handler at WARNING, so an operator sees refusals without
any per-module printing.

## 4. Why a callback, not logging, on the client side

`await_turn` already takes `repush`; a second callback is the same shape and
keeps the decision about presentation with the caller. `reference_run` already
owns the console vocabulary for this run (`  step N pushed ...`), and the stall
line belongs beside it in the same voice. A log record would land in a
different stream from the progress line it is a counterpart to.

## 5. The diagnostic payload

`on_repush` receives what an operator actually needs to tell a desync from a
dead peer:

| key | why it is there |
| --- | --- |
| `step` | which step of ours is outstanding |
| `attempt` | how many times we have re-sent it — "9" is the number bb-ai-12 counted as nine turns |
| `inbox_depth` | zero means they never reached us; non-zero means they did and we are not matching |
| `inbox_steps` | a desync reads as a desync: they sent step 0 while we wait on 1 |
| `senders` | a wrong `sender` value is refused upstream, so anything unexpected here is worth seeing |

`inbox_depth` and `inbox_steps` together are what distinguishes the two live
hypotheses that cost us a day: "they never reached us" from "they reached us
and we dropped it".

## 6. Modules

| module | change | lines |
| --- | --- | --- |
| `src/mcp_server/reference_tools.py` | `_LOG.warning` on both refusal paths | 111 → ~122 |
| `src/scripts/claims_guards.py` | `on_repush` param + payload | 127 → ~145 |
| `src/scripts/claims_match_loop.py` | pass `on_repush` through | 112 → ~116 |
| `src/scripts/reference_run.py` | supply the printer, configure logging | 128 → ~140 |

`claims_guards` is the tight one at 127. If the payload builder does not fit,
it moves to a helper in the same file rather than growing `await_turn` itself.

## 7. Test plan (written first, all of it)

`tests/scripts/test_refusal_visibility.py`:

1. a malformed inbound turn logs a WARNING naming the failing field
2. …and the inbox is still not written to (FR2)
3. a well-formed turn logs nothing and IS stored (no false positives)
4. a refused `submit_audit` logs a WARNING too (FR3)
5. the returned payload is byte-identical to what it returns today (FR2)

`tests/scripts/test_stall_visibility.py`:

6. `on_repush` is called once per re-push, with the step and a rising `attempt`
7. it carries `inbox_depth`, `inbox_steps` and `senders` from the real inbox
8. an empty inbox and a mismatched-step inbox are distinguishable in the payload
9. absent `on_repush`, `await_turn` behaves exactly as before, re-push included
10. a raising `on_repush` never breaks the wait — a diagnostic must not be able
    to end a live series

(10) is the one that matters most. Every other line of this phase is optional
comfort; a diagnostic that can kill a graded run is worse than no diagnostic.

## 8. Order of work

PRD → PLAN → TODO → tests (failing, confirmed) → `reference_tools` →
`claims_guards` → `claims_match_loop` → `reference_run` → README figures →
full suite green.

The suite needs ports 8801/8802, which a live runner holds, so the final green
run requires stopping the peers for the duration. That is the only unavoidable
downtime in this phase and it is taken once, at the end.
