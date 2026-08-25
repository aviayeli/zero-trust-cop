"""Honour the throttle both groups agreed to (audit T-1, fourth sitting).

`rate_limiter_gatekeeper` names five tunables — 30 requests/minute, 2
concurrent, 3 retries, 5-second backoff, a queue depth of 100 — and nothing in
`src/` read any of them. Our peer would call as fast as the event loop allows.

That is not merely impolite. If the opposing group DID implement the limiter,
we are the peer that gets dropped, and `HttpPeer` converts a dropped call into
`TechnicalLossError` — so ignoring an agreed throttle is a path to forfeiting.

Everything here is injected: the clock, the sleeper and the settings, so the
policy is tested without spending real seconds.
"""

import asyncio

import pytest

from mcp_server.rate_limiter import RateLimiter, ThrottleSettings


def _settings(**kwargs):
    base = {
        "requests_per_minute": 30, "concurrent_requests": 2,
        "retry_backoff_sec": 5, "max_retries": 3, "queue_depth": 100,
    }
    base.update(kwargs)
    return ThrottleSettings(**base)


class _Clock:
    """A monotonic clock that only moves when the sleeper advances it."""

    def __init__(self):
        self.now = 0.0
        self.slept = []

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def test_the_minimum_interval_comes_from_requests_per_minute():
    """30/minute is one call every two seconds, computed not hardcoded."""
    limiter = RateLimiter(_settings(requests_per_minute=30), clock=_Clock())

    assert limiter.min_interval_sec == pytest.approx(2.0)


def test_calls_are_spaced_to_respect_the_agreed_rate():
    clock = _Clock()
    limiter = RateLimiter(_settings(requests_per_minute=60), clock=clock, sleeper=clock.sleep)

    async def drive():
        for _ in range(3):
            await limiter.run(_ok)

    asyncio.run(drive())

    assert clock.slept == [pytest.approx(1.0), pytest.approx(1.0)]


async def _ok():
    return "sent"


def test_the_first_call_is_never_delayed():
    clock = _Clock()
    limiter = RateLimiter(_settings(), clock=clock, sleeper=clock.sleep)

    asyncio.run(limiter.run(_ok))

    assert clock.slept == []


def test_concurrency_is_capped_at_the_agreed_number():
    """A semaphore, sized from config — not a literal."""
    limiter = RateLimiter(_settings(concurrent_requests=2), clock=_Clock())

    assert limiter.concurrency == 2


def test_a_transient_failure_is_retried_with_the_configured_backoff():
    clock = _Clock()
    limiter = RateLimiter(
        _settings(max_retries=3, retry_backoff_sec=5, requests_per_minute=6000),
        clock=clock, sleeper=clock.sleep,
    )
    attempts = []

    async def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise ConnectionError("throttled")
        return "sent"

    assert asyncio.run(limiter.run(flaky)) == "sent"
    assert len(attempts) == 3
    assert clock.slept[-2:] == [pytest.approx(5.0), pytest.approx(10.0)]


def test_backoff_gives_up_after_max_retries_and_re_raises():
    """A permanently dead peer must still surface, not retry forever."""
    clock = _Clock()
    limiter = RateLimiter(
        _settings(max_retries=2, requests_per_minute=6000),
        clock=clock, sleeper=clock.sleep,
    )
    attempts = []

    async def dead():
        attempts.append(1)
        raise ConnectionError("gone")

    with pytest.raises(ConnectionError):
        asyncio.run(limiter.run(dead))

    assert len(attempts) == 3, "one initial attempt plus max_retries"


def test_a_technical_loss_is_never_retried():
    """The watchdog already ruled; retrying would relitigate a match outcome."""
    from mcp_server.http_peer import TechnicalLossError

    clock = _Clock()
    limiter = RateLimiter(_settings(), clock=clock, sleeper=clock.sleep)
    attempts = []

    async def expired():
        attempts.append(1)
        raise TechnicalLossError("peer did not answer")

    with pytest.raises(TechnicalLossError):
        asyncio.run(limiter.run(expired))

    assert len(attempts) == 1
