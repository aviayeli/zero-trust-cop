# PRD 11 — Getting a graded league series played, and reported

## Problem

Phase 10 made us able to PLAY a reference-v3 series. It did not make us able
to run one as an *operation* against a classmate we have never dialled, and
two of the gaps only surface at the moment they cost the whole series.

Three defects, in order of what they cost:

1. **A finished graded series sends no email.** `scripts.match_report.
   report_by_email` exists and is correct, and exactly two callers use it:
   `run_local_mcp_match.py:143` and `run_remote_mcp_match.py:116`. Neither is
   the league entry point. `reference_cli.main()` writes the four artifacts,
   prints their paths and returns — so the one run that is actually graded is
   the one run that reports nothing. The rulebook's §9.3 obligation is
   discharged by hand or not at all, and "not at all" is indistinguishable
   from success at the console.

2. **`mode = "auto"` cannot fail loudly, and the token expires weekly.** On a
   dead OAuth token `send_game_report` writes `logs/email_draft_<uid>.txt`
   and returns True. That is the right default for CI and for local
   simulation — a missing credential must never break the suite — and the
   wrong one for a graded submission, where the operator needs to learn at
   the console that Dr. Segal did not receive the report. The shipped config
   must keep drafting; the graded run must be able to demand delivery.

3. **Nothing verifies the opponent's endpoint before the series starts.**
   `connect_and_play` retries a failing `open_session` for the whole
   `--wait-minutes` window, which is correct behaviour and a terrible
   diagnostic: a typo in their URL, a tunnel that is down, and a peer that is
   up but serving a different dialect are three different problems that all
   present as the same silence for thirty minutes. On 2026-08-24 three
   attempts against ali-ahm1 were lost to timing alone. An operator needs to
   distinguish "their tunnel is not there" from "their tunnel is there and
   their terms disagree with ours" *before* committing a series to it.

A fourth item is documentation rather than defect: the exposure step (two
ngrok tunnels, one per peer port) is described in the README as prose and has
never been reduced to something runnable, so it is re-derived by hand under
time pressure at the start of every match.

## Requirements

* **FR1** — The reference-v3 entry point reports the series by email after
  the artifacts are written, using the same `[email]` block every other
  entry point reads. Reporting runs only when artifacts were written: a
  `--no-artifacts` rehearsal has no result file to report.
* **FR2** — Reporting must never fail the series it is reporting on. A
  series that played to completion and then could not send is a series with
  its artifacts safely on disk and a non-zero diagnostic on stdout, not a
  traceback that discards the run.
* **FR3** — The email mode is overridable per run without editing config.
  Absent an override the configured mode is used unchanged, so the shipped
  `mode = "auto"` continues to govern CI and local play.
* **FR4** — A pre-game check reports, for a named opponent endpoint,
  whether it is reachable, whether it speaks MCP, whether it serves the
  reference-v3 tool surface, and whether its agreed terms value-equal ours.
* **FR5** — The terms comparison names the FIRST differing term and both
  values. "Terms mismatch" sends two teams diffing fourteen values that
  already agree; `num_games` disagreeing is the one this league has actually
  hit.
* **FR6** — The check is read-only. It must not open a sub-game, push a
  turn, or write an artifact — a diagnostic that half-starts a series is
  worse than no diagnostic.
* **FR7** — The check exits non-zero on any failure, so it can gate a
  launch script rather than only inform a human.
* **FR8** — Our own two peers are exposable as public HTTPS endpoints by
  running one command, with the ports read from the peers' own configs
  rather than repeated in a script.
* **FR9** — Every artifact of this phase honours the project constraints:
  no Python file over 150 lines, no tunable inlined in source, and a failing
  test before every implementation line.

## Out of scope

* Changing the wire, the handshake, the settlement or any artifact schema.
  This phase adds an operational tail and a diagnostic; it does not touch
  what a match *is*.
* Automating the exchange of endpoints with the opponent. The URL arrives
  over WhatsApp; the tooling takes it as an argument.
* Replacing `setup_league_match.py`. Its `--opponent-key` path serves the
  native dialect, which reference-v3 does not use (reference-v3 authenticates
  terms by `SHA256(canonical_json(terms)|nonce)`, not by Ed25519 peer keys),
  and its `--public-url` path still owns `config/declaration.json`.

## Acceptance

* A completed reference-v3 series prints an `email_report=` line naming the
  mode it used, and with a live token the result JSON reaches
  `rmisegal+uoh26finalgame@gmail.com` as an `application/json` attachment.
* `--email-mode send` on a broken token prints `email_report=FAILED` and
  still leaves all four artifacts on disk.
* `netcheck` against a dead URL, a live non-MCP URL, a live MCP peer with
  disagreeing terms, and a live conformant peer produces four distinguishable
  outcomes and three non-zero exits.
* The full suite is green and the README's self-checked figures move with
  the tree.
