# PLAN 21 — Appendix F compliance, wire relaxation, series tie

Implements PRD 21 in its three parts, in that order. Every new module stays
under the 150-line ceiling.

## Modules

```
src/engine/appendix_f.py          ~95   the mandated table + a checker
src/mcp_server/wire_vocab.py      ~85   sender / result_claim / terminal words
```

Parts 2 and 3 otherwise EDIT existing modules rather than adding new ones:

```
src/mcp_server/wire_v3_session.py   two rules relaxed (currently 82 lines)
src/reporting/settlement.py         tie award in _aggregate (currently 150)
src/reporting/official_scope.py     tie award in _aggregate (currently 145)
```

`settlement.py` is AT 150 and `official_scope.py` at 145. The award is a
three-line addition to each; if either crosses, the aggregate helper moves to a
shared module rather than the ceiling being bent. Checked in T3.5.

## Part 1 — `engine/appendix_f.py`

```python
FIXED:  dict[tuple[str, str], object]   # 13 קבוע, exact equality
FLOORS: dict[tuple[str, str], float]    #  9 מינימום, >= only
check(config: dict) -> list[str]        # one message per violation, empty = ok
```

Keyed `(section, field)` so a value is declared once (FR1.1). The docstring
carries the provenance: transcribed by SMNGRP05 from the PDF we do not have,
with printed page numbers.

`check` returns messages, not booleans, so a failure names field, our value,
required value and status (FR1.3).

The test walks **every** `config/**/game.json` the repo ships (FR1.2), not a
fixed list, so a config added later is covered without editing the test.

## Part 2 — `mcp_server/wire_vocab.py`

```python
sender_ok(value) -> bool          # role OR group id; empty/non-str refused
outcome_of(claim) -> str | None   # str or {"outcome": ...} -> internal word
```

`TERMINAL = {"capture", "survival", "timeout"}` and
`ALIASES = {"escape": "survival"}`. An unknown word returns `None` and the
caller refuses — never guessed (FR2.3).

Comparison lowercases and strips (FR2.4). **Nothing here is ever applied to a
payload before hashing** (FR2.0): `canonical_str` and `reference_payload` keep
receiving bytes exactly as they arrived. A test asserts the boundary directly
by re-verifying a record whose `result_claim` needed normalising.

`wire_v3_session.py` then swaps two rules:

```
"sender":       _sender_ok            -> wire_vocab.sender_ok
"result_claim": isinstance(v, dict)   -> wire_vocab.outcome_of(v) is not None
```

`wire_v3.py`'s turn-level `sender` rule is left alone. Turn `sender` identifies
the seat within a live sub-game and is inside the hashed turn payload; only the
AUDIT-level sender is a filing identity.

## Part 3 — the tie award

One helper, applied by both aggregates:

```python
def award_series_tie(total: dict, tie_score: int) -> dict:
    """Equal cumulative points -> tie_score to each side (Appendix F Table 17)."""
```

Trigger is equality of cumulative points and nothing else (FR3.2). Applied
BEFORE `winner_group` is derived is wrong — equal totals plus an equal award
stay equal, so order does not change the winner; it is applied after, so the
awarded figure is what both the aggregate and the digest carry (FR3.4).

`tie_score` is read from `config["scoring"]["tie_score"]`, never inlined
(FR3.3).

## Tests, red first

`tests/unit/test_appendix_f.py`
* every shipped config passes — this is the regression guard the repo lacked
* a config with `min_games_to_pass: 1` fails, and the message names the field,
  both values and קבוע — the exact bug that survived ten days
* `max_barriers: 0` fails as below floor, not as merely different
* raising `max_barriers` to 20 PASSES — מינימום permits raising
* `pheromone_min_center_intensity` is absent from both tables (FR1.5)

`tests/unit/test_wire_vocab.py`
* `sender` accepts `"police"` and `"aviayeli"`; refuses `""`, `None`, `123`
* `result_claim` accepts `"survival"` and `{"outcome": "survival", "steps": 35}`
* `"escape"` maps to `"survival"`; `" Survival "` and `"survival"` agree
* an unknown word is refused, NOT guessed
* **the boundary**: a record whose claim needed normalising still re-hashes
  against its original bytes (FR2.0)

`tests/unit/test_series_tie.py`
* 45–45 becomes 47–47, `series_tie` true, `winner_group` null
* a 3–3 sub-game split at 60–30 gets **no** award — the corrected trigger
* a 4–2 split at 45–45 **does** get the award
* `tie_score` comes from config: change it to 5 and the award moves
* **regression**: the real ZeroOne0 artifacts still reproduce
  `c39d331c...` and `5077306a...` at 3997 bytes (FR3.5)
