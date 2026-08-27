# PRD 21 — Appendix F compliance, wire relaxation, and the series tie award

Three changes, sequenced by what each one prevents. They share a document
because they arose from one exchange with SMNGRP05 and one root cause: values
and vocabularies the book fixes, which nothing in this repo checked.

---

## Part 1 — Appendix F compliance (highest priority)

### Problem

`min_games_to_pass` read `1` in three config files. Appendix F Table 18 marks
it קבוע, and printed p.139 defines that status as
*"ערך מחייב שאינו ניתן לשינוי כלל. סטייה מן הערך הזה פוסלת את הקבוצה"* — a
binding value that cannot be changed at all; deviation **disqualifies the
group**.

It entered on 2026-08-17 inside an unrelated off-manifold refactor and survived
ten days and two graded series. The value is fixed now. The reason nobody knew
is not.

This repository mechanically enforces a 150-line ceiling, a documented test
count and a tracked-file count — and has **no check whatsoever** on the values
the book marks permanent. That asymmetry is the actual defect.

### Provenance, stated because we cannot verify it ourselves

`police_thief_p2p.pdf` Appendix F is **not in this repository**; two modules
already carry that caveat. Every value below is transcribed from SMNGRP05, who
have the PDF, with printed page numbers. It is adopted on their transcription,
not on our reading. That is recorded in the module docstring so the next reader
knows the provenance.

### Requirements

**FR1.1** — One table holds the thirteen קבוע values and the nine מינימום
floors. Values are declared once, never inlined at a call site: the project
constitution forbids inlined tunables, and a compliance table repeated per
call site is that same defect.

**FR1.2** — The check runs against **every** config the repo ships, not the one
that happens to be loaded. Our deviation existed in three files.

**FR1.3** — A failure names the field, our value, the required value and the
status (קבוע vs מינימום). "Config invalid" is not a useful failure.

**FR1.4** — קבוע is exact equality. מינימום is `>= floor`; raising is legal,
lowering is not. A `0` where a floor exists must fail — SMNGRP05 lost 240
matches' work to a `max_barriers = 0` that looked like a clean symmetric
experiment and was forbidden.

**FR1.5** — `pheromone_min_center_intensity` is **not** in Appendix F (Table 16
has three rows). It is recorded as negotiated, not mandated, and is not
checked.

---

## Part 2 — Wire relaxation for SMNGRP05

### Problem

Two validators reject SMNGRP05's shapes outright:

```
wire_v3_session.py:62   "sender": required 'police' | 'thief'
wire_v3_session.py:64   "result_claim": required object
```

They send `sender` as the group id and `result_claim` as a bare string. Their
constraint is real and better argued than ours: their `AuditPayload` is a
frozen dataclass and `result_claim` is compared downstream against the strings
`"capture" / "survival" / "timeout"`. A dict arriving there does not raise — it
compares unequal and **silently mis-scores** the sub-game. A loud rejection is
recoverable; a silent mis-score is not.

Separately, opponents name the same terminal event differently. ZeroOne0's
"escape" is our "survival"; both `result_claim`s agreed on every sub-game of a
completed series while using different words.

### THE SAFETY BOUNDARY — the load-bearing requirement

**FR2.0** — Relaxation applies to **validation and interpretation only**. It
must never touch bytes that are hashed or re-hashed.

Commit preimages are built by `interop.canonical_str(payload)` and
`crypto.reference_payload`. Normalising a payload before hashing it changes the
digest and breaks verification against every record already sealed — 206
opponent records and 200 of our own, on a series already settled and reported.

A record is verified against the bytes as received, always. Vocabulary and
whitespace handling live at the semantic layer, above the hash.

### Requirements

**FR2.1** — `sender` accepts a role (`police`/`thief`) **or** a group id.
Neither spelling is privileged. Empty and non-string remain refused: silence
was never acceptance and neither is a blank.

**FR2.2** — `result_claim` accepts a bare string **or** an object. When an
object, the outcome is read from its `outcome` key.

**FR2.3** — Terminal vocabulary maps to one internal set. `escape` → `survival`
is the known case. Mapping is explicit and table-driven; an unknown word is
**refused, never guessed**. Guessing at an outcome is how a sub-game gets
mis-scored quietly, which is the exact failure Part 2 exists to avoid.

**FR2.4** — Comparison ignores surrounding whitespace and case. `" Survival "`
and `"survival"` are the same claim. This is normalisation for comparison, not
rewriting of stored data.

**FR2.5** — We continue to SEND exactly `{sender, records, result_claim}` and
nothing else. SMNGRP05 build their payload with `AuditPayload(**data)`, so a
fourth key raises `TypeError` and destroys the sub-game at the audit.

---

## Part 3 — The series tie award

### Problem

`tie_score` is loaded from config and used in the learning reward table. It is
**never applied to a series total**. Our aggregate sets `series_tie: true` when
totals are level and stops there.

A level series would have us filing 45–45 while the opponent files 47–47 — two
groups filing different numbers for one scored match. SMNGRP05 report that both
their last two series ended exactly level, so the branch is live, not
hypothetical.

### THE TRIGGER — corrected before implementation

The award triggers on **cumulative points being equal**, and on nothing else.

Book: *"ניקוד לכל צד כאשר הניקוד המצטבר של כל המשחקונים מול יריבה מסתיים
בתיקו"* — points to each side when the cumulative score of all sub-games ends
in a tie. SMNGRP05 place it at series level in three independent citations.

**A 3–3 split of sub-games won is NOT the trigger.** Three wins as cop at 20
each against three as thief at 10 each is 60–30 — a decisive series with an
even sub-game count. Keying the award on 3–3 would award tie points to a series
that has a clear winner, and would miss a genuine 45–45 tie that fell 4–2.

### Requirements

**FR3.1** — When `total_score` is equal across both groups, each group receives
`tie_score` **added to** its total. `series_tie` stays `true` and
`winner_group` stays `null`.

**FR3.2** — The trigger is equality of cumulative points. Sub-games won, ties
count and role distribution do not enter it.

**FR3.3** — `tie_score` is read from the agreed config. Appendix F marks it
קבוע at 2, so there is exactly one correct value — but it is still read, never
inlined, per the constitution and FR1.1.

**FR3.4** — The award enters the settlement scope, so both teams' digests
reflect the awarded totals. A tie awarded on one side only produces two digests
for one series — the failure the whole settlement mechanism exists to prevent.

**FR3.5** — The historical `c39d331c...` and official `5077306a...` digests
must still reproduce byte-identically. Neither of our completed series was
level, so no awarded row exists in either; this is a regression guard, not a
migration.

---

## Non-goals

* Replaying or amending any completed series.
* Editing filed artifacts or the published evidence bundle. The
  `min_games_to_pass` deviation inside them is **disclosed, not rewritten**.
* Sending any email.
* Changing what we put on the wire beyond Part 2's three keys.
