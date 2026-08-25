# PLAN 11 — Getting a graded league series played, and reported

Derived from `PRD_11_League_Match_Ops.md`. Approved shape before any code.

## 1. What this phase does NOT touch

The wire, the handshake, the claims loop, the settlement, and all four
artifact schemas. Phase 10 settled what a match *is*; this phase adds the two
things that bracket one — a diagnostic before, a dispatch after — plus the
exposure step, which is shell rather than Python.

`MatchState`, `claims_runner`, `reference_run` and `reference_writer` are
read by this phase and edited by none of it.

## 2. The probe: what "read-only" actually permits

`netcheck` has to compare fourteen agreed terms with a peer, and the only
tool on the reference-v3 surface that carries terms is `negotiate` — the tool
that OPENS a sub-game. That looks like a contradiction and is not, because of
how the two sides number sub-games:

```
role_schedule(6, "police")  ->  sub-games 1 2 3 4 5 6      (1-INDEXED)
netcheck probe              ->  sub_game_number = 0        (outside the series)
```

Sub-game 0 exists in no schedule either side will play, so a handshake at 0
cannot collide with a real one, cannot be mistaken for sub-game 1, and leaves
the opponent's loop waiting for the same first turn it was already waiting
for. Our own `negotiate` is pure — it validates, compares, signs a reply and
returns, touching neither `inbox` nor `audits` (`reference_negotiate.py:52`)
— so a conformant peer's is at worst equally harmless.

The probe pushes no `receive_turn`, sends no `submit_audit`, and writes no
artifact. That is the whole of FR6.

## 3. The four checks, in dependency order

Each check runs only if the one before it passed, because a failure earlier
makes every later verdict meaningless — and reporting "terms disagree"
against a peer that is simply down is how an operator ends up editing a
correct `game.json`.

| # | check | passes when | names on failure |
| --- | --- | --- | --- |
| 1 | `reachable` | an MCP session opens and initializes | the transport error verbatim — their 502 is the finding |
| 2 | `surface` | `negotiate`, `receive_turn`, `submit_audit`, `receive_control` are all listed | which tools are missing |
| 3 | `handshake` | the reply says yes in any of the three live spellings | their `reason` |
| 4 | `terms` | their terms value-equal ours | the FIRST differing term, ours and theirs |

Check 3 accepts `status: "accepted"`, `accepted: true` and `ok: true` —
`negotiate_reply._require_acceptance` already knows all three, and a probe
that refused an unfamiliar word for yes would report a healthy peer as dead.
Check 4 reuses `negotiate_reply._first_difference` rather than restating the
comparison; one definition of "the terms disagree" is the point.

A bare acceptance carrying no `terms` is reported as `handshake ok, terms
UNVERIFIED` and is **not** a pass: asserting a comparison we could not run is
the failure mode the whole phase exists to prevent.

## 4. Modules

| module | holds | lines |
| --- | --- | --- |
| `src/scripts/netcheck.py` | the four checks, their ordering, the exit code | 150 |
| `src/scripts/netcheck_cli.py` | the session, the arguments, the rendering | 111 |
| `src/scripts/reference_cli.py` | `+ --email-mode`, `+` the dispatch tail | 105 → 129 |
| `src/scripts/match_report.py` | `report_by_email(..., mode=None)` | 34 → 42 |

The probe was planned as ONE module and is two: the checks alone came to 150
lines exactly, so the transport and the command line went next door — the same
seam `run_reference_match` / `reference_cli` already uses, and `netcheck.main`
re-exports so `python -m scripts.netcheck` stays the runnable name.

`netcheck_cli.session_peer` builds the session the way a real series does —
same streamable-HTTP client, same `watchdog_timeout_sec`, same agreed
`rate_limiter_gatekeeper` throttle. A probe on a different transport verifies
a path we will not use. It does NOT reuse `reference_dial.opponent`, which
yields only `HttpPeer.call`: the surface check needs `list_tools`, which is a
session method rather than a tool.

## 5. The dispatch tail

```
reference_cli.main()
    play the series                       (unchanged)
    write_series_artifacts()              (unchanged)
    report_by_email(paths["result"], ...) (NEW)
```

Three properties, each of them FR2 or FR3:

* It runs **only when artifacts were written**. `--no-artifacts` produces no
  result file, and reporting a path that does not exist would print a failure
  for a rehearsal that did nothing wrong.
* It **cannot fail the series**. The whole call sits under `except
  Exception`, prints `email_report=FAILED`, and returns the summaries. A
  series that played six sub-games and then hit a dead token must still
  return its summaries and leave its four artifacts on disk.
* The **mode is overridable, and defaults to the config**. `--email-mode`
  passes through to `report_by_email`; absent it, `load_email_settings` still
  decides, so the shipped `mode = "auto"` continues to govern CI, local
  simulation and every existing caller.

`report_by_email` grows one optional keyword. `run_local_mcp_match` and
`run_remote_mcp_match` call it unchanged and behave identically.

## 6. Exposure

`scripts/league_up.sh` + a generated ngrok config. The ports are **read from
`config/<role>/game.toml`** at run time via `tomllib`, never written into the
script: `my_port` is a tunable, the constitution keeps tunables out of
source, and a script with `8802` in it is a second place for the port to live
and drift.

The script generates the ngrok config into the scratch path it is given,
starts one agent with both tunnels (`ngrok start --all`), and prints the two
public URLs by reading the local agent API. One agent, two tunnels — which is
what the free tier permits, and what two separate `ngrok http` invocations
would violate.

## 7. Test plan (written first, all of it)

`tests/scripts/test_netcheck.py` — the probe is driven with a fake `call`, so
none of these opens a socket:

1. all four checks pass against a conformant fake → exit 0
2. an unreachable endpoint → `reachable` fails, later checks do NOT run
3. a peer missing `submit_audit` → `surface` names it, `handshake` does not run
4. a refusal → the peer's own `reason` is surfaced
5. terms differing on `num_games` → the report names `num_games`, `6`, and theirs
6. a bare `{"accepted": true}` → `terms UNVERIFIED`, exit non-zero
7. the probe uses `sub_game_number == 0` and calls no tool but `negotiate`

`tests/scripts/test_reference_dispatch.py`:

8. a completed series calls the reporter with the result path
9. `--no-artifacts` reports nothing
10. a reporter that raises does not lose the summaries
11. `--email-mode send` reaches `send_game_report` as `send`
12. no `--email-mode` leaves the configured mode in force

## 8. Order of work

PRD → PLAN → TODO → tests (failing, confirmed) → `netcheck` → dispatch tail →
shell → README figures → full suite green.

The README's self-checked figures (`tests/unit/test_readme_consistency.py`)
move last, because the test counts what exists once everything else does, and
the tracked-file count only agrees after the new files are staged.
