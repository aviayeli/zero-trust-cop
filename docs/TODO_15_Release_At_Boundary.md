# TODO 15 — Do not hold the opponent's session across the pause

Derived from `PLAN_15_Release_At_Boundary.md`.

## 15.1 Tests first

- [ ] `tests/scripts/test_release_at_boundary.py` — cases 1-7 in PLAN §6
- [ ] `tests/scripts/test_pause_releases.py` — cases 8-9
- [ ] Confirm they fail for the right reason

## 15.2 The change

- [ ] Per-URL `AsyncExitStack` in `lazy_opponents`, so one session can close
- [ ] The shared stack still closes whatever remains at series end
- [ ] `release()` closes and FORGETS every open endpoint
- [ ] Every close suppressed individually (`BaseException`); the far side
      being gone is the normal case here, not an error
- [ ] `reach.release` attached to the yielded callable, so existing callers
      and their three test modules are untouched
- [ ] `reference_run`'s `hold` releases BEFORE sleeping

## 15.3 Gates

- [ ] Full suite green; figures re-derived; every file <= 150 lines
- [ ] `--sub-game-pause 0` path byte-identical: nothing released, no pause

## 15.4 Deliberately NOT done

- [ ] ~~Pick the pause length.~~ Bounded below by their process swap and
      above by their 60s handshake timeout. Both are theirs to measure; we
      take a number.
- [ ] ~~Retry a handshake they have already abandoned.~~ If they time out
      waiting for us the sub-game is lost, and the series restarts by the
      protocol both sides agreed.

## 15.5 The boundary was crossed (2026-08-25 20:06:56-20:12:59)

First complete series against a real opponent. Seven attempts died at the
sub-game boundary; this one did not.

```
  saved logs/aviayeli/log_aviayeli-vs-bb-ai-12_g01.json
  PAUSE 30s -- window for the opponent to relaunch (their sessions released)
  saved logs/aviayeli/log_aviayeli-vs-bb-ai-12_g02.json

sub_game=1 role=police steps=35 outcome=survival
  their_audit=accepted handshake=counter-signed
sub_game=2 role=thief  steps=35 outcome=capture
  their_audit=accepted handshake=counter-signed
email_report=ok mode=draft
```

- [x] **69 turns across two sub-games, both sides, both audits accepted, both
      handshakes counter-signed.** Zero pairing collisions, zero stalls.
- [x] All four artifacts written, and `mutual_agreement.confirmed: True` with
      a settlement `sha256` -- the cross-team consensus hash exercised for the
      first time outside a test.
- [x] The report was DRAFTED, not sent: `email_report=ok mode=draft`, and the
      draft names the course inbox without contacting it. Turning artifacts on
      for a friendly run cost nothing and proved the whole tail.
- [x] Copied to `logs/evidence/friendly_series/` before any re-run can
      overwrite `g01`/`g02`.

**Result: bb-ai-12 30, aviayeli 10.** They took both -- our cop failed to
capture in 35 turns, and their cop caught our thief. That is a real outcome
against a real opponent and it is worth reading as one: the boundary work is
done, the strategy work is not.

- [ ] **Still open, and now the visible gap:** `scripts.replay_match` exits 1
      on these logs (TODO_11 §11.7). A grader reaching for the obvious
      verifier gets `TAMPERED!` on a clean series, because the verifier reads
      the native dialect's per-turn `submissions` block and a reference-v3
      turn carries `{step, ours, theirs}`. The cross-team evidence is real and
      in the artifacts; the offline re-verifier for this wire is not written.
