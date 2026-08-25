# Hyperparameter search — and why the champion cannot simply be applied

32,000 games. 80 configurations × 200 games × two evader profiles.

```bash
PYTHONPATH=src .venv/bin/python -m scripts.grid_search \
    --profile C_bluffer --games 200 --out docs/grid_search_C.json
```

Grid: `decay_per_step` ∈ {0.05, 0.10, 0.15, 0.20, 0.25}, `emit_intensity` ∈
{0.5, 0.7, 0.9, 1.0}, `max_consecutive_stay` ∈ {2, 3, 4, 5}.

## The negative result, first

**Against profile C (the deceptive bluffer): zero of 80 configurations
captured anything, across 16,000 games. No knob moved any metric.**

This is reported rather than smoothed into a "best available" cell, because
crowning a least-bad point in a space where every point scores zero would
misrepresent the search. It is also the more useful finding: the failure
against a perfectly-informed deceiver is not in the parameters.

## The positive result

Against profile A (random walker), the search does separate cells:

| | decay | intensity | κ | capture | mean steps | thaw fired |
|---|---|---|---|---|---|---|
| **champion** | 0.25 | 0.5 | 2 | **100.0%** | **9.3** | 129 |
| shipped | 0.10 | 0.9 | 3 | 99.0% | 10.7 | 308 |

A 1-point capture gain and a 13% reduction in steps-to-capture.

## The physical intuition

All three moves in the same direction, and they mean one thing: **make the
belief forget faster.**

`decay_per_step` 0.10 → 0.25 shortens the exponential memory. Section II of
the paper gives the switching lag

```
L = ceil( ln(1 + d·M₀/ΔK) / -ln(1-d) )
```

which falls sharply in `d`. At d=0.10 a signal parked for 18 turns costs 6
turns of lag; at d=0.25 the accumulated mass M₀ is far smaller and the belief
follows within one or two. Under belief uncertainty a **short memory beats an
accurate one**, because the field is not estimating a static quantity — it is
tracking a moving target through a channel that lags.

`emit_intensity` 0.9 → 0.5 flattens the deposited kernel, which lowers M₀ for
the same number of deposits: the same effect by another route.

`max_consecutive_stay` 3 → 2 is the smallest admissible bound, and the
`thaw_fired` count falling 308 → 129 shows why the other two matter more: with
a faster-forgetting belief the pursuer arrives on a stale target far less
often, so the refutation rule has less to do. **The parameters are doing the
work the thaw was compensating for.**

## Why this is NOT applied to config

`decay_per_step` and `emit_intensity` are **two of the fourteen signed
contract terms** (`mcp_server/terms.py`). They enter the pre-game terms hash,
so changing either unilaterally makes our `negotiate` signature disagree with
the opponent's and the handshake is refused. They are **renegotiable, not
tunable** — a proposal to make to an opponent before a match, not a local
edit.

`max_consecutive_stay` is private to our `[strategy]` block and *could* be
lowered to 2 unilaterally. We have not: its only measured effect is on profile
A, where the shipped value already captures 99%, and it is exactly the kind of
single-profile tuning that overfits a benchmark. Left as-is pending a wider
profile set.

## What to do with this

Propose `decay_per_step = 0.25`, `emit_intensity = 0.5` at the next
negotiation, with this table as the argument. Both sides benefit — a
faster-forgetting belief helps whichever peer is pursuing — so it is a
plausible mutual agreement rather than a concession.

And note what it does *not* fix: profile C stays at 0%. That gap is the
train/test mismatch in `FINDING_pheromone_carryover.md`, and only retraining
addresses it.
