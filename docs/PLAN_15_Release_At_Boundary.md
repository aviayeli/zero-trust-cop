# PLAN 15 — Do not hold the opponent's session across the pause

Derived from `PRD_15_Release_At_Boundary.md`.

## 1. Per-endpoint exit stacks

`lazy_opponents` enters every session into ONE shared `AsyncExitStack`, which
is why no single session can be closed: a stack unwinds in LIFO order and has
no notion of "close that one".

Each open gets its own stack instead, kept by URL:

```
stacks[url] = AsyncExitStack()
calls[url]  = await stacks[url].enter_async_context(opener(url, config))
```

The shared stack stays, and closes whatever is left at series end via a single
`push_async_callback`. So the teardown guarantee is unchanged; only the
granularity improves.

## 2. `release` rides on the callable (FR5)

`lazy_opponents` yields `reach`, an async `(role) -> call`. Three test modules
and `reference_run` depend on that shape, and none of them should have to
change for this.

Python functions carry attributes, so `reach.release` is the whole API:

```
async def reach(role): ...
reach.release = release
yield reach
```

Existing callers are untouched. The one new caller asks for `reach.release()`.

## 3. The pause does the releasing (no new parameter)

`play_series` already takes an injectable `pause`. It does not need to learn
about sessions; the caller that owns them can do both:

```
async def hold(seconds):
    await reach.release()          # drop their sessions FIRST
    print("  PAUSE ...")
    await asyncio.sleep(seconds)
```

That satisfies FR4 for free: with `pause_between = 0` the pause is never
called, so nothing is ever released and the path is byte-identical.

Order matters and is tested: release **before** the sleep. Releasing after
would hold the session across the window, which is the defect being fixed.

## 4. Releasing must not fail the series (FR3)

The far side is *expected* to be gone — that is what the window is for — so
closing will usually raise, and anyio will usually wrap it in a task group.
Every close is suppressed individually, with `BaseException` for the same
reason `connect_and_play` uses it, and every URL is dropped from both maps
whether or not its close was clean. A session we could not close politely is
still a session we must never reuse.

## 5. Modules

| module | change | budget |
| --- | --- | --- |
| `src/scripts/reference_dial.py` | per-URL stacks, `release`, attached to `reach` | 145 → ≤150 |
| `src/scripts/reference_run.py` | `hold` releases before sleeping | 150 → ≤150 |

`reference_dial` is tight; the room comes out of prose, not out of the
docstrings that record why the lazy open exists.

## 6. Test plan (written first)

`tests/scripts/test_release_at_boundary.py`:

1. `reach.release` exists and is awaitable
2. releasing closes the session that was opened
3. the next `reach(role)` opens a NEW session rather than reusing the closed one
4. releasing with nothing open is a no-op
5. a close that raises does not propagate — the series survives
6. …and the endpoint is still forgotten, so the failed-to-close session is
   never reused
7. release is idempotent

`tests/scripts/test_pause_releases.py`:

8. `reference_run`'s pause releases BEFORE it sleeps — the ordering that is
   the whole point
9. with `pause_between = 0` nothing is released at all (FR4)

## 7. Order of work

PRD → PLAN → TODO → tests (failing) → `reference_dial` → `reference_run` →
figures → suite green.
