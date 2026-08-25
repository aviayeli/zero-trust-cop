# TODO 11 — Getting a graded league series played, and reported

Derived from `PLAN_11_League_Match_Ops.md`. Nothing here is executed until it
appears above.

## 11.1 Tests first (must fail before any implementation)

- [x] `tests/scripts/test_netcheck.py` — the seven cases in PLAN §7.
      Driven with a fake `call`; no socket is opened by any of them.
- [x] `tests/scripts/test_reference_dispatch.py` — the seven cases in PLAN §7.
- [x] Confirmed both files FAILED for the right reason (`ModuleNotFoundError`,
      `AttributeError`), not for a typo in the test.

## 11.2 The probe

- [x] `src/scripts/netcheck.py` — the check kernel, 150 lines exactly.
- [x] `src/scripts/netcheck_cli.py` — session, arguments, rendering, 111
      lines. The split was forced by the limit, not planned; `netcheck.main`
      re-exports it so `python -m scripts.netcheck` is still the name typed.
- [x] Four checks in dependency order; a failed check stops the ones after it.
- [x] `sub_game_number = 0` — outside the 1-indexed schedule either side
      plays, so the probe cannot collide with a real sub-game.
- [x] Acceptance judged by `negotiate_reply._require_acceptance`, so all
      three live spellings of yes are read.
- [x] Terms compared by `negotiate_reply._first_difference`, so "the terms
      disagree" has exactly one definition in this repo.
- [x] A bare acceptance with no terms reports `terms UNVERIFIED` and exits
      non-zero: never assert a check that did not run.
- [x] Session built in `netcheck_cli.session_peer` on the same transport,
      watchdog and agreed throttle a real series uses. NOT
      `reference_dial.opponent`: that yields only `call`, and the surface
      check needs `list_tools`, which is a session method.
- [x] Non-zero exit on any failure (FR7).

## 11.3 The dispatch tail

- [x] `report_by_email` grows an optional `mode=None`; absent it,
      `load_email_settings` still decides. Both existing callers unchanged.
- [x] `reference_cli` grows `--email-mode {auto,draft,send}`, default None.
- [x] The tail runs only when `write_artifacts` is true.
- [x] The tail is wrapped so a reporting failure cannot discard six played
      sub-games; it prints `email_report=FAILED` and returns the summaries.

## 11.4 Exposure

- [x] `scripts/league_up.sh` — one ngrok agent, two tunnels, ports read from
      `config/<role>/game.toml` at run time. No port literal in the script.
- [x] It prints both public HTTPS URLs and the two follow-up commands
      (`setup_league_match --public-url`, and the URL to send the opponent).

## 11.5 Documentation and the self-checked figures

- [x] README gains §6 step 4b, the league runbook (expose → netcheck → play),
      and §8 records that the reference-v3 entry point now reports too.
- [x] Staged the new files, then re-derived the figures: 1419 tests, 311
      tracked Python files, longest 150 lines.
- [x] Full suite green: 1418 passed, 1 skipped, 0 line-limit violations.

## 11.6 Deliberately NOT done

- [ ] ~~Set `network.opponent_url` in `config/<role>/game.toml` for the
      league match.~~ The reference-v3 path takes the opponent's endpoint
      from `--opponent-url` (`reference_run.py:53`); `opponent_url` feeds
      `transport.py` for loopback and the native dialect only. Editing it for
      a league match changes nothing and creates a second, stale place to
      look for the opponent's address.
- [ ] ~~Install the opponent's Ed25519 public key.~~ reference-v3
      authenticates terms with `SHA256(canonical_json(terms)|nonce)`
      (`reference_negotiate.py:70`), not with peer keys.
      `setup_league_match --opponent-key` serves the native dialect.
- [ ] ~~Change the shipped `[email] mode`.~~ It stays `auto` so a missing
      credential can never break CI; the graded run passes
      `--email-mode send` instead.

## 11.7 Found while verifying, NOT fixed by this phase

- [ ] **`scripts.replay_match` cannot verify a reference-v3 log.** Run against
      `logs/opponent-2-ZeroOne0/log_ZeroOne0-vs-aviayeli_g01.json` it prints
      `TAMPERED!` and exits 1, once per turn: `no submissions block`. That is
      not a tamper finding, it is a dialect mismatch — the verifier reads the
      NATIVE dialect's per-turn `submissions` (commit, reveal, signature), and
      a reference-v3 turn carries `{step, ours, theirs}` because the move stays
      sealed until `submit_audit`.

      The reference-v3 evidence is elsewhere and is real: each sub-game log
      carries `their_audit_response` — the opponent's own re-hash of our
      disclosed chain — and the result carries `mutual_agreement.consensus`
      with the settlement `sha256` both teams must reach independently.

      So a graded reference-v3 series has cross-team evidence but no OFFLINE
      re-verifier, and the one command a grader would reach for reports a
      forgery that did not happen. A `--wire reference-v3` mode for
      `replay_match`, re-running `audit_check.verify_records` over the
      disclosed chain, is the fix. It is a phase of its own (PRD_12) and is
      deliberately not smuggled into this one.

## 11.8 bb-ai-12 pre-match findings (2026-08-25)

Recorded here because the reply to bb-ai-12 quotes these numbers and a claim
made to another team should be reproducible from this repo.

- [x] **They run `multiplicative_book_v1`; we run `subtractive_chebyshev_v1`.**
      Harmless, and for a sharper reason than "not one of the 14 terms":
      `smell_grid` is absent from `turn_message.sealed_payload`
      (`{step, state, position, move, intent, hint}`), so it is never hashed
      and never re-hashed at `submit_audit`. A decay disagreement cannot
      produce a false tamper verdict.
- [x] **The argmax is unaffected — 0 disagreements over 7,000 half-turns**
      (200 random walks x 35 steps, 35% stall rate to age the trail).
      Structural, not luck: both forms merge by MAX and re-emit at the current
      cell, so that cell holds the post-decay centre (0.80 subtractive / 0.81
      multiplicative) and no aged cell can exceed it. `claims_runner.py:62` is
      our only consumer of their grid and reads only `strongest_cell`.
- [x] **Multiplicative discloses far more.** ~36 of 49 cells lit at sub-game
      end against our ~19. The asymmetry favours us, so it was disclosed to
      them rather than banked.
- [x] **Multiplicative never clears, at the kit's 3-place rounding.**
      `round(0.005 * 0.9, 3) == 0.005` is a fixed point; 25 cells were still
      lit after 200 decay steps. Subtractive clears completely in 8. Reported
      to them as a probable unintended bug on their side.
- [x] **Their endpoint was down at negotiation time.** Six probes of
      `https://comic-leverage-paprika.ngrok-free.dev/mcp` over 52 seconds all
      returned HTTP 502: tunnel up, nothing listening behind it. `netcheck`
      stopped at `reachable` and ran no later check, which is the intended
      ordering.

Reproduce the decay comparison by subclassing `SmellTrail` and overriding
`decay` to scale by `1 - pheromone_decay` instead of subtracting it; everything
else is the shipped class.

- [ ] **Open, needs bb-ai-12:** who plays which side in sub-game 1 (a mutual
      `role` assumption is refused at `negotiate`; an inverted one is played
      through coherently by both engines), their exact team-code string, and a
      re-send of one corrupted line describing their endpoint topology.

## 11.9 The window that was not a window (2026-08-25, live)

- [x] **`--wait-minutes 45` gave up after 183 seconds and said nothing.**
      183s is exactly one `lazy_opponents` budget (36 x `_REOPEN_WAIT_SEC`),
      so the OUTER retry in `connect_and_play` never fired once.
      Root cause: `streamable_http_client` hosts its session in an anyio task
      group; when the session fails, anyio cancels that scope and on asyncio
      the cancellation is delivered to OUR task at its next await -- which was
      `await sleep(interval)` in the retry itself. It re-raised, and the run
      unwound.
- [x] **Intermittent, which is why it survived the phase that introduced it.**
      One relaunch died at 183s and the next was still up at 453s under the
      same conditions; whether anyio leaves a cancellation pending depends on
      how the failure unwinds. Every existing test of `connect_and_play`
      injects a fake `sleep` that cannot raise, so none of them could see it.
- [x] Fixed in `reference_launch._wait_out`, covered by
      `tests/scripts/test_connect_and_play_cancel.py`. `Task.uncancel()` alone
      is NOT enough on 3.12: it decrements the counter and leaves
      `_must_cancel` set, so the next await raises regardless. Delivery clears
      the flag, so the cancellation is caught, counted down, and the wait
      retried once. A CancelledError with no request behind it is re-raised.

## 11.10 The structural blocker this exposed, NOT fixed here

- [ ] **Our loop cannot read an inbox until it has dialled the opponent.**
      `play_series` asks `call_for(role)` before the turn loop, and that goes
      through `lazy_opponents._open`. Against bb-ai-12 on 2026-08-25 their
      thief negotiated with our cop and pushed SEVEN turns into our inbox
      while our runner was still retrying their 502 endpoint, so not one of
      them was ever read. From their side it looked exactly like a peer that
      accepted the turns and went silent.

      This is the ali-ahm1 failure from `run_reference_match.py:7-11` in the
      opposite direction: there, their loop would not read our turns until a
      handshake completed; here, OUR loop will not read theirs until we can
      reach them. A peer that can be reached but cannot reach back plays no
      turns and produces no diagnostic.

      Worth considering: serve-and-read before the dial succeeds, or at least
      report inbox depth while retrying, so "they are pushing to us and we
      cannot see it" stops being invisible. Needs its own PRD.

## 11.11 What the bb-ai-12 timing data actually showed (2026-08-25)

Two of my diagnoses were wrong and their independently-captured timestamps
disproved both. Recorded because the reasoning error is the reusable lesson.

- [x] **"We never sent a turn" was wrong.** It rested on our runner printing
      zero `step N pushed` lines. `progress` fires at
      `claims_match_loop.py:81`, AFTER `await_turn` returns THEIR reply -- so
      zero lines means zero completed ROUND TRIPS and says nothing about what
      we sent. Read the callsite before inferring from its absence.
- [x] **"Those were our 5s session-open retries" was wrong.** Measured
      properly by pointing the client at a logging 502 endpoint: our open
      retry is a single POST every 5.0s, uniform, no GET, no 202
      (`[5,5,5,5,5,5,5,5,6,5,5,5,5,5]`). Their log had a GET, a 202 and ~10.5s
      gaps. I had derived 5.0s by READING `_REOPEN_WAIT_SEC` and predicted a
      cadence for a path that was not in play.
- [x] **What their data does match: the REPUSH.** `await_turn(repush_every=20)`
      x `poll_interval_sec=0.5` = exactly 10.0s. Their gaps were
      `[0,0,1,1,10,11,10,10,11]`: session open (3 requests), negotiate, one
      turn at step 1, then five re-pushes of that same sealed turn. Their
      reported "7 turns" and "9 turns" were one turn re-sent 7 and 9 times.
      Neither attempt ever advanced past step 1.

- [ ] **Open: a refusal is invisible to the opponent at the HTTP layer.**
      `reference_tools.receive_turn` returns HTTP 200 carrying
      `{"status": "refused", "reason": ...}` and does NOT append to the inbox.
      An opponent watching status codes sees an unbroken run of 200s while
      every message is being dropped -- which is exactly what bb-ai-12
      reported as "turns exchange cleanly". Our own `negotiate` docstring
      already warns that a peer reading only one field "must not read a
      refusal as silence"; the same trap exists here in the other direction
      and nothing surfaces it. Worth considering: log inbound refusals
      server-side, and report inbox depth while `await_turn` is re-pushing, so
      "we are re-sending step 1 for the ninth time" is visible rather than
      silent. Needs its own PRD.
