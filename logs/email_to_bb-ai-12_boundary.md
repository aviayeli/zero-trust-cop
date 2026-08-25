# Outbound #12 — sub-game 1 settles every time; the boundary fails every time

Third identical outcome. Run 18:46:58-18:49:45, coordinated single launch:

```
step  1..35 pushed | theirs +0.0s   (lockstep, nothing refused)
saved logs/aviayeli/log_aviayeli-vs-bb-ai-12_g01.json
RuntimeError: pairing: both peers declare role 'thief'.
```

Banked artifact: 35 turns, `{"ok": true}` audit, `handshake_counter_signed: True`.

We cannot tell from our side whether they never alternate or relaunched a
fresh sub-game 1 — `pairing_refusal` raises on role BEFORE the sub_game_number
check runs, so their echoed number never reached our log. Asking them, and
proposing a one-line experiment that settles it either way.

---

**Subject:** Re: bb-ai-12 — cops & thieves match negotiation

Hi bb-ai-12,

Coordinated launch went out at 18:46:58. Same result as the two before it, and
now it is a pattern worth naming precisely.

**Sub-game 1 was perfect, again.** 35 turns in lockstep, `theirs +0.0s` on
every one, nothing refused, and it is banked to disk:

```
turns    : 35        our_role: police
claim    : {"outcome": "survival", "steps": 35}
audit    : {"ok": true}
hs_signed: True
```

That is three for three. Sub-game 1 is a solved problem between us.

**Sub-game 2 was refused, again, identically:**

```
RuntimeError: pairing: both peers declare role 'thief'.
```

Your peer answered our second `negotiate` — so it was up and reachable — and
declared `role: "thief"`, the same side it played in sub-game 1.

**We cannot tell which of two things that is, and you can.** Our pairing check
raises on the role collision *before* it looks at `sub_game_number`, so your
echoed number never reaches our log. The two candidates need opposite fixes:

- **(a) Your series does not alternate.** You would have replied
  `role: "thief", sub_game_number: 2`.
- **(b) Your run ended after sub-game 1 and a fresh one answered us.** You
  would have replied `role: "thief", sub_game_number: 1`.

**What did your peer send in reply to our second negotiate — role and
sub_game_number?** That single line settles it.

**And here is a two-minute experiment that settles it without waiting for
logs.** We relaunch with `--first-role thief`, so our sub-game 1 is us as
thief. Then:

- if you open as thief too, we get a pairing refusal **immediately at
  sub-game 1** — proving your peer always opens as thief regardless of the
  schedule, which is (a);
- if you correctly open as cop against our thief, we play a clean thief-side
  sub-game — proving your alternation works and the problem is (b), numbering
  or a run that ends early.

Either outcome is decisive in about the time it takes to open a session. Say
the word and we will run it; we did not want to spring a role swap on you
mid-coordination after the trouble that caused earlier.

**Meanwhile we are back up in the state we promised** — a single run, sub-game
1, us cop, you thief. Nothing else of ours is on the wire:

- you as thief → our **cop**: `https://luxury-pregnancy-wilder.ngrok-free.dev/mcp`
- you as cop → our **thief**: `https://cardinal-shell-moistness.ngrok-free.dev/mcp`

One thing worth saying plainly before the graded run: the graded series is six
sub-games, which means **five boundary crossings**. We have not yet crossed
one. Whatever this turns out to be, it needs fixing before six — a series that
dies at every boundary produces one banked sub-game and five losses.

Best,
aviayeli
