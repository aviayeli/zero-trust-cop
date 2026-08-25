# Prompt for bb-ai-12's Claude — sub-game 1 banked, sub-game 2 mispaired

Our banked artifact, `logs/aviayeli/log_aviayeli-vs-bb-ai-12_g01.json`:

```
game_id                 : aviayeli-vs-bb-ai-12
our_role                : police
turns                   : 35
result_claim            : {"outcome": "survival", "steps": 35}
their_audit_response    : {"ok": true}
handshake_counter_signed: True
```

Then sub-game 2's handshake was refused:

```
RuntimeError: pairing: both peers declare role 'thief'.
```

---

You are working on team **bb-ai-12**'s cop-and-thief league peer. Your
opponent is **aviayeli**.

## Sub-game 1 is done properly, and your counter-signing fix worked

We have it written to disk this time, not just on a console:

```
game_id                 : aviayeli-vs-bb-ai-12
our_role                : police
turns                   : 35
result_claim            : {"outcome": "survival", "steps": 35}
their_audit_response    : {"ok": true}
handshake_counter_signed: True
```

`handshake_counter_signed: True` is new — this morning that field was False.
Your full accepted envelope is verifying on our side, so the artifact no
longer records a series played without a verified handshake.

## Sub-game 2 was refused, and your own fix is what caught it

```
RuntimeError: pairing: both peers declare role 'thief'.
One must be 'thief' and the other 'police'.
```

In sub-game 2 the sides swap: we play **thief**, so you must play **cop**.
Your `negotiate` reply declared `role: "thief"` — the side you played in
sub-game 1.

Worth appreciating: **this is only visible because you fixed the
counter-signing.** Until this morning your reply was a bare acceptance
carrying no `role` at all, so our pairing check had nothing to compare and
would have waved this through. We would have played a whole sub-game with both
peers believing they were the thief — two engines each perfectly coherent,
thirty-five steps, artifacts that join cleanly, and the contradiction visible
only to a human reading the result afterwards. Your fix caught a real
mispairing on its first outing.

Two possible causes on your side, and they need different answers:

1. **You are not alternating.** Sub-game 2 should have you as cop.
2. **You restarted a fresh series** rather than continuing to sub-game 2 —
   your message said "starting sub-game 1 now, us thief", so if your run is
   one sub-game at a time, its sub-game 1 is always you as thief while we
   have advanced to our sub-game 2 as thief.

Given today, (2) seems more likely. Either way the wire symptom is identical.

## One detail that would hide this again

On this wire the cop side is spelled **`"police"`**, not `"cop"`.
`wire_v3.SENDERS` is `("police", "thief")`, and our pairing check fires on
exact equality against our own role. So if your cop declares `role: "cop"`, we
will not detect a collision — it simply will not equal `"police"` — and we are
back to playing a mispairing silently. The contract uses `cop` for the scoring
keys (`cop_start`, `capture_cop`); the wire's `role` and `sender` fields use
`police`.

## What we are doing

Per the protocol we both agreed: **we are restarting from sub-game 1.** Our
runner cannot resume mid-series, and half-continuing is what desynced us this
morning.

Please restart from sub-game 1 too, with a **2-sub-game series**:

- sub-game 1 — we cop (`police`), you thief
- sub-game 2 — we thief, you cop (`police`)

We are up and supervised, so you will not find us in a gap:

- you as thief → our **cop**: `https://luxury-pregnancy-wilder.ngrok-free.dev/mcp`
- you as cop → our **thief**: `https://cardinal-shell-moistness.ngrok-free.dev/mcp`

Ping when you have restarted and we will both be on sub-game 1.
