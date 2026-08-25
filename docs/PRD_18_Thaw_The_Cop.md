# PRD 18 — The cop must not be frozen by a signal it cannot verify

## Problem

In three graded cop sub-games our cop emitted `MOVE:STAY` for exactly 16
consecutive turns each -- 55 of 105 cop turns, 52% -- and never captured.
Replaying the sealed log against the opponent's own transmitted grids gives
the mechanism exactly:

```
step  our pos  their argmax   our BELIEF       move
   9   (5, 4)      (6, 6)       (6, 6)      MOVE:E
  12   (6, 6)      (6, 6)       (6, 6)      MOVE:E   <- we ARRIVE on the belief
  13   (6, 6)      (6, 6)       (6, 6)   MOVE:STAY   <- frozen from here
  28   (6, 6)      (0, 0)       (6, 6)   MOVE:STAY   <- their argmax has MOVED
```

Three faults compose:

1. **Their transmitted argmax parked at a corner for ~18 turns.** The smell
   grid is a self-report; its argmax is not their position, and
   `TODO_10 §10.14` already recorded that "the argmax of a received grid does
   NOT name the opponent's current cell".
2. **We chased it and arrived on it**, so the believed cell became our own.
3. **`relative == (0,0)` makes `STAY` uniquely distance-optimal**: every other
   move scores 1, `STAY` scores 0, and `manhattan_primary_action` only lets
   the Q-table break ties *within* the optimal set. So the table cannot
   override it however large its values.

And the belief cannot recover quickly even when their argmax moves: the field
is an exponentially-weighted history, `x_{t+1} = (1-decay)·x_t + K`, so a cell
that accumulated for 18 turns takes several fresh deposits elsewhere before
`strongest()` follows. Measured: 4 more turns at steps 24-32.

Two independent reviews reached the same reading. Codex derived the fixed
point and the recurrence; Gemini named the game theory: an unverified,
costless signal is **cheap talk**, whose only sequential equilibrium is
babbling, and a deterministic cop tracking it hands the thief a guaranteed
survival by transmitting a static fake argmax while evading elsewhere.

That is not a hypothesis about the opponent's intent -- we cannot know it --
but it is the exact behaviour their traffic produced, and the exploit works
whether or not it was deliberate.

## Requirements

* **FR1** — A cop that is standing on its own believed target and has not
  captured has empirically falsified that belief. It must stop treating the
  cell as the target rather than resting on it.
* **FR2** — No consecutive-`STAY` run may exceed a configured bound, for
  either role.
* **FR3** — When the belief is falsified, the cop moves usefully rather than
  randomly: toward unexplored board, not a coin flip.
* **FR4** — The thief is unaffected by FR1. Standing still is a legitimate
  evasive move for an evader and must stay available.
* **FR5** — Every bound is configured, never inlined.
* **FR6** — The trained tables are NOT retrained or invalidated. This
  constrains the move set the existing policy chooses from; it does not
  change what the policy values.
* **FR7** — No file over 150 lines; a failing test before every line.

## Out of scope

* Retraining on belief-derived state. That is the deeper fix, recorded in
  `FINDING_pheromone_carryover.md`, and it is a 10,000-episode run plus new
  committed deliverables -- not something to do between matches.
* Modelling the opponent's honesty. We already track a belief in their
  truthfulness for hints; extending it to the smell channel is a phase of its
  own.
* Changing what we transmit. Our own grid is honest and stays so.

## Acceptance

* Replaying the graded g01 board with the patched policy produces no
  16-turn frozen run.
* A cop standing on its believed target for the bound moves off it.
* A thief may still `STAY` indefinitely.
* Every existing strategy test passes unchanged.
