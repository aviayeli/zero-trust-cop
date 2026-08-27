# PRD 22 — Persist the opponent's disclosed chain and our verdict on it

## Problem

Our server already does the hard part and then throws it away.

`reference_tools.py::submit_audit` validates an inbound audit, re-hashes every
record against the digest that peer pushed at the time, and appends the whole
payload plus our verdict to an in-process `audits` list. Its own docstring
says why that list exists:

> *discarding the payload meant asserting a verdict nobody could recheck --
> and made it impossible to catch an opponent walking through a cell our board
> holds as a wall.*

`audits` is never written anywhere. It lives in the runner process and dies
with it. An accepted audit is also silent: `_refused` logs a warning on
rejection, acceptance logs nothing.

So after a series we hold a verdict nobody can recheck — the exact thing the
docstring warns against — and we cannot show, afterwards, that the opponent's
chain reached us at all.

This surfaced against SMNGRP05. We reported "zero records disclosed, all six
sub-games". We were wrong: `their_audit_response` is the REPLY to our own
outbound call, a receipt for our payload, never a carrier for theirs. When
they asked the obvious follow-up — *did you log an inbound submit_audit from
us?* — we could not answer in either direction. Zero refusals in our log is
equally consistent with "nothing arrived" and "it arrived and was recorded
nowhere".

Their position, and ours: survivable in a friendly, not in a counted series.
A settlement rests on being able to show you received and verified the other
side's chain. This is precondition 2 of 2 for the graded rematch.

## Requirements

**FR1** — An accepted inbound audit is persisted into that sub-game's log file
on disk: the disclosed records as received, and our verdict on them.

**FR2** — Records are persisted **as received**, byte-for-byte. They are the
preimages of digests the opponent pushed; normalising or re-serialising them
before storage destroys the only evidence that lets anyone recheck the
verdict. This is the same boundary PRD 21 FR2.0 draws.

**FR3** — Acceptance stays quiet on stdout. The persistence IS the record;
a log line is not evidence and a per-sub-game line is stdout spam. Refusals
keep their existing warning.

**FR4** — A sub-game with no inbound audit persists that fact distinguishably
from one that was never checked. Absent and empty must not look alike — the
whole defect above is an absence that could not be told from anything else.

**FR5** — The accumulator is cleared per sub-game, exactly as `app.inbox` is,
so sub-game 4's log cannot inherit sub-game 3's audit.

**FR6** — Every touched module stays at or under the 150-line ceiling.

## Non-goals

* Changing what we SEND. Our outbound audit stays `{sender, records,
  result_claim}` — a fourth key breaks opponents building with `cls(**data)`.
* Re-opening, replaying or amending any completed series.
* Making `their_audit_response` carry their chain. It is a receipt; that
  reading was our error and it stays a receipt.
