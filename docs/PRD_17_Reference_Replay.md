# PRD 17 — An offline verifier for a reference-v3 log

## Problem

`scripts.replay_match` is the command this project points a marker at. The
README opens with it:

```
$ python -m scripts.replay_match logs/aviayeli/log_aviayeli_g01.json
Verified OK
```

Run it on the graded series we just submitted and it prints `TAMPERED!` and
exits 1, once per turn: `no submissions block`.

Nothing was tampered with. The verifier reads the NATIVE dialect, whose turns
carry a `submissions` block of commit, reveal and Ed25519 signature. A
reference-v3 turn carries `{step, ours, theirs}`, because on that wire the
move stays sealed until `submit_audit` and is never revealed per turn. Two
different record shapes, one verifier.

So a marker reaching for the obvious command gets a forgery verdict on a clean
series that both teams audited and whose settlement hash they independently
confirmed. That is the worst possible failure mode for an evidence-based
submission: the evidence is real and the tool that reads it says otherwise.

## What a reference-v3 log can actually prove

Our log holds our own sealed chain (`turns[].ours` = payload, nonce, commit)
and the digests they pushed (`turns[].theirs.commit`). It does **not** hold
their disclosed chain — that crosses the wire once, inside `submit_audit`, and
is judged live by `audit_check.verify_records` rather than stored.

So an honest offline verifier can establish:

* every one of our records re-hashes to its own commit under our serializer;
* steps are contiguous and ascending, with no gap a fabricated middle could
  hide in;
* every move we sealed was legal on the board the log itself records;
* the outcome we claim is consistent with the trajectory we sealed.

It cannot establish that their disclosed chain matched their pushed digests,
because that evidence is not in this file. A verifier that implied otherwise
would be worse than no verifier.

## Requirements

* **FR1** — `replay_match` recognises a reference-v3 log and verifies it
  rather than refusing it.
* **FR2** — The native path is untouched. A native log verifies exactly as it
  does today, byte for byte in its output.
* **FR3** — A tampered reference-v3 log is refused, naming the step and the
  check it failed. Re-hashing is the load-bearing one: rewriting a payload
  after the fact must not pass.
* **FR4** — The verdict states plainly what was **not** covered — their
  chain — so nobody reads `Verified OK` as more than it is.
* **FR5** — The exit code still gates: 0 verified, 1 refused.
* **FR6** — No file over 150 lines; a failing test before every line.

## Out of scope

* Storing their disclosed chain in the log so it becomes checkable offline.
  That changes an artifact schema after a graded submission used it, and the
  live `submit_audit` already judged that chain at the time.
* Re-verifying the settlement hash. Both teams confirmed it independently and
  it is recorded in the result.

## Acceptance

* The six graded logs verify, and say what they did not cover.
* A payload edited in a copy is refused, naming the step.
* Every existing native-dialect test passes unchanged.
