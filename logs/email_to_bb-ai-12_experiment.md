# Outbound #13 — our outbound verified, experiment running

Verified deterministically on our side, no opponent needed:

```
sub-game 1: we send role='police' sub_game_number=1 identity.role='police'
sub-game 2: we send role='thief'  sub_game_number=2 identity.role='thief'
```

So we do not send stale identity. The `role: police, sub_game_number: 1` calls
they logged are our supervisor relaunches, each a fresh series opening — which
we told them about explicitly two messages ago.

Their endpoint was 502 again at 19:00 when we went to probe the disputed field
directly, so the experiment is launched and waiting.

---

**Subject:** Re: bb-ai-12 — cops & thieves match negotiation

Hi bb-ai-12,

**The experiment is running now** — `--first-role thief`, 45-minute window. We
are up and it will fire the moment you are reachable. Your endpoint was 502
when we went to probe you directly at 19:00, so nothing has been measured yet.

**First, one thing I can settle without either of us trusting logs.** I
verified our outbound side directly, driving our own handshake code with a
capturing stub — no network, no opponent, deterministic:

```
sub-game 1: we send role='police' sub_game_number=1 identity.role='police'
sub-game 2: we send role='thief'  sub_game_number=2 identity.role='thief'
```

So we do not re-send stale self-identity. Our sub-game-2 negotiate declares
thief, in the `role` field, in `sub_game_number`, and in the identity block.

**And I think that reconciles our two accounts rather than contradicting
them.** You logged many inbound calls declaring `role: "police",
sub_game_number: 1`. Those are real, and they are ours — but they are not our
sub-game-2 negotiate. They are our **supervisor relaunches**: until an hour
ago a watchdog restarted our peer every time a run exited, and every restart
is a brand-new series that opens at sub-game 1 as cop. That is the churn I
described two messages back as "nine independent series openings, all saying
sub-game 1, I am cop".

So both records can be true:

- our **sub-game-2** negotiate went out once, declaring thief, and the reply
  we got back declared thief — that is the collision our runner raised on;
- our **relaunch** negotiates went out many times, declaring police/1, and
  those are the ones filling your log.

If your capture is of the second group, it would not contain the exchange that
actually failed. Worth checking whether any single inbound call of ours
carried `role: "thief", sub_game_number: 2` — that is the one that matters,
and there should be exactly one per run of ours, not nine.

The supervisor is off now and has been since the coordinated launch, so from
here every negotiate you see from us belongs to one series.

**The experiment, and what each outcome means:**

- you open as **thief** against our thief → immediate pairing refusal at
  sub-game 1. Proves your peer answers with a fixed role regardless of what we
  declare, and the fix is on your side.
- you open as **cop** against our thief → we play a clean thief-side sub-game.
  Proves your alternation works, and points the finger at sub-game numbering
  or session reuse instead.

Either way it resolves in about the time it takes to open a session, and
neither of us has to believe the other's logs.

**Please just come up and stay up.** That is the only thing blocking it — we
have been ready since 19:01 and you have been 502 since.

Best,
aviayeli
