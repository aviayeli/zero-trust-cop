# PRD 15 — Do not hold the opponent's session across the pause

## Problem

PRD_14 added `--sub-game-pause`, a window at each sub-game boundary for an
opponent that launches one process per sub-game. It worked: the first live run
with it crossed the boundary with **zero** pairing collisions, where five
previous attempts had all collided.

It died anyway, two seconds before the window closed, and the cause is in the
fix itself.

`lazy_opponents` opens a session per opponent endpoint and keeps it for the
series. The pause sits inside that held session. So the sequence is:

1. sub-game 1 ends; we bank the artifact at 19:35:43;
2. we sleep for ninety seconds, still holding their session open;
3. their sub-game-1 process exits — **which is the entire point of the
   window**;
4. the held session's background stream fails 502, its anyio task group
   unwinds, and the exception propagates out through the exit stack;
5. our run dies at 19:37:11, before the window it was waiting out closes.

The traceback names the held session, not a new dial:
`reference_launch.py:78 async with open_session()` →
`reference_dial.py:99 AsyncExitStack` → `reference_dial.py:37
streamable_http_client`.

The codebase already knew this shape. `lazy_opponents`' own docstring records
that holding a session idle for 190 seconds against a 180-second watchdog got
it reaped, and lazy opening was the fix. The pause reintroduced exactly that
idle hold, on purpose and in the worst possible place: across the interval in
which the opponent is expected to disappear.

A second constraint surfaced from the opponent at the same time, and it
bounds the window from above: **their handshake timeout is 60 seconds**, so a
90-second pause outlives it and they give up before we have started dialling.
The pause must be shorter than their handshake timeout and longer than their
process swap.

## Requirements

* **FR1** — The opponent's sessions are closed and forgotten at the sub-game
  boundary, before the pause, so nothing of theirs is held across a window in
  which they are expected to exit.
* **FR2** — The next sub-game reopens on first use, exactly as a first dial
  does today. A released endpoint must be indistinguishable from one never
  opened.
* **FR3** — Releasing must not fail the series. A session whose far side has
  already gone will raise on close; that is the normal case here, not an
  error.
* **FR4** — With no pause configured, nothing releases and nothing changes.
  The zero-pause path stays byte-identical.
* **FR5** — The existing callers of `lazy_opponents` are untouched. It yields
  the same callable it yields today.
* **FR6** — No file over 150 lines; a failing test before every line.

## Out of scope

* Choosing the pause length. It is bounded below by their swap time and above
  by their handshake timeout, and both are theirs to measure.
* Retrying a handshake the opponent has already abandoned. If they time out
  waiting for us, the sub-game is lost and the series restarts by agreement.
* Making our own peers relaunch per sub-game.

## Acceptance

* A sub-game boundary with a pause closes every open opponent session first.
* The following sub-game opens a fresh one on first use.
* A release whose underlying close raises leaves the series running.
* A run with `--sub-game-pause 0` opens, holds and closes sessions exactly as
  it does today.
