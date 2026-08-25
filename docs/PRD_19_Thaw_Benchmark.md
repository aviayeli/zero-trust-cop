# PRD 19 — Measure the thawed cop against a diverse thief pool

## Problem

PRD_18 thawed the cop and proved it on one replay: g01's real belief
trajectory, where the 16-turn freeze is capped at 3. That proves the rule
fires on the case it was built for. It measures nothing.

We do not know the thawed cop's capture rate, its steps-to-capture, or whether
some other belief pattern freezes it in a way the g01 trajectory never showed.
Shipping a strategy change on one replay is the same mistake as shipping the
pheromone reset would have been: plausible, unmeasured.

**The existing harness cannot answer it.** `tournament_loop.play_episode`
feeds `state_key` the opponent's TRUE position via `_last_resolved`, so
`hybrid_opponent_cell` returns it directly and never consults the pheromone
field. The freeze requires the pheromone fallback. A benchmark through that
path would exercise none of the code under test and report a clean bill for a
bug it cannot reach.

So the harness has to reproduce what the WIRE does: no observed position,
belief built only from the argmax of a grid the opponent chooses to transmit.

## Requirements

* **FR1** — The cop's belief comes only from a transmitted smell grid, never
  from a true position, exactly as `claims_adapters._observer` does it.
* **FR2** — Four thief profiles, differing in movement AND in what they
  transmit:
  * **A** random walker, honest grid;
  * **B** greedy distance-maximiser, honest grid;
  * **C** deceptive bluffer — moves to evade, transmits a grid whose argmax is
    pinned to a fixed corner. This is bb-ai-12's observed behaviour and the
    case the thaw exists for;
  * **D** corner-hider — reaches a corner and stays, honest grid.
* **FR3** — Reported per profile: capture rate, mean steps to capture, total
  and longest `STAY` run, and how often the thaw fired.
* **FR4** — Both arms measured: thawed and unthawed, same seeds, same
  profiles. A number without its baseline says nothing.
* **FR5** — Deterministic under a seed, so a reported figure can be
  reproduced.
* **FR6** — No file over 150 lines; a failing test before the harness is
  trusted.

## Out of scope

* Retraining. This measures the shipped tables under the shipped heuristic.
* Running over the real MCP wire. The wire is proven; what is unmeasured is
  the policy under belief uncertainty, and a local harness isolates that.

## Acceptance

* 1,000 games complete and produce a per-profile table.
* The unthawed arm reproduces long freezes against profile C; the thawed arm
  does not.
* Any residual freeze or loop is named in the report rather than smoothed away.
