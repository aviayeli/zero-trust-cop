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
