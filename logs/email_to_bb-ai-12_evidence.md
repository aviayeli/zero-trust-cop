# Outbound #6 — their timing data solved it; my hypothesis was wrong twice

Measured, not reasoned:

- our session-open retry against a 502 endpoint: single POST, uniform 5s
  (15 requests, gaps `[5,5,5,5,5,5,5,5,6,5,5,5,5,5]`). My "uniform ~5.4s"
  prediction was RIGHT about that path — and that path is not what they logged.
- `await_turn(repush_every=20)` x `poll_interval_sec=0.5` = **10.0s**.
  Their gaps: `[0,0,1,1,10,11,10,10,11]`. Exact match.
- `progress` fires at `claims_match_loop.py:81`, AFTER `await_turn` returns.
  Zero progress lines means zero completed ROUND TRIPS, not zero pushes.
- `receive_turn` returns HTTP 200 carrying `{"status":"refused"}` for a
  message that fails validation, and does NOT append it to the inbox.

---

**Subject:** Re: bb-ai-12 — cops & thieves match negotiation

Hi bb-ai-12,

Your timing data solved it, and it did so by proving me wrong twice. Thank you
for capturing it before my theory arrived — that is exactly why it was worth
anything.

**Wrong once: "we never sent a turn."** I based that on our runner printing
zero `step N pushed` lines. I have now read the code instead of assuming it:
that line is emitted *after* we receive your reply for the step, not when we
send ours. Zero lines means zero completed round-trips. It says nothing about
what we sent. We were almost certainly sending the whole time.

**Wrong twice: "those ten requests were our 5-second retry loop."** I measured
it rather than guessing this time — pointed our client at a dead endpoint and
logged what it emits. Our session-open retry is a single POST every 5.0
seconds, uniform, no GET, no 202. Your log has a GET, a 202 and ~10.5s gaps.
Categorically not that path. Your reading was correct and mine was not.

**What your data actually matches.** While we wait for your reply to a step, we
re-send the *same* sealed turn every `repush_every` polls. That is 20 polls at
`poll_interval_sec = 0.5` — **exactly 10.0 seconds**. Your gaps:

```
13:06:08  GET  200   \
13:06:08  POST 202    |  session open
13:06:08  POST 200   /
13:06:09  POST 200      negotiate
13:06:10  POST 200      turn, step 1  -- our first push
13:06:20  POST 200   \
13:06:31  POST 200    |  the SAME step-1 turn, re-pushed
13:06:41  POST 200    |  every 10s while we waited for yours
13:06:51  POST 200    |
13:07:02  POST 200   /
```

So the ten requests are: connect, negotiate, one turn, and five re-pushes of
that one turn. **Your "7 turns" and "9 turns" were almost certainly one turn
re-sent 7 and 9 times, not 7 and 9 distinct turns.** The re-push is deliberate
— identical bytes, identical digest, safe under the kit's at-least-once
contract — and it exists precisely so a peer that is not reading yet does not
deadlock us.

Which means we never advanced past **step 1** in either attempt.

**So the real question is why your step-1 turn never reached our loop — and I
think the answer is on our side, in a way your 200s would hide.**

Our `receive_turn` returns **HTTP 200 even when it refuses the message**. The
body carries `{"status": "refused", "reason": "..."}` and the message is *not*
appended to our inbox. A 200 in your tunnel log is therefore not evidence that
we accepted anything — only that our tool ran.

Could you check the **response body** of your `receive_turn` calls? If it says
`refused`, the `reason` field names the exact field that failed. Our validator
requires every one of `step`, `sender`, `hint`, `smell_grid`, `commit`,
`timestamp` on every turn, with `smell_grid` a dict of `"r,c" -> number`.

Two specifics worth confirming regardless, because our loop matches on both:

- **`step` numbering.** We wait for *your* message carrying `step == 1` for our
  step 1. If yours starts at 0, we will wait forever while you re-send happily.
- **`sender`.** We require `"police"` or `"thief"` literally — a team code or
  anything else there is refused.

That single check should end this. If your body says `accepted` and carries our
step, then the fault is further into our loop and I will go dig there.

**We are live again** and I will keep us up:

- you as thief -> our cop: https://luxury-pregnancy-wilder.ngrok-free.dev/mcp
- you as cop -> our thief: https://cardinal-shell-moistness.ngrok-free.dev/mcp

Best,
aviayeli
