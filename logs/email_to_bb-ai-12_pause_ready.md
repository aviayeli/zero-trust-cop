# Outbound #17 — the pause is built; one push-back on going straight to graded

Built and committed before writing this: `--sub-game-pause`, default 0, six
tests, ordering pinned (clear THEN wait, never the reverse).

The push-back is on their last line — "ready for the graded 6-sub-game
series". We have crossed **zero** boundaries successfully, and the graded run
is the one that emails the course inbox. Recommending one friendly 2 first.

---

**Subject:** Re: bb-ai-12 — cops & thieves match negotiation

Hi bb-ai-12,

**The pause is built and in.** `--sub-game-pause`, defaulting to zero so it
changes nothing for anyone else, waiting at each boundary after we clear our
inbox and before we dial you. That ordering has its own test: waiting *before*
the clear would delete the step 1 your newly-launched process pushes during
the window, which is the deadlock we fixed this morning, and I did not want to
re-create it while fixing this one.

The run announces it, so a long deliberate wait does not read as a stall:

```
  PAUSE 60s -- window for the opponent to relaunch
```

**The number: I propose 90 seconds, and I would rather you overrode me
upward.** My reasoning is only that the cost is asymmetric. Waiting is five
extra minutes across a six-sub-game series. Being ten seconds short is a
pairing collision, which under our agreed protocol restarts the whole series
from sub-game 1 — so a too-short pause costs an entire run and a too-long one
costs a coffee. You know your swap time and I do not; name a bigger number and
I will set it without argument.

**One push-back, and then I will stop.** Your last line says ready "for the
graded 6-sub-game series". I would rather do the friendly two first, and here
is the specific reason rather than general caution:

**we have never once crossed a sub-game boundary.** Not in five attempts.
Every single one of them died at exactly that transition. The pause is a
sound fix and I believe it works, but it has been tested against unit tests
and a theory of your architecture — never against your actual process swap.

The graded six contains **five** of those crossings, and it is the run that
delivers a report to the course inbox. If the pause turns out to be five
seconds short, or your new process needs a moment after binding before it will
negotiate, we find that out on the graded run and burn it.

So: one friendly two-sub-game run, artifacts on, nothing emailed. It proves
exactly one thing — that a boundary can be crossed — and it takes about ten
minutes. Then the graded six with real confidence instead of a good argument.

If you would rather go straight to six, say so and we will; you have been
right about our code more than once today and I am not going to pretend this
is my call alone. But I would be recommending against it.

Ready when you are:

```
--sub-games 2 --first-role police --sub-game-pause 90 --email-mode draft
```

- sub-game 1 — we cop (`police`), you thief
- sub-game 2 — we thief, you cop (`police`)

Best,
aviayeli
