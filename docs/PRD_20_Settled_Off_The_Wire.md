# PRD 20 — Confirming a settlement that was reached off the wire

## Problem

`mutual_agreement.confirmed` is written in exactly one place:

```
src/scripts/reference_artifacts.py:110
    "confirmed": all(_accepted(s.get("their_audit_response")) for s in summaries)
```

It is computed DURING a live match run, from the opponent's `submit_audit`
replies at the moment they arrive. `reporting/email_sender.py:87` refuses to
report unless that flag is literally `True`.

Against ZeroOne0 the series completed and was settled — but not on that path.
Their six `submit_audit` replies carried `["records","result_claim","sender"]`
and no verdict key, so `confirmed` computed to `false`. The agreement was then
reached afterwards, over `receive_control`, which our own server documents as
"a status channel touching no game state, never sealed, never scored". It
accepted their `result_agreement` and, correctly, changed nothing.

So we hold a series that is complete, cryptographically verified (206/206 of
their records, 200/200 of ours), and whose 3997-byte consensus scope both
teams derived independently to the identical digest
`5077306a3703467941ce7593bcf805a022c9f162588acc4f3feca97a045b0373` — and our
reporter refuses to report it, while the opponent's artifact for the same
series records `confirmed: true`.

Two teams, one series, contradicting artifacts. That contradiction is on the
record and is not in our favour.

The architecture assumed the only way to close a series is to play it. A
replay does not fix this: it produces a NEW series with a new result, not a
confirmation of the one already settled.

## What must not happen

This PRD exists because the obvious fix is the wrong one.

* **No manual override.** No flag, no env var, no `--force`, no CLI argument
  whose meaning is "set it to true".
* **No hand-edit** of a sealed artifact. Refused all through the ZeroOne0
  exchange and refused here.
* **Their word is not evidence.** An opponent asserting agreement, in any
  message on any channel, must not be sufficient. Silence was never
  acceptance; neither is assertion.

The existing posture must survive intact: a positive verdict, independently
checkable, or nothing.

## What the gate must require

`confirmed` may become true off the wire only when all of the following hold,
each machine-checked at the moment of writing:

1. **We derive the consensus scope ourselves**, from our own raw artifacts —
   the result, the six sub-game logs and the agreed config — recomputing
   scores from the config's scoring table rather than copying any value the
   opponent supplied.
2. **The digests match byte-identically.** Our independently derived SHA-256
   over the scope equals the digest the opponent published, and the UTF-8
   byte length matches too. A length mismatch localises a disagreement that a
   bare digest comparison only reports as "different".
3. **The series is internally sound**: every disclosed opponent record
   re-hashes to the digest they pushed, all six sub-games present.
4. **Provenance is recorded** in the artifact — the digest, the byte length,
   the scope serialization used, and that this was settled off the wire rather
   than at `submit_audit`. A reader must be able to tell the two apart.

If any check fails, `confirmed` stays false and the tool says which check
failed. Refusal is the default.

## Non-goals

* Re-playing the series. Out of scope and counterproductive (see Problem).
* Changing the historical `c39d331c...` digest, which stays preserved
  unchanged as the record of what the played series hashed to under our own
  settlement scope.
* Sending any email. Reporting stays a separate, explicitly authorised step.
* Making `receive_control` write state. It stays a status channel.

## Functional requirements

**FR1** — A module builds the official Appendix-F consensus scope from our own
persisted artifacts, deriving every field it can and taking only the
opponent's `github_commit` on disclosure, since another team's repository is
not verifiable by us.

**FR2** — The scope serializes as `json.dumps(scope, sort_keys=True,
ensure_ascii=False)` — default spaced separators, no trailing newline — the
form both teams agreed for settlement.

**FR3** — A verification entry point takes the opponent's claimed digest and
byte length, derives ours independently, and returns a pass/fail verdict
naming the first check that failed.

**FR4** — On a pass, and only then, the result artifact records
`confirmed: true` together with the provenance of FR4 above. On a failure the
artifact is left byte-identical to what it was.

**FR5** — The historical `mutual_agreement.sha256` is preserved. The official
off-the-wire settlement is recorded alongside it, not on top of it.
