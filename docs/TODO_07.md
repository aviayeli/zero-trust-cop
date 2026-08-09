# TODO 07 — Submission Alignment

Executes [PLAN_07](PLAN_07_Submission_Alignment.md). TDD throughout: each
behaviour item names the test that must fail first.

## 1. Identity rename (FR1)

- [ ] `config/declaration.json`: `group_name` -> `aviayeli`.
- [ ] `agreed_between[0]` -> `aviayeli` in the three `game.json` copies.
- [ ] `git mv logs/groupa logs/aviayeli`; rename the four artifacts; rewrite
      `game_uid` / `game_id` / `group_id` inside them.
- [ ] `results/result_simulation.json`, `logs/email_draft_*.txt`,
      `scripts/simulate_email_delivery.py::GAME_UID`.
- [ ] Test suites: the seven modules holding `logs/groupa/log_ztc001_g01.json`,
      plus the `group_id="groupa"` arguments in `test_match_log`,
      `test_game_uid`, `test_submission_artifacts`, `test_replay_verifier`.
- [ ] README paths and command examples.
- [ ] Gate: `scripts.replay_match logs/aviayeli/log_aviayeli_g01.json`
      still prints `Verified OK` — proves the rename left the crypto intact.

## 2. Ports and tunnel validation (FR2)

- [ ] Update `test_transport_settings::test_the_configured_ports_are_the_ruled_ones`
      to cop 8802 / thief 8801. Confirm it FAILS.
- [ ] Swap `[network]` in `config/police/game.toml` and `config/thief/game.toml`.
      Confirm it passes and `test_declaration_agrees_with_transport` now fails.
- [ ] Swap `mcp_servers` in `config/declaration.json`. Both pass.
- [ ] New `tests/mcp_server/secure/test_tunnel_urls.py`: empty is legal; ngrok
      and Localtonet http/https accepted; trailing slash and whitespace
      normalised; bare host, `tcp://`, `//host`, and no-host rejected. Confirm
      it fails (no module).
- [ ] Write `src/mcp_server/tunnel.py::parse_public_url`. Confirm it passes.
- [ ] Route `load_network_settings.public_url` through it; add a test that an
      invalid configured `public_url` raises at load.

## 3. Report attachment (FR3)

- [ ] New `tests/unit/test_email_attachment.py`: the message is
      `multipart/mixed`; exactly one `application/json` part; its filename is
      `result_<game_uid>.json`; its decoded payload round-trips to the result
      dict; the body part does NOT contain the serialised result. Confirm it
      fails.
- [ ] Write `src/reporting/mime_report.py`; re-export from `email_sender`.
- [ ] Update `test_email_sender::test_the_message_is_plain_text_...` — the
      contract it pins is now the opposite one.
- [ ] Keep `test_email_fallback::test_the_draft_contains_the_whole_report`
      green: `message_text` must return summary + attachment payload.
- [ ] Confirm `gmail_transport.gmail_send` needs no change (`as_bytes()` already
      serialises a multipart correctly).

## 4. Decay documentation (FR4)

- [ ] `src/strategy/pheromones.py` docstring: constants + geometric residual.
- [ ] `src/gui/live_heatmap.py` docstring, README §7 heatmap paragraph.
- [ ] No behaviour change; the pheromone tests must be untouched and green.

## 5. Gates

- [ ] `pytest -q` — every previously passing test still passes.
- [ ] Update README's self-checked figures (test total x2, tracked file count,
      longest-file line count); `test_readme_consistency` proves them.
- [ ] 150-line audit over `git ls-files '*.py'`.
- [ ] `scripts/sync_repos.sh` without `--push` — rebuild and re-gate the thief
      branch. Pushing both remotes is NOT part of this TODO.
