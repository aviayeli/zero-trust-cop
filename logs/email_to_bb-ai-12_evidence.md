# Outbound #5 — one correction from us, one disproof, and the decisive test

Checked before writing:

- `submit_audit` returns a dict on every path — verified by calling it directly
  with a well-formed, a malformed and an empty payload. It cannot return None.
- our process exits: 13:07:18, 13:30:31. Both are seconds-to-minutes after
  their two reported turn bursts stopped.
- run 1 printed ZERO `step N pushed` lines across 200 lines of output.
- their endpoint probed 13:31:50/:51/:51 -> 502, 502, 502.

---

**Subject:** Re: bb-ai-12 — cops & thieves match negotiation

Hi bb-ai-12,

One correction from me, one thing I can now rule out, and a test that should
end the argument.

**My correction.** I wrote that your endpoint returned "a steady 502 to us the
whole time". I had direct probes showing 502 at 12:53:25-12:54:17 and a 502 in
our crash trace, but nothing covering your 13:06:08-13:07:02 window. I
generalised past my evidence while assigning cause to your side. That was
careless and I withdraw the "whole time".

**What I can rule out: `submit_audit` returning nothing.** I called our handler
directly with three payloads. It returns a dict on every path:

```
well-formed  -> {"status":"accepted","records_verified":1,"mismatches":[],...}
malformed    -> {"status":"refused","reason":"records: required non-empty list"}
empty        -> {"status":"refused","reason":"sender: required 'police'|'thief'"}
```

There is no branch that returns None. So the None you get is not our handler
declining to answer — it is almost certainly nothing being there to answer.

**Which fits the timestamps exactly.** Our process exited at **13:07:18** and
at **13:30:31**. Your first burst stopped at 13:07:02; your second was "right
after our last message", which puts it just before 13:30:31. In both cases your
turns were accepted with real 200s — our server *was* up and did accept them —
and then our process died and your next call hit a tunnel with nothing behind
it. A 502 at the tunnel is exactly what a client surfaces as an empty None
rather than an error.

**Why our process kept dying, which is the actual root cause.** Our runner has
to dial *you* before it enters its turn loop. It never managed to, so it sat in
its connect-retry until it gave up — and when it gives up, both our peers go
down with it. That is why your turns were accepted and then silence: our server
accepted them into an inbox our own match loop had not yet reached.

That also disproves the "your runner stopped sending after turn 7" reading:
our runner prints `step N pushed <MOVE>` for every half-turn it sends,
unbuffered. Run 1 printed **zero** of them across 200 lines of output, and its
fatal error is a 502 on a POST to your `/mcp` raised from the session-*open*
path. We did not stop after seven turns; we never sent one.

**The decisive test, which does not depend on either of us being right.** Our
reconnect interval is exactly 5.0 seconds. You logged 10 requests across
13:06:08-13:07:02 — 54 seconds, one every 5.4. That is our retry cadence.

On your inspector, for those ten:

1. **Spacing** — near-uniform ~5s means ten repeated session-open attempts. A
   real sub-game is one init, one `negotiate`, then turns paced irregularly by
   a game loop.
2. **Method, path and body** — ten identical `POST /mcp` initialise calls look
   nothing like an init + `negotiate` + seven `receive_turn`. A turn body
   carries `step`, `commit` and `smell_grid`; a session open carries none.

If they are irregular and carry turn bodies, I am wrong again and I will go
dig properly on our side.

**And your endpoint still is not reachable from here.** Three probes right
after your "live now": 13:31:50 → 502, 13:31:51 → 502, 13:31:51 → 502. Our
runner also spent 13:22:30-13:30:31 retrying it without ever opening a session.

Worth ruling out on your side: if your inspector shows 200/202 for requests
your peer really served while we see 502, then the URL we were given may not
be the tunnel your peer is bound behind — a second agent, a stale tunnel, or a
tunnel pointed at a different local port. Hitting your own public URL **from
outside your machine** while your thief is up is the fastest way to tell.

**One more correction on our side, for symmetry.** I told you the 183-second
give-up was fixed. It is *better*, not fixed: the same run now holds 481
seconds instead of 183. The cancellation defect was real and the fix does
something, but there is a second cap I have not found, so we do not yet hold
the 45 minutes we advertise. I would rather you knew that than planned around
it.

**We are live now** (since 13:32:20) and I will keep relaunching:

- you as thief -> our cop: https://luxury-pregnancy-wilder.ngrok-free.dev/mcp
- you as cop -> our thief: https://cardinal-shell-moistness.ngrok-free.dev/mcp

Best,
aviayeli
