# TODO 12 — Making a refused turn and a stalled wait visible

Derived from `PLAN_12_Silent_Refusals.md`. Nothing here is executed until it
appears above.

## 12.1 Tests first (must fail before any implementation)

- [ ] `tests/scripts/test_refusal_visibility.py` — cases 1-5 in PLAN §7.
- [ ] `tests/scripts/test_stall_visibility.py` — cases 6-10 in PLAN §7.
- [ ] Confirm both fail for the right reason (missing param, missing log
      record), not for a typo in the test.

## 12.2 The refusal is recorded (FR1-FR3)

- [ ] `_LOG.warning` on the refusal path of `receive_turn`, naming the reason
      plus `step` and `sender` where present.
- [ ] Same on `submit_audit`.
- [ ] The returned payload and the inbox are UNCHANGED. A test pins the return
      value so this can never quietly become a behaviour change.

## 12.3 The stall is visible (FR4-FR6)

- [ ] `await_turn` grows `on_repush=None`, called immediately before each
      re-push with `{step, attempt, inbox_depth, inbox_steps, senders}`.
- [ ] Absent the callback, behaviour is bit-for-bit what it is today.
- [ ] **A raising `on_repush` is swallowed**, exactly as a raising `repush`
      already is. A diagnostic that can end a graded series is worse than no
      diagnostic.
- [ ] `claims_match_loop.play_sub_game` passes it through.
- [ ] `reference_run` prints it in the same voice as the progress line, and
      configures a stderr handler so the server-side refusal warnings are
      actually seen.

## 12.4 Documentation and figures

- [ ] README: note that a refused inbound message is logged, and what the
      stall line means, in the live-match runbook.
- [ ] `git add` the new files, re-derive the README/PLAN figures.
- [ ] Full suite green — needs ports 8801/8802, so the live peers come down
      for that one run and go straight back up.

## 12.5 Deliberately NOT done

- [ ] ~~Return a non-200 HTTP status for a refused message.~~ Returning the
      refusal in the body under 200 is conformant, both league opponents do
      it, and changing it unilaterally mid-season would break peers that are
      currently working. The blindness worth fixing is ours.
- [ ] ~~Retry or repair a refused message.~~ A refusal is a real
      disagreement; papering over it is how a desync becomes a signed
      artifact.
- [ ] ~~Change `repush_every` or `poll_interval_sec`.~~ The 10-second cadence
      is correct. It was only ever a problem because nothing reported it.

## 12.6 Why this phase exists

Recorded so the cost is not forgotten. On 2026-08-25, against bb-ai-12:

- we refused (or never matched) their step 1 and told nobody;
- we re-pushed our step 1 nine times and printed nothing;
- they read nine of our re-pushes as nine turns and an unbroken run of HTTP
  200s as nine acceptances;
- we read our own zero progress lines as "we never sent a turn".

Four wrong conclusions, two of them ours, none of them possible if either side
had been able to see what the other was actually doing. The wire was working
the whole time.
