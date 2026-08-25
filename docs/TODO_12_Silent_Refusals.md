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

## 12.7 It paid for itself on the first live run (2026-08-25 14:09-14:16)

The diagnostics were live for one run against bb-ai-12 and named both faults
at once, after two days in which neither side could see anything:

```
WAITING on their step 1 (re-pushed 1x) | our inbox: 1 msg, steps=[2], senders=['thief']
...
submit_audit REFUSED step=None sender='thief': result_claim: required object
```

- [x] **`inbox_depth` was the field that mattered, exactly as PLAN §5 argued.**
      1, not 0. They HAD reached us. Every earlier hypothesis on both sides
      assumed one of "they never reached us" or "we stopped sending", and both
      were wrong.
- [x] **Fault A: their first turn carries `step: 2`; we wait on `step: 1`.**
      A deadlock neither side could error on -- we re-push our step 1 every
      10s forever, which from their side reads as a stream of turns. That is
      the origin of their "7 turns" and "9 turns": one turn of ours, re-sent.
- [x] **Fault B: their `submit_audit` omits `result_claim`.** Refused before
      anything is stored, which is why they saw an empty reply.
- [x] **A correction to us:** their endpoint DID serve us in that window --
      we opened a session, negotiated and pushed. The 502s are intermittent,
      not the permanent one-directional wire we told them it was.

Nothing here needed a new experiment, a new probe or another round of
correspondence. Two lines of diagnostic output, once.

## 12.8 The fault was OURS, and bb-ai-12 found it (2026-08-25)

I read `inbox: 1 msg, steps=[2]` and concluded their first turn was numbered 2.
It was not. They came back with message-level logging showing our server had
answered `{"status":"accepted","step":1}` to their step 1 -- and both records
were true at once.

- [x] **`claims_runner` cleared the inbox AFTER the handshake.**

          handshake = await negotiate(...)   # a network round-trip
          app.inbox.clear()                  # unconditional

      Our server is bound and answering throughout. A peer that negotiates and
      pushes immediately lands its step 1 DURING that round-trip, and the clear
      destroys it. We then wait for a step 1 we had already accepted and
      deleted; they wait for the step 2 we will not send until we see it.
      Neither side errors and both re-push forever.
- [x] Fixed by clearing FIRST, before anything that awaits. The clear itself is
      right -- a turn from the previous sub-game must not satisfy this one's
      step 1, and `test_the_previous_sub_games_residue_is_still_dropped` keeps
      that honest. What was wrong was doing it after a call the opponent can
      push into.
- [x] `tests/scripts/test_inbox_race.py` reproduces the live deadlock with an
      opponent that pushes during the handshake and then answers nothing.

**The lesson, which is mine.** The diagnostic told me the inbox held step 2 and
nothing else. That is evidence about the inbox, not about what they sent -- and
I read it as the latter. A second read of `claims_runner` before writing to
them would have caught it; instead I sent a confident, wrong diagnosis and they
had to disprove it with their own logs. Third time in this exchange I asserted
past my evidence. The diagnostics are only as good as the care taken reading
them.

## 12.9 The fix worked: 35/35 steps, first complete exchange (14:26-14:31)

First run after moving the inbox clear ahead of the handshake:

```
  step  1 pushed MOVE:S | theirs +0.0s
  ...
  step 35 pushed MOVE:W | theirs +0.0s
```

- [x] **All 35 steps, both directions, nothing refused.** `theirs +0.0s` on
      every step: their turn was already in our inbox when we polled. Not a
      limping exchange -- perfect lockstep for a whole sub-game.
- [x] The deadlock is closed. Three failed attempts and two days of
      correspondence, and the cause was one unconditional `clear()` on the
      wrong side of an await.

- [ ] **Still open, and theirs: the sub-game was PLAYED, not SETTLED.** Our
      closing `submit_audit` got 502 -- their peer exits once it has pushed
      its own last turn. Without the mutual audit there is no verdict, no
      cross-team evidence and no artifact; the result would be a claim rather
      than something a grader can re-verify. A sub-game ends at the audit
      exchange, not at step 35.
