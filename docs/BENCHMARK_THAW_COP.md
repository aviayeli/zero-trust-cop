# Benchmark — the thawed cop under belief uncertainty

1,000 games. 125 per thief profile per arm, four profiles, thawed and
unthawed on identical seeds. Reproduce with:

```bash
PYTHONPATH=src .venv/bin/python -m scripts.benchmark_simulation \
    --games 125 --seed 20260826 --out docs/benchmark_thaw.json
```

## Why not the existing harness

`tournament_loop.play_episode` hands `state_key` the opponent's TRUE position,
so `hybrid_opponent_cell` returns it and never consults the pheromone field.
The freeze requires that fallback. A benchmark through that path would have
exercised none of the code under test and reported a clean bill for a bug it
cannot reach — so this harness reproduces the wire instead: the thief emits a
trail, we read only its argmax, and the cop decides from that.

## Results

| profile | arm | capture | mean steps | STAY moves | longest STAY | thaw fired |
|---|---|---|---|---|---|---|
| A random | thawed | **100.0%** | 10.5 | 0 | 0 | 171 |
| A random | unthawed | 99.2% | 8.9 | 166 | 4 | — |
| B greedy | thawed | 0.0% | — | 0 | 0 | 500 |
| B greedy | unthawed | 0.0% | — | 1000 | 6 | — |
| C bluffer | thawed | 0.0% | — | 0 | **0** | 1500 |
| C bluffer | unthawed | 0.0% | — | 2875 | **23** | — |
| D corner | thawed | 100.0% | 12.0 | 0 | 0 | 0 |
| D corner | unthawed | 100.0% | 12.0 | 0 | 0 | — |

## What this says

**The freeze is gone.** Against the bluffer the unthawed cop stood still 2,875
times with a longest run of 23 turns; the thawed cop has a longest run of
**zero**. That is the defect PRD_18 targeted, eliminated.

**And it did not become captures.** Profiles B and C are 0% in BOTH arms. The
freeze was never the reason we failed to capture a competent evader — we do
not capture one either way. Unfreezing the cop made it chase; chasing is not
catching.

That is the finding worth carrying forward, and it corrects an implication in
PRD_18: the thaw is **necessary and insufficient**. It removes a pathology; it
does not add pursuit skill.

**Honesty is not punished.** Profile D transmits truthfully and sits in a
corner — an argmax that never moves, indistinguishable on the wire from
profile C's lie. The thaw never fires there (0 firings) and capture stays at
100%. The rule keys on "I am standing on my belief and have no capture to
claim", which is false for D because we capture on arrival.

**A small cost on the easy case.** Against a random walker the thaw trades 8.9
mean steps for 10.5 — about 18% slower — to convert the last 0.8% of escapes.
Worth it under the agreed scoring, where a capture is 20 and a survival 10.

## Edge cases and residual risk

* **No freeze or loop survived in any thawed arm.** Longest STAY run is 0
  across all four profiles.
* **The thaw fires very often against C** — 1,500 times across 125 games, on
  roughly a third of all decisions. That is the belief being wrong a third of
  the time, not the rule being trigger-happy: each firing is a step where we
  stood on a cell the argmax named and nothing was there.
* **Profiles B and C are stronger than a real opponent.** Both are given the
  cop's TRUE position while the cop only has belief. On the real wire neither
  side sees the other, so these are an upper bound on evader strength, not a
  model of bb-ai-12. The 0% should be read as "against a perfectly-informed
  evader", not "against any evader".
* **One policy, one board.** `barrier_seed` is null in the shipped contract,
  so every game runs on an empty 7x7. Barriers would change pursuit geometry
  and are untested here.

## What this implies for the next match

The scoring pays 20 for a capture and 10 for survival, so the cop is the side
worth improving — and this says the improvement is **not** in the freeze.
It is in pursuit under a belief that is wrong a third of the time, which
points back at the transfer gap recorded in `FINDING_pheromone_carryover.md`:
the tables were trained on true positions and are played on an argmax that
lags by several turns.

That is a retraining problem, not a heuristic one.
