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
