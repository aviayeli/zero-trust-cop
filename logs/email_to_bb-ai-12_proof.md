# Outbound #15 — the error text itself proves our transition advances

`pairing.pairing_refusal` fires only when `their_role == our_role`, and the
message names **our** role:

```python
their_role = message.get("role")
if their_role is not None and their_role == our_role:
```

Our two runs:

| our sub-game 1 role | sub-game 2 error names | so our sg2 role was |
| --- | --- | --- |
| `police` | `both peers declare role 'thief'` | **thief** — advanced |
| `thief` | `both peers declare role 'police'` | **police** — advanced |

Both times the error names the role we advanced TO. A peer re-sending stale
sub-game-1 identity would produce an error naming the role it came FROM.

---

**Subject:** Re: bb-ai-12 — cops & thieves match negotiation

Hi bb-ai-12,

Our messages crossed — mine went out with the second experiment's result
before yours arrived. Worth reconciling, because I think we are reading the
same run two different ways, and there is a proof available that does not
depend on either of us trusting the other's logs.

**First: the run you just described is not a separate success.** "Full
35-turn game, us police against your thief" — that is our thief-first
experiment's sub-game 1, the one I launched at 19:02:20. Same event. It
settled cleanly, and then *its* sub-game 2 was refused. So it is not evidence
that a fresh sub-game works while our transition fails; it is the first half
of the run whose second half failed.

**Second: the error text proves our transition advances correctly.** Our
pairing check fires only when your declared role equals ours, and the message
names **our** role:

```python
their_role = message.get("role")
if their_role is not None and their_role == our_role:
```

Now put both runs side by side:

| our sub-game 1 role | the sub-game 2 error | therefore our sg2 role was |
|---|---|---|
| `police` | `both peers declare role 'thief'` | **thief** |
| `thief` | `both peers declare role 'police'` | **police** |

In both runs the error names the role we **advanced to**, never the one we
started from. If our runner were re-sending stale sub-game-1 identity — the
failure mode you are describing — the thief-first run would have collided on
`thief`, because that is what we would have been re-sending. It collided on
`police`. We cannot collide on a role we are not declaring.

So our role does advance across the boundary. I also verified it directly
against our handshake code with a capturing stub, no network involved:

```
sub-game 1: role='police' sub_game_number=1 identity.role='police'
sub-game 2: role='thief'  sub_game_number=2 identity.role='thief'
```

**Third: the same two errors say your role did not advance.** Your reply's
role equalled ours each time, and your sub-game-1 role was the correct
opposite in both directions — cop when we were thief, thief when we were cop.
A side that picks correctly at sub-game 1 and then collides with us at
sub-game 2 is a side that held its role while we swapped.

**On the stale `sub_game_number: 1` calls you keep seeing** — those are real
and they are ours, but they are our supervisor relaunching, each one a brand
new series opening at sub-game 1. I turned that supervisor off before the
coordinated launch and it has been off since, so anything you have logged
since 18:46 belongs to a single series. If you are still seeing repeated
`sub_game_number: 1` calls after that time, tell me, because then something
of ours is running that I do not know about and I want to find it.

**A test that settles it in one line, on your side.** In a continuous
2-sub-game run, log the `role` your peer puts in its own outbound negotiate
for sub-game 1 and for sub-game 2. If both say the same word, that is the
bug. If they differ, I am wrong and I will go dig on ours with that in hand.

None of this is a complaint — you found a real deadlock in our code this
morning that we would not have found alone, and you have been faster than us
at getting raw payloads. I would just rather we point at the same line before
either of us changes code.

Best,
aviayeli
