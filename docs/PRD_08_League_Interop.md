# PRD 08 — League interop conformance

## Lifecycle note

This phase was directed as a standing mission rather than raised through the
`PRD → PLAN → TODO` order the project constitution requires. The requirement is
recorded here **after** implementation so the lifecycle is documented rather
than silently bypassed; that ordering is the deviation, and it is stated rather
than hidden.

## Problem

Every hash this project exchanges with an opposing group is re-computed by that
group. None of it can be validated by self-consistency: one implementation sits
on both sides of every local test, so signing and verifying with the same wrong
construction passes our whole suite and fails only in front of an opponent —
where the failure is scored as tampering and voids the sub-game for BOTH sides.

The class publishes a community interop kit
(`github.com/Imreec/copthief-league-protocol`) pinning exactly the
serialization details the book leaves to inter-team agreement, with shared
fixtures. Conformance against those fixtures is the only evidence available
before a real cross-group match.

## Findings this phase acts on

1. **`ensure_ascii` was defaulted to True.** Non-ASCII was escaped to
   `\uXXXX`. All fields we currently seal are ASCII, so nothing was broken in
   practice — but a free-language `hint` is Hebrew by design, and the escape
   would have surfaced as a false tamper verdict at audit.
2. **The commit construction was one of the book's three.** We emitted the
   Rulebook-5.3 positional concatenation; the kit pins the lecturer's reference
   form. §10.2 (undelimited digest) is closed as a side effect.
3. **`game_id` was our own group name.** Each side named the four artifacts
   after itself, so one match produced two sets of filenames and two reports
   that cannot be joined at all.
4. **`game_uid` was not derived.** It was the same local label, carrying no
   binding to the agreed terms.
5. **No settlement consensus existed.** `mutual_agreement.confirmed` asserted
   agreement with nothing an opponent could recompute.

## Requirements

* **FR1** — One canonical form: `sort_keys=True, ensure_ascii=False,
  separators=(",", ":")`, UTF-8.
* **FR2** — `commit = SHA256(canonical(payload) + "|" + nonce)`, a single pipe.
  Superseded encodings stay verifiable behind a keyword-only gate.
* **FR3** — `game_id = "-vs-".join(sorted(pair))`;
  `game_uid = UUID(SHA256(canonical(terms) + "|" + "|".join(sorted(pair)))[:16])`,
  derived from the EXTRACTED terms, never the whole `game.json`.
* **FR4** — Settlement consensus over the trimmed symmetric outcome, signed
  with the SPACED canonical form, sign-then-insert.
* **FR5** — Conformance proven against the kit's vendored CORE fixtures, not
  against our own re-implementation.

## Non-goals

* The kit's ENHANCEMENT vectors (opt-in mechanics not required by the book).
* Changing any agreed *value* in `config/game.json`. The spelling of
  `axis_origin_corner` (`"topleft"` here, `"top-left"` in the kit's example
  vectors) is a term whose value both peers must match exactly; it is flagged
  for cross-group confirmation, not silently rewritten.

## Acceptance

* Every previously passing test still passes; new behaviour arrives with tests
  written first.
* No `.py` over 150 lines; no new tunable inlined as a literal.
* README's self-checked figures remain accurate.
