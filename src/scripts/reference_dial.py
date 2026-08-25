"""Reaching the opponent: opening a session to their endpoint (PRD_10 10.16).

Split from ``reference_launch`` at the transport seam: that module decides WHEN
to try, this knows what a try consists of. A separate HTTP liveness probe lived
here and was removed -- ``connect_and_play`` retries the open itself, so the
probe only bought a second, invisible deadline.
"""

from __future__ import annotations

import contextlib

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from mcp_server.http_peer import HttpPeer
from scripts.remote_peers import opponent_limiter

# Pause between attempts on a flapping endpoint. 36 x 5s = three minutes, to
# cover a full up/down cycle: rstabcde's cop answered 502 to an open and 200
# to a probe thirty seconds later, cycling on one to two minutes. A
# thirty-second cushion sat inside that cycle and missed as often as it hit.
_REOPEN_WAIT_SEC = 5.0

@contextlib.asynccontextmanager
async def opponent(url: str, config):
    """A callable that invokes one of their tools, under our watchdog.

    Rate-limited by the agreed ``rate_limiter_gatekeeper`` block: the other
    end is another group's server, and if they enforce it and we do not, WE
    are the side that gets dropped.
    """
    async with streamable_http_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            peer = HttpPeer(session, config.watchdog_timeout_sec,
                            limiter=opponent_limiter(config))
            yield peer.call


@contextlib.asynccontextmanager
async def opponents(endpoints: dict, config, urls=None):
    """Open every endpoint the opponent serves; yield `(our_role) -> call`.

    ``urls`` narrows this to the endpoints the schedule will actually address.
    Opening all of them killed runs that needed one: a single sub-game as
    police never reaches their cop, and their cop's 502 took the run with it.
    Whatever opens, opens ONCE and is kept for the series.
    """
    from scripts.opponent_endpoints import endpoint_for

    urls = sorted(urls) if urls else sorted(
        {endpoints["cop"], endpoints["thief"]})
    async with contextlib.AsyncExitStack() as stack:
        calls = {
            url: await stack.enter_async_context(opponent(url, config))
            for url in urls
        }
        yield lambda role: calls[endpoint_for(endpoints, role)]


# Re-exported: the session POOL moved to ``scripts.reference_pool`` at the
# 150-line limit, and callers still reach for it by this name.
def lazy_opponents(*args, **kwargs):
    """See ``scripts.reference_pool.lazy_opponents``."""
    from scripts.reference_pool import lazy_opponents as _lazy

    return _lazy(*args, **kwargs)
