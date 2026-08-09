# PLAN 07 — Submission Alignment

Implements [PRD_07](PRD_07_Submission_Alignment.md). Order matters: the rename
touches the files the later steps edit, so it goes first and lands whole.

## 1. Identity rename (FR1)

Pure substitution, no new code. `groupa` -> `aviayeli` and `ztc001` ->
`aviayeli` collapse to a single literal, so the artifact directory and the
artifact filenames finally agree.

| Where | What |
|---|---|
| `config/declaration.json` | `group_name` |
| `config/game.json`, `config/{police,thief}/game.json` | `agreed_between[0]` |
| `logs/groupa/*` | directory renamed; `game_uid`/`game_id`/`group_id` fields |
| `logs/email_draft_ztc001.txt`, `results/result_simulation.json` | uid |
| `scripts/simulate_email_delivery.py` | `GAME_UID` |
| tests, README | paths and expected identifiers |

The committed log is *replayed by test*, so the rename is only safe because
signatures cover `{role, turn, h_commit}` and commitments cover the revealed
tuple — neither includes the uid. `scripts.replay_match` re-verifying the
renamed log is the proof, and it runs in CI already.

## 2. Ports and tunnel validation (FR2)

Swap the two `[network]` blocks and `mcp_servers` in the declaration together;
they are pinned to each other by an existing test, so a half-swap fails loudly.

`public_url` validation is new behaviour and needs a home. `transport.py` is 39
lines and would stay under the limit, but URL parsing is a separate concern
from "read a TOML block", so it goes in `src/mcp_server/tunnel.py`:

```
parse_public_url(value: str) -> str      # "" | normalised absolute http(s) URL
```

Rules: empty is legal (loopback-only). Otherwise the scheme must be `http` or
`https` and a host must be present; surrounding whitespace and a trailing
slash are normalised away so `https://x.ngrok-free.app/` and
`https://x.ngrok-free.app` are the same endpoint. A bare host, a `tcp://`
tunnel, or a scheme-relative `//host` is rejected with `ValueError` — those are
the three shapes a tunnel dashboard actually hands you by mistake.

`load_network_settings` routes `public_url` through it, so a bad endpoint fails
at config load rather than at first contact.

## 3. Report attachment (FR3)

`email_sender.py` is 106 lines and building a multipart would push it past 150,
so message construction moves to `src/reporting/mime_report.py`:

```
build_message(result, recipient) -> MIMEMultipart
summary_text(message) -> str        # the body part only
attachment_json(message) -> str     # the decoded attachment payload
```

`email_sender` keeps the policy (agreement precondition, modes, drafts) and
imports construction. `message_text` becomes summary + decoded attachment
concatenated, which is what the draft writes — so the draft keeps carrying the
whole report even though the body no longer does.

Body text names the attachment and states the verdict; it must not contain the
serialised result, and a test asserts that directly rather than trusting review.

## 4. Decay documentation (FR4)

Comment and prose only: `pheromones.py` module docstring, `gui/live_heatmap.py`,
README §7. State the configured constants and the geometric consequence, with
the turn-10 residual spelled out so the "~10 steps" claim cannot quietly
reappear.

## 5. Gates

`pytest -q`, the 150-line audit over `git ls-files '*.py'`, then
`scripts/sync_repos.sh` (no `--push`) to rebuild and re-gate the thief branch.
Pushing stays a separate, explicitly requested step.
