"""Honour the throttle the shared contract agreed to.

``rate_limiter_gatekeeper`` in ``config/game.json`` names five tunables that
nothing read: 30 requests/minute, 2 concurrent, 3 retries, 5-second backoff,
queue depth 100. Ignoring an agreed throttle is not merely impolite — if the
opposing peer enforces it, WE are the side that gets dropped, and
``http_peer`` turns a dropped call into ``TechnicalLossError``. An unread
limit was therefore a path to forfeiting a match on manners.

The clock and the sleeper are injected so the policy is testable without
spending real seconds, and every figure comes from the contract rather than a
literal here.
"""

import asyncio
import time
from dataclasses import dataclass

from mcp_server.http_peer import TechnicalLossError

_SECONDS_PER_MINUTE = 60.0


@dataclass(frozen=True)
class ThrottleSettings:
    """The agreed gatekeeper block, as read from ``config/game.json``."""

    requests_per_minute: int
    concurrent_requests: int
    retry_backoff_sec: float
    max_retries: int
    queue_depth: int


def throttle_settings(config) -> ThrottleSettings:
    """Lift the agreed gatekeeper block off a loaded GameConfig."""
    return ThrottleSettings(
        requests_per_minute=config.requests_per_minute,
        concurrent_requests=config.concurrent_requests,
        retry_backoff_sec=config.retry_backoff_sec,
        max_retries=config.max_retries,
        queue_depth=config.queue_depth,
    )


def limiter_for(config, public_url: str):
    """The throttle to use for a peer, or None when there is nobody to protect.

    The agreed limit exists to keep us from overrunning the OPPOSING group's
    server. On loopback both peers are ours, and spending the interval to be
    polite to ourselves would add minutes to every local match. A configured
    ``public_url`` is what says a real opponent is on the other end.
    """
    if not public_url:
        return None
    return RateLimiter(throttle_settings(config))


class RateLimiter:
    """Space, cap and retry outbound peer calls per the agreed contract."""

    def __init__(self, settings: ThrottleSettings, clock=time.monotonic, sleeper=None):
        """``sleeper`` defaults to asyncio.sleep; injected for deterministic tests."""
        self._settings = settings
        self._clock = clock
        self._sleep = asyncio.sleep if sleeper is None else sleeper
        self._semaphore = asyncio.Semaphore(settings.concurrent_requests)
        self._last_started: float | None = None

    @property
    def min_interval_sec(self) -> float:
        """Seconds between call starts implied by ``requests_per_minute``."""
        if self._settings.requests_per_minute <= 0:
            return 0.0
        return _SECONDS_PER_MINUTE / self._settings.requests_per_minute

    @property
    def concurrency(self) -> int:
        return self._settings.concurrent_requests

    async def _space(self) -> None:
        """Delay until the agreed interval since the last call has elapsed."""
        if self._last_started is not None:
            waited = self._clock() - self._last_started
            remaining = self.min_interval_sec - waited
            if remaining > 0:
                await self._sleep(remaining)
        self._last_started = self._clock()

    async def run(self, call):
        """Invoke ``call`` under the agreed rate, concurrency and retry policy.

        ``TechnicalLossError`` is NEVER retried: the watchdog has already ruled
        that the peer failed to answer inside its window, and retrying would
        relitigate a match outcome rather than recover from a hiccup.

        Raises:
            Exception: the last failure, once ``max_retries`` is exhausted.
        """
        async with self._semaphore:
            for attempt in range(self._settings.max_retries + 1):
                await self._space()
                try:
                    return await call()
                except TechnicalLossError:
                    raise
                except Exception:
                    if attempt == self._settings.max_retries:
                        raise
                    await self._sleep(self._settings.retry_backoff_sec * 2**attempt)
