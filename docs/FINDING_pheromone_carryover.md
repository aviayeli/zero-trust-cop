# Finding — the pheromone field never resets, in training or in a series

Measured 2026-08-25 while asking whether a series could be resumed at
sub-game N. Recorded rather than fixed; the recommendation is at the bottom.

## What was asked

Does carrying the pheromone belief across sub-games change play, and would
resetting it make a resumed series faithful?

## What the measurements say

**1. The stale estimate never expires.**

```
belief NEVER expires: still (4, 6) after 500 decay steps
   (a sub-game is only 35 steps long)
```

`PheromoneField` decays geometrically in float, so `strongest()` keeps
returning a cell forever. Once the field has anything in it,
`hybrid_opponent_cell(None)` never returns None again for the life of the
process.

**2. It changes play, often.** Over 300 simulated sub-game-1 walks, entering
sub-game 2:

```
opening move differs from a fresh belief          : 163/300 (54%)
carried estimate >=3 cells from the thief's start : 213/300 (71%)
```

So we enter sub-game 2 believing the opponent is somewhere they demonstrably
are not — positions reset to `thief_start` every sub-game — and that changes
our opening move more than half the time.

**3. And training does exactly the same thing.** This is the part that
matters, and it inverts the obvious fix.

```
episode 0: cop's field at START = None     -> at END = (6, 6)
episode 1: cop's field at START = (6, 6)   -> at END = (6, 6)
episode 2: cop's field at START = (6, 6)   -> at END = (6, 6)
```

`train_diverse` builds the learner policies once and reuses them for all
10,000 episodes; `play_episode` calls `episode.reset()` but never touches the
policy's field. So `tournament_loop._last_resolved`'s own docstring —

> *"Returning None on turn 0 is what exercises the D2 fallback: the policy
> then asks its pheromone field instead, which is empty and yields None."*

— is true of **episode 0 and no other**. From episode 1 on, turn 0 was keyed
against a stale cell from the previous episode. The shipped tables were
trained that way.

## Why this must NOT be "fixed" now

Match behaviour and training behaviour currently AGREE: both carry. Resetting
the field per sub-game at match time would leave the tables trained one way
and played another — the same class of mismatch that `match_policy_mode`
exists to avoid, and PLAN.md §10.10 records what measuring that cost.

The coherent fix is to reset per episode in training AND per sub-game at match
time, then retrain both tables. That is a 10,000-episode run and a new pair of
committed deliverables. Doing it days before a graded series, on the strength
of a mid-league discovery, would trade a known regime for an unmeasured one.

## Consequence for resuming a series

A resumed run starts with an empty field where a continuous run would not, and
by (2) that changes the opening move about half the time. So a resume is not
byte-faithful to an uninterrupted series regardless of what we do — but it is
no *less* faithful than the first sub-game of any fresh run, which also starts
empty. `--start-at-sub-game N` remains a small change; it simply cannot claim
to reproduce a continuous series exactly.

## Recommendation

- **Now, before the league finishes:** change nothing. Record it.
- **After:** reset per episode in training and per sub-game at match time,
  retrain, and measure both regimes against the opponent pool before shipping
  whichever wins. Then a resume becomes exactly faithful as a side effect.
