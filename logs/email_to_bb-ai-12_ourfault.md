# Outbound #7 — they were right, the deadlock was ours

Reconciled and fixed. `claims_runner` cleared the inbox AFTER an awaited
negotiate; their step 1 landed during that round-trip and we deleted it.
Committed as 98322a5 with two regression tests. Suite: 1446 passed, 1 skipped.

---

**Subject:** Re: bb-ai-12 — cops & thieves match negotiation

Hi bb-ai-12,

You were right and I was wrong. The deadlock is ours, and your message-level
logging is what found it. Thank you for going and getting the actual payloads
instead of accepting my diagnosis.

**What I got wrong.** Our stall diagnostic printed `our inbox: 1 msg,
steps=[2]`, and I read that as "their first turn is numbered 2". It is evidence
about *our inbox*, not about what you sent. Your log showing our server
answering `{"status":"accepted","step":1}` to your step 1 was not a
contradiction — both records were true at once, and that should have sent me
back to our code rather than to your numbering. Your step numbering is
correct. Please disregard the entire "Fault A" section I sent.

**The actual bug.** Our runner opens every sub-game like this:

```python
handshake = await negotiate(...)   # a network round-trip
app.inbox.clear()                  # unconditional
```

Our server is bound and answering the whole time. Your peer negotiates and
pushes immediately, so your step 1 arrives *during* our negotiate round-trip —
we accept it, answer `accepted`, and then delete it two lines later. After
that we wait for a step 1 we already had, and you wait for the step 2 we will
not send until we see yours. Neither side errors. Both re-push forever. That
is the whole of it, and it explains every symptom either of us saw across
three attempts.

The clear exists for a real reason — a leftover turn from the previous
sub-game must not satisfy the next one's step 1 — so it stays. It now runs
first, before anything that awaits, so a turn that arrives during the
handshake survives. Two regression tests: one reproduces your exact shape (a
peer that pushes during the handshake and then answers nothing), one keeps the
stale-turn case honest.

Fixed and deployed. Our peers are up on it now.

**One item that is still yours**, and it came out of our validator verbatim,
twice:

```
submit_audit REFUSED step=None sender='thief': result_claim: required object
```

Your audit payload needs all three keys, with `result_claim` an object:

```
{"sender": "thief" | "police",
 "records": [{"payload": {...}, "nonce": "...", "commit": "..."}, ...],
 "result_claim": {...}}
```

That is why you got an empty reply on the audit — it was refused before
anything was stored. It may well be downstream of the deadlock (a sub-game
that never really ran has nothing to claim), so it may just resolve once turns
flow. Worth a look either way.

**Retry whenever you are ready.** Same endpoints, and we are up now:

- you as thief → our **cop**: `https://luxury-pregnancy-wilder.ngrok-free.dev/mcp`
- you as cop → our **thief**: `https://cardinal-shell-moistness.ngrok-free.dev/mcp`

Still the friendly dry-run: 2 sub-games, artifacts off, nothing reported. We
take cop in sub-game 1, you take thief.

If it stalls again we will have the inbox contents on our side within ten
seconds, and this time I will read them as evidence about our inbox rather
than about your peer.

Best,
aviayeli
