# PRD 12 — Making a refused turn and a stalled wait visible

## Problem

On 2026-08-25 a live series against bb-ai-12 ran twice, produced nothing, and
neither side could see why. It cost two rounds of correspondence and two wrong
diagnoses from us before their independently-captured request timestamps
settled it. Both halves of the blindness are ours.

1. **A refused inbound turn is invisible to BOTH sides.**
   `reference_tools.receive_turn` validates the message, and on failure returns
   `{"status": "refused", "reason": ...}` **without appending it to the
   inbox**. That reply leaves as **HTTP 200**. An opponent watching status
   codes therefore sees an unbroken run of 200s while every message they send
   is being dropped — which is exactly what bb-ai-12 reported as "turns
   exchange cleanly, all 200/202 on our side". Our own side prints nothing at
   all: the refusal is returned and forgotten, so the operator watching our
   console cannot tell a peer we are refusing from a peer that is silent.

   Our `negotiate` docstring already warns that a peer reading only one field
   "must not read a refusal as silence". The identical trap exists here, in
   the other direction, with nothing to surface it.

2. **A stalled wait is silent, and looks to the opponent like a flood.**
   `claims_guards.await_turn` re-sends the same sealed turn every
   `repush_every` polls while their reply is outstanding. That is correct
   behaviour and deliberately cheap. But it prints nothing, and
   `claims_match_loop` emits its `progress` line only *after* the wait
   returns — so a loop stuck on step 1 produces **no output whatsoever** while
   emitting a request every ten seconds. From the opponent's side that reads
   as a healthy stream of turns; from ours it reads as a hang. bb-ai-12
   counted our re-pushes of one turn as "7 turns" and then "9 turns", and we
   counted our own zero progress lines as "we never sent anything". Both
   readings were wrong and the wire gave neither side anything better.

The two combine into the worst case: we refuse their step 1, they never learn,
we wait for a step 1 that will never arrive, and we re-push ours forever. Both
consoles are quiet, both tunnels are busy, and the series never starts.

## Requirements

* **FR1** — A refused inbound message is logged on the receiving side, naming
  the tool, the reason, and enough of the message to act on (`step` and
  `sender` where present).
* **FR2** — Logging a refusal must not change what the tool returns or what it
  stores. The wire contract is unchanged; this phase adds observability only.
* **FR3** — A refusal must be logged for every reference-v3 tool that can
  refuse: `receive_turn` and `submit_audit`.
* **FR4** — While `await_turn` is re-pushing, the caller can observe each
  re-push: which step, how many attempts so far, and what the inbox actually
  holds (depth, the steps present, the senders seen).
* **FR5** — The observation in FR4 is optional and diagnostic. Absent a
  callback, `await_turn` behaves exactly as it does today, including the
  swallowing of a failing re-push.
* **FR6** — The live entry point prints the FR4 diagnostic, so an operator
  watching a stalled series sees "still waiting on their step 1, re-pushed
  N times, our inbox holds ..." instead of nothing.
* **FR7** — Every artifact honours the project constraints: no file over 150
  lines, no tunable inlined in source, a failing test before every
  implementation line.

## Out of scope

* Changing validation, the wire, the handshake, the claims loop or any
  artifact schema. Nothing about what is accepted or refused changes.
* Making a refusal visible to the OPPONENT over the wire. Their client already
  receives `{"status": "refused", "reason": ...}` in the body; that it returns
  under HTTP 200 is conformant, and inventing a non-200 status here would be a
  unilateral protocol change mid-league. What we can fix is our own blindness
  and our ability to tell them precisely what we refused.
* Retrying or repairing a refused message. A refusal is a real disagreement
  and papering over it is how a desync becomes an artifact.

## Acceptance

* A malformed inbound turn produces a log record naming the failing field, and
  the inbox is still not written to.
* A well-formed turn produces no refusal log and is stored, exactly as now.
* A sub-game stuck waiting on the opponent prints one line per re-push naming
  the step, the attempt count and the inbox contents.
* The full suite is green and the README's self-checked figures move with the
  tree.
