# PLAN 20 — Confirming a settlement reached off the wire

Implements PRD 20. Two new source modules, both well under the 150-line
ceiling, and no change to any existing write path.

## Seam

The split is between *deriving what the settlement says* and *deciding whether
to record it*. They are different jobs with different failure modes: the first
is pure computation over artifacts, the second touches a sealed file.

```
src/reporting/official_scope.py    ~110    build + serialize + digest
src/scripts/settle_official.py     ~120    verify, then record or refuse
```

`official_scope.py` sits in `reporting/` beside `settlement.py`, which already
owns the historical scope. Two scopes now exist and they are NOT the same
shape — `settlement.py` builds our own five-key rows under `cop`/`thief`,
PRD 20 builds the league's Appendix-F rows under `police`/`thief`. Keeping
them in separate modules stops one from being quietly edited into the other;
the historical `c39d331c...` must keep reproducing forever.

## `official_scope.py`

```python
build(result, config, logs, their_commit) -> dict
serialize(scope) -> str          # json.dumps(sort_keys, ensure_ascii=False)
digest(scope) -> tuple[str, int] # (sha256 hex, utf-8 byte length)
```

`build` derives, per sub-game:

| field | derived from |
|---|---|
| `result`, `sub_game_number` | our result artifact's `games` |
| `roles` | each log's `our_role`, mapped to `{group: role}` |
| `score` | recomputed from `config["scoring"]`, never copied |
| `winner_group`, `tie` | from the recomputed score |
| `started_at`, `ended_at` | min/max `timestamp` across the opponent's records in that log, converted to +03:00 |
| `audit` | `log_verified` / `tampered` from our own re-hash |
| `log_files` | our own filenames |
| `tokens` | zeros, on the accepted known-zero basis |
| `github_commit` | ours from the artifact; theirs passed in |

`their_commit` is a parameter, not a lookup, because another team's repository
is not verifiable by us. Making it an argument keeps that visible at every
call site rather than buried.

The aggregate is re-summed from the derived rows. Nothing the opponent sent is
read anywhere in this module.

## `settle_official.py`

```python
verify(scope, claimed_sha, claimed_len) -> str      # "" on pass, else reason
confirm(result_path, scope, sha, length) -> dict    # writes, or raises
```

Order of checks, each naming its own failure:

1. six sub-games present
2. every opponent record in every log re-hashes to its pushed digest
3. our derived byte length equals theirs
4. our derived sha256 equals theirs

Length is checked BEFORE the digest deliberately: a length mismatch says
*where* two scopes diverge, a digest mismatch only says *that* they do.

On a pass, `confirm` writes into the artifact:

```json
"mutual_agreement": {
  "sha256": "c39d331c...",           // preserved, untouched
  "confirmed": true,
  "official_settlement": {
    "sha256": "5077306a...",
    "byte_length": 3997,
    "serialization": "json.dumps(scope, sort_keys=True, ensure_ascii=False)",
    "method": "independent derivation from our own artifacts, digests compared",
    "channel": "off-the-wire (receive_control), not submit_audit"
  }
}
```

`channel` exists so a reader can always tell an off-the-wire settlement from
one earned live at `submit_audit`. On failure nothing is written and the
artifact stays byte-identical.

## Tests, red first

`tests/unit/test_official_scope.py`

* a known-answer test over the real ZeroOne0 artifacts: the derived scope is
  **3997 bytes** with sha256 **5077306a3703467941ce7593bcf805a022c9f162588acc4f3feca97a045b0373**. This is the load-bearing test — it pins agreement with a second, independent implementation.
* scores come from the config: mutating `config["scoring"]` moves the scope
* roles alternate per sub-game and are `police`/`thief`, never `cop`

`tests/scripts/test_settle_official.py`

* a wrong claimed digest refuses, and the artifact is byte-identical after
* a wrong claimed length refuses, and names length rather than digest
* a matching pair sets `confirmed: true` and records the provenance block
* the historical `sha256` survives the write unchanged
* there is no argument, flag or env var that sets `confirmed` without the
  digest comparison — asserted by inspecting the CLI's own parser

The last one is the PRD's "no manual override" requirement turned into a test,
so a future convenience flag fails the suite rather than passing review.
