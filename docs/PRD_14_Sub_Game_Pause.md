# PRD 14 — A window for an opponent who relaunches between sub-games

## Problem

`play_series` goes from one sub-game's `submit_audit` straight into the next
sub-game's `negotiate`. There is no pause of any kind; the gap is
milliseconds. That is right for a peer that serves both roles from one live
process, which is what we are.

bb-ai-12 are not. They run **one manually-launched process per sub-game** —
an operator starts either their police repo or their thief repo, whichever
that sub-game needs — and nothing on their side persists or transitions
between sub-games. Their architecture is conformant; the league format does
not require a peer to be long-lived.

The two shapes deadlock at every boundary, and the mechanism took five failed
attempts to see:

1. they launch their sub-game-1 process with the correct role;
2. we play the sub-game and exchange audits;
3. **their sub-game-1 process is still bound** — they added a shutdown-grace
   period so our closing `submit_audit` would stop hitting a peer that had
   already exited, and that grace window is still open;
4. our sub-game-2 `negotiate` arrives milliseconds later and that still-live
   process answers, declaring *its* role, the sub-game-1 one;
5. `pairing_refusal` correctly refuses, and the series ends.

Both sides were reading this as the other's bug for most of a day. Neither is:
their process answers honestly about itself, our runner advances correctly,
and the two facts are simply incompatible at millisecond separation.

Launching back-to-back by hand cannot fix it. There is no human-speed window
between an audit and the next handshake, and an operator trying to hit it is
racing their own shutdown grace.

## Requirements

* **FR1** — The runner can be told to wait a configured number of seconds
  between sub-games, giving a relaunching opponent a real window to bring one
  process down and the next up.
* **FR2** — The default is **zero**, and a zero pause must be
  indistinguishable from today: same call sequence, no sleep, no output.
* **FR3** — The pause falls **between** sub-games only. Never before the
  first, where nothing has ended yet, and never after the last, where it would
  only delay the artifacts.
* **FR4** — The pause happens **after** the inbox is cleared, not before.
  Clearing after a pause would delete the turns their newly-launched process
  pushes during it — the exact deadlock fixed earlier today.
* **FR5** — The wait is announced, so an operator watching a long pause knows
  it is deliberate rather than a stall.
* **FR6** — The pause is injectable, so the suite proves the ordering without
  sleeping through it.
* **FR7** — No file over 150 lines; a failing test before every line.

## Out of scope

* Guessing the right pause. It depends on how fast the opponent's operator
  works and is theirs to name; we take a number.
* Retrying a refused handshake. A pairing collision is a real disagreement
  about who is playing which side, and waiting longer does not resolve it.
* Making our own peers relaunch per sub-game. Ours are long-lived by design
  and that is the shape the wire is happiest with.

## Acceptance

* `--sub-game-pause 60` waits sixty seconds before sub-games 2..n and not
  before sub-game 1.
* `--sub-game-pause 0` — the default — performs no wait at all.
* The clear still precedes the pause, so a turn pushed during the window
  survives into the sub-game it belongs to.
