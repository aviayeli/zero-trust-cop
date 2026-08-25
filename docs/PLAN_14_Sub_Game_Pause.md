# PLAN 14 — A window for an opponent who relaunches between sub-games

Derived from `PRD_14_Sub_Game_Pause.md`.

## 1. Where the wait goes, and why the order is load-bearing

```
for index, role in enumerate(schedule, start=1):
    app.inbox.clear()          # drop the previous sub-game's residue
    await pause(seconds)       # NEW, and only when index > 1
    reach = call_for(role)     # reopen the session they just restarted
    handshake = await negotiate(...)
```

**Clear, then pause.** Not the other way round. During the window their new
process comes up and may negotiate and push its step 1 immediately; if we
cleared *after* the pause we would delete exactly that turn, which is the
deadlock fixed this morning. Clearing first means the residue goes and
anything arriving during the window survives.

The stale-turn risk that the clear exists for is unaffected: a late turn from
their *old* process carries a high step number (they end at 35), and
`await_turn` matches on step, so it cannot satisfy the new sub-game's step 1.
It will show up in the stall diagnostic's `inbox_steps`, which is exactly
where an operator would want to see it.

## 2. Shape

`play_series` grows two keywords:

| name | default | why |
| --- | --- | --- |
| `pause_between` | `0` | seconds; zero is today's behaviour exactly (FR2) |
| `pause` | `asyncio.sleep` | injectable, so tests prove ordering without sleeping (FR6) |

`reference_cli` grows `--sub-game-pause` (default 0). `reference_run` passes a
`pause` that prints before sleeping, which satisfies FR5 without
`claims_runner` knowing anything about the console.

## 3. The line budget forces one extraction

`claims_runner.py` is at exactly 150. The pause cannot be added without
removing something, so the schedule-validation block — which is about
arguments, not about playing — moves to a module-level helper. That keeps the
loop readable and buys the room honestly rather than by deleting comments that
were paid for.

## 4. Test plan (written first)

`tests/scripts/test_sub_game_pause.py`:

1. with a pause, the wait happens once per boundary — n-1 times for n sub-games
2. it never happens before sub-game 1
3. it never happens after the last sub-game
4. the wait is the configured number of seconds
5. `pause_between=0` performs no wait at all (FR2)
6. the default is 0 — an existing caller is untouched
7. the inbox is cleared BEFORE the wait, not after (FR4) — the ordering test
8. `--sub-game-pause` parses, and defaults to 0

(7) is the one that matters: it is the property that keeps this from
re-introducing the deadlock it exists to work around.

## 5. Order of work

PRD -> PLAN -> TODO -> tests (failing) -> `claims_runner` -> `reference_cli`
-> `reference_run` -> figures -> suite green.
