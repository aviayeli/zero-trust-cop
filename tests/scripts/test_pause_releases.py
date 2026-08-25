"""The pause must DROP their sessions before it waits (PRD_15 FR1, FR4).

This is the ordering that the whole phase exists for. Waiting while still
holding their session is what killed the first live run with a pause: we slept
ninety seconds holding a connection to a process whose entire job, during that
window, was to exit.

`reference_run` builds the `pause` that `play_series` calls, so the ordering
lives there and is asserted there.
"""

import inspect


def _hold_source():
    from scripts import reference_run

    return inspect.getsource(reference_run.run)


def test_the_pause_releases_before_it_sleeps():
    """Release first, sleep second. The reverse is the defect."""
    source = _hold_source()
    body = source[source.index("async def hold("):]
    release_at = body.index("release()")
    sleep_at = body.index("asyncio.sleep")

    assert release_at < sleep_at, (
        "the pause sleeps while still holding their session -- the window "
        "exists precisely so they can exit, and their exit kills it"
    )


def test_the_pause_is_what_carries_the_release():
    """No new parameter on play_series: the caller that owns the sessions
    does both, which is what keeps a zero pause byte-identical."""
    source = _hold_source()

    assert "pause=hold" in source
    assert "pause_between=args.sub_game_pause" in source


def test_a_zero_pause_never_releases_anything():
    """FR4. `play_series` only calls `pause` at a boundary when
    `pause_between` is truthy, so zero means the sessions are never dropped
    and the path is exactly today's."""
    from scripts.claims_runner import play_series

    source = inspect.getsource(play_series)

    assert "if index > 1 and pause_between:" in source


def test_release_is_awaited_not_merely_called():
    """A coroutine left unawaited would close nothing and warn at exit."""
    source = _hold_source()
    body = source[source.index("async def hold("):]

    assert "await reach.release()" in body or "await release()" in body


def test_reference_run_still_builds_one_pause_per_run():
    """Sanity: the helper is defined once, inside run(), where it can close
    over the session pool."""
    source = _hold_source()

    assert source.count("async def hold(") == 1
