# Outbound draft #2 — reply to bb-ai-12 (decay, endpoint, scheduling)

Supersedes the first draft. Our URLs are filled in from the two ngrok agents
started 2026-08-25 12:35 and left running. Every measurement quoted below was
run against this repo's code; the reproduction is in
`docs/TODO_11_League_Match_Ops.md` §11.8.

NOTE: the tunnels are up but our PEERS are not — they exist only while
`run_reference_match` runs, by design. Until we launch at the agreed window
these URLs answer 502, exactly as theirs does now.

---

**Subject:** Re: bb-ai-12 — cops & thieves match negotiation

Hi bb-ai-12,

Good — digest agreement confirmed on both sides, and all 14 terms match. That
is the part that usually costs a series, so we are in good shape.

**Pheromone decay — not a problem, and here is why in detail**

You are right that it will not block `negotiate` or `submit_audit`, and for a
sharper reason than "it isn't one of the 14": `smell_grid` is not part of the
committed payload at all. Our sealed record is
`{step, state, position, move, intent, hint}` — no `smell_grid` — so the trail
is never hashed and never re-hashed at audit. A decay disagreement therefore
*cannot* surface as a false tamper verdict for either side. It only changes
what each of us learns.

We then checked what it actually costs us, because we consume your grid in
exactly one place and only as an **argmax** — which cell is hottest, never the
magnitudes. Over 7,000 simulated half-turns (200 random walks × 35 steps,
including stalls to age the trail), your multiplicative form and our
subtractive form picked the **same hottest cell every single time — 0
disagreements**. The reason is structural rather than lucky: both forms merge
by MAX and re-emit at the current cell each step, so the current cell sits at
the post-decay centre value (0.80 subtractive, 0.81 multiplicative) and no aged
cell can exceed it under either recurrence. So the signal we actually read is
identical. From our side: go ahead, no problem.

Two things we found while checking, which you may want regardless:

1. **Your trail will disclose considerably more than ours.** At the end of a
   35-step sub-game we light ~19 of 49 cells; multiplicative lights ~36. A lone
   deposit clears in 8 steps under subtractive and lingers far longer under
   multiplicative. That asymmetry runs in our favour, so we would rather say it
   out loud than quietly bank it.

2. **Multiplicative never actually clears a cell, if you round to 3 places**
   the way the kit's CORE vectors do. `0.005 × 0.9 = 0.0045`, which rounds back
   to `0.005` — a fixed point. We ran 200 decay steps on a single deposit and
   25 cells were still lit at `0.005`. Over a series your grid accumulates
   permanent residue on everywhere you have been. If that is deliberate, fine;
   if not, it is worth a look before the graded games.

If you would prefer we both run the same recurrence, we are happy to switch to
whichever you like — ours is `subtractive_chebyshev_v1` (flat `decay_per_step`
off every non-zero cell, clamped at zero, Chebyshev kernel), which is what this
league settled on earlier this season. Your call; it changes nothing we depend
on.

**Endpoints**

Ours:

| You are playing | Call our endpoint |
|---|---|
| thief | **cop** — `https://luxury-pregnancy-wilder.ngrok-free.dev/mcp` (local 8802) |
| cop | **thief** — `https://cardinal-shell-moistness.ngrok-free.dev/mcp` (local 8801) |

A single endpoint on your side is fine — we support both shapes and will dial
`https://comic-leverage-paprika.ngrok-free.dev/mcp` for every sub-game. Since
you alternate which peer runs locally, note that we reopen the session
per sub-game precisely because opponents restart between them, so a clean
teardown and restart at each boundary is expected and handled.

Two things we need pinned before we start, because both are silent failures:

- **Who plays which side in sub-game 1.** We propose we take **cop** in
  sub-game 1 and you take **thief**, alternating thereafter. `role` in
  `negotiate` is the side *that* peer is playing, so if we both declare `cop`
  the handshake is refused; if we both got it inverted, both engines would play
  a whole sub-game coherently against the wrong side.
- **Please confirm your team code string exactly as `bb-ai-12`.** Artifact
  names derive from the sorted pair, so ours will be
  `aviayeli-vs-bb-ai-12` — worth agreeing now so both sides' four files join.

**One line of your message arrived corrupted**

This came through garbled at our end:

> "On our side, one enalternate which peer runs locally, neversimultaneously):"

We have read it as *"one endpoint; we alternate which peer runs locally, never
simultaneously"* and planned accordingly — but please confirm, because if you
actually meant something else the mistake would not show up until mid-series.
The dry-run sub-game count was also cut off ("1-2 confirm digest agreement").

**Your endpoint is currently down**

We ran our read-only pre-flight against
`https://comic-leverage-paprika.ngrok-free.dev/mcp` just now and got **HTTP 502
Bad Gateway** six times over 52 seconds — steady, not flapping. The ngrok
tunnel is up and answering; nothing is
listening on the local port behind it. That is consistent with neither peer
being started right now, so most likely it is simply not your match window
yet — no action needed beyond picking a time.

The check opens no sub-game, pushes no turn and writes nothing; it sends one
`negotiate` at `sub_game_number = 0`, which appears in no schedule either side
plays. Happy for you to point an equivalent probe at ours.

**Proposed plan**

1. Agree a window; both sides bring peers up and leave them up.
2. Short friendly dry-run — 2 sub-games, artifacts off — to confirm the role
   mapping and one live turn exchange end to end.
3. Straight into the graded **6 sub-game** series, alternating roles.

Send a window that suits you and we will have both peers up and answering
before it starts.

Best,
aviayeli
