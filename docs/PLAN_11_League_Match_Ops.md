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

---

# PLAN 11b — Migrating from split ports to one endpoint

Derived from `PRD_11_League_Match_Ops.md` §11b. Approved shape before any code.

## 1. The routing key is ours, not theirs

This is the whole design, and it is settled by two facts in the code rather
than by preference:

```
receive_turn    sender REQUIRED  (wire_v3.TURN_REQUIRED)
submit_audit    sender REQUIRED  (wire_v3_session.AUDIT_REQUIRED)
receive_control sender REQUIRED  (wire_v3_session.CONTROL_REQUIRED)
negotiate       role   OPTIONAL  (wire_v3_session.NEGOTIATE_OPTIONAL)  <-- !
```

`negotiate` is the message that OPENS a sub-game and the one that may carry no
role. So dispatch cannot key on what the opponent claims.

And it must not, even where it could. `pairing.pairing_refusal` refuses when
`their_role == our_role`; derive ours from theirs and that comparison is
tautological forever. That check is described in its own docstring as the only
place a mispairing can be caught, and a mispairing is otherwise played through
coherently by both engines for thirty-five steps.

So the unified server holds an **active role** of its own. `claims_runner`
already walks `role_schedule(sub_games, first_role)` and knows, per sub-game,
which side we are playing. It sets it; the server obeys it; the opponent's
claim is only ever *checked* against it.

## 2. Composition, not rewrite

`create_app(role)` binds a role into nine things — `own_role`, `gate`,
`policy`, `episode`, `match_state`, the public keys, the identity block, the
inbox, and `our_role` inside `negotiate`. Rewriting that to be role-agnostic
would touch every one of them and put the native dialect at risk for no
league benefit.

Instead the unified app **composes the two peers it already builds**:

```
create_unified_app(config_root)
├── peers = {role: create_app(role) for role in PEER_ROLES}   # unchanged
│      each keeps its own inbox, audits, identity, terms, our_role
├── mcp = FastMCP(port=unified_port)                          # ONE listener
└── four dispatching tools -> peers[active].<tool>
```

`create_app` builds a `FastMCP` but does not bind until it is run, so the two
inner apps cost nothing but their own state. Nothing in `server.py`,
`dialects.py`, `reference_surface.py` or `reference_tools.py` changes at all —
which is what keeps the split-port path (FR5) provably intact: it is the same
code, reached the same way.

The runner needs no change either. It is handed `peers`, the same
`{role: app}` mapping it takes today, and polls `app.inbox` as it always has.

## 3. The self-dial refusal (FR4)

On two ports a message from our own side could not arrive: our cop's port was
not our thief's. On one port it can, and it is exactly the shape a self-dial
takes — `--opponent-url` pointed at our own tunnel. `await_turn` already
raises on our own turn appearing in our own inbox; the unified surface refuses
it one layer earlier, at the tool, so it never reaches the inbox at all.

## 4. Modules

| module | holds | budget |
| --- | --- | --- |
| `src/mcp_server/unified.py` | `create_unified_app`, the four dispatchers, the active-role holder | ≤150 |
| `config/<role>/game.toml` | `unified_port` in `[network]` (FR6) | +1 line each |
| `scripts/ngrok_unified.yml` | one tunnel, one authtoken | new |
| `scripts/league_up.sh` | `--unified` mode | +~25 |

No change to `server.py`, `dialects.py`, `reference_surface.py`,
`reference_tools.py`, `claims_runner.py` or `claims_match_loop.py`.

## 5. Test plan (written first)

`tests/scripts/test_unified_endpoint.py`:

1. one app serves all four reference-v3 tools on one port
2. a turn arrives while we play police -> lands in the POLICE inbox
3. the sides swap -> the same tool now lands it in the THIEF inbox
4. a turn whose `sender` is our own active role is REFUSED, not stored (FR4)
5. `negotiate` with no `role` at all is still answered (it is optional)
6. `negotiate` declaring the role WE are playing is still refused (FR3)
7. the unified port comes from config, not from a literal (FR6)
8. the two-port `create_app` path is untouched — same tools, same inboxes (FR5)

(6) is the one to get right. It is the check the obvious design would have
silently destroyed.

## 6. Migration, and what stays

Split ports remain the default and the shipped topology. Unified is opt-in
until a graded series has been played on it, because the path that has
actually carried a match is evidence and the new one is not yet.

Order: docs -> tests -> `unified.py` -> config -> ngrok -> `league_up.sh` ->
figures -> suite green.
