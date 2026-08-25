# TODO 14 — A window for an opponent who relaunches between sub-games

Derived from `PLAN_14_Sub_Game_Pause.md`.

## 14.1 Tests first

- [ ] `tests/scripts/test_sub_game_pause.py` — the eight cases in PLAN §4
- [ ] Confirm they fail for the right reason

## 14.2 The change

- [ ] `play_series(..., pause_between=0, pause=asyncio.sleep)`
- [ ] The wait sits AFTER `app.inbox.clear()` and BEFORE `call_for` (FR4)
- [ ] Only for `index > 1`, never after the last (FR3)
- [ ] `pause_between=0` performs no wait at all (FR2)
- [ ] Extract the schedule validation to a helper to buy the lines honestly
- [ ] `reference_cli`: `--sub-game-pause`, default 0
- [ ] `reference_run`: a `pause` that announces before sleeping (FR5)

## 14.3 Gates

- [ ] Full suite green; figures re-derived; every file <= 150 lines

## 14.4 Deliberately NOT done

- [ ] ~~Pick the pause for them.~~ It depends on how fast their operator
      works. We take a number and tell them what it is.
- [ ] ~~Retry a refused handshake.~~ A pairing collision is a real
      disagreement about who plays which side; waiting longer does not fix it.
- [ ] ~~Relaunch our own peers per sub-game.~~ Ours are long-lived by design.
