"""HttpPeer routes every wire call through the agreed throttle.

The limiter is useless unless the transport actually uses it, and the seam is
easy to add and forget — exactly how `rate_limiter_gatekeeper` came to be
declared and unread in the first place. So the wiring is asserted, not assumed.
"""

import asyncio

import pytest

from engine.config import load_config
from mcp_server.http_peer import HttpPeer
from mcp_server.rate_limiter import RateLimiter, throttle_settings


class _Session:
    def __init__(self):
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append(name)

        class _Result:
            content = [type("T", (), {"text": '{"status": "ok"}'})()]

        return _Result()


class _CountingLimiter:
    def __init__(self):
        self.ran = 0

    async def run(self, call):
        self.ran += 1
        return await call()


def test_throttle_settings_come_from_the_shared_contract():
    """Every figure negotiated, none inlined."""
    settings = throttle_settings(load_config("config/game.json"))

    assert settings.requests_per_minute == 30
    assert settings.concurrent_requests == 2
    assert settings.retry_backoff_sec == 5
    assert settings.max_retries == 3


def test_every_tool_call_goes_through_the_limiter():
    limiter = _CountingLimiter()
    peer = HttpPeer(_Session(), timeout_seconds=5, limiter=limiter)

    asyncio.run(peer.get_match_status())
    asyncio.run(peer.get_observation("cop"))

    assert limiter.ran == 2


def test_a_peer_without_a_limiter_still_works():
    """The limiter is optional so existing call sites keep working unchanged."""
    peer = HttpPeer(_Session(), timeout_seconds=5)

    assert asyncio.run(peer.get_match_status()) == {"status": "ok"}


def test_the_real_limiter_is_accepted_by_the_transport():
    settings = throttle_settings(load_config("config/game.json"))
    peer = HttpPeer(_Session(), timeout_seconds=5, limiter=RateLimiter(settings))

    assert asyncio.run(peer.get_match_status()) == {"status": "ok"}


def test_a_loopback_peer_is_not_throttled():
    """The agreed limit protects the OPPOSING peer; on loopback both are ours.

    Applying it locally would spend five minutes per 35-turn match to be
    polite to ourselves. The decision is a function rather than a comment so
    it can be asserted.
    """
    from mcp_server.rate_limiter import limiter_for

    assert limiter_for(load_config("config/game.json"), public_url="") is None


def test_a_peer_reachable_over_a_tunnel_is_throttled():
    """A public_url means a real opponent is on the other end."""
    from mcp_server.rate_limiter import limiter_for

    limiter = limiter_for(load_config("config/game.json"), public_url="https://x.ngrok.app")

    assert limiter is not None
    assert limiter.concurrency == 2
