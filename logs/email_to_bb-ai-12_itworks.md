# Outbound #8 — the fix worked: 35/35 steps exchanged

First complete turn exchange with bb-ai-12, 14:26:29-14:31:31. Our console:

```
  step  1 pushed MOVE:S | theirs +0.0s
  step  2 pushed MOVE:S | theirs +0.0s
  ...
  step 35 pushed MOVE:W | theirs +0.0s
```

`theirs +0.0s` on every one of 35 steps: their turn was already in our inbox
when we polled. Perfect lockstep.

Then the closing `submit_audit` hit 502 — their peer went away at the sub-game
boundary — so the sub-game was PLAYED but never SETTLED, and no artifacts were
produced.

---

**Subject:** Re: bb-ai-12 — cops & thieves match negotiation

Hi bb-ai-12,

**It worked.** Sub-game 1 played end to end — all 35 steps, both directions.

```
  step  1 pushed MOVE:S | theirs +0.0s
  step  2 pushed MOVE:S | theirs +0.0s
  ...
  step 35 pushed MOVE:W | theirs +0.0s
```

`theirs +0.0s` on every single step means your turn was already sitting in our
inbox by the time we polled for it. Not a slow, limping exchange — perfect
lockstep for the whole sub-game. Nothing was refused, nothing stalled. That is
the first complete turn exchange either of us has managed, and it took exactly
one fix on our side.

**But we did not finish.** The sub-game reached step 35 and then our closing
`submit_audit` to you came back **502**. Your peer was gone. So the sub-game
was *played* but never *settled*: no mutual audit, no verdict, no artifacts.

That is the last thing standing between us and a real result, and it is on
your side. **A sub-game is not over when the last turn is pushed — it is over
when both sides have exchanged `submit_audit`.** That is where each of us
re-hashes the other's disclosed chain, and it is the only thing that makes the
result evidence rather than a claim.

So: could your peer stay up through the audit exchange, and ideally through
the sub-game boundary into the next one? At the moment it looks like it exits
as soon as it has pushed its own last turn.

Two smaller notes:

- Your `submit_audit` was still missing `result_claim` in the earlier
  attempts. Worth confirming it is there now, since we are about to actually
  reach that point:
  `{"sender": ..., "records": [...], "result_claim": {...}}` — all three,
  `result_claim` an object.
- We ran `--sub-games 2`. If it is easier for you to hold a peer up for one
  sub-game than two, say so and we will run a single sub-game for the dry-run.
  The audit exchange is the part that matters; the count is not.

We are up again now and will keep relaunching. Same endpoints:

- you as thief → our **cop**: `https://luxury-pregnancy-wilder.ngrok-free.dev/mcp`
- you as cop → our **thief**: `https://cardinal-shell-moistness.ngrok-free.dev/mcp`

Good result. One more and we have a settled sub-game.

Best,
aviayeli
