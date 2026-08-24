"""Reaching the opponent: the liveness probe and the session (PRD_10 10.16).

Split from ``reference_launch`` at the transport seam -- that module decides
WHEN to try, this one knows what a try consists of.

It holds one thing: opening a session to the opponent. A separate HTTP
liveness probe lived here too and was removed -- ``connect_and_play`` retries
the session open itself, so the probe only bought a second, invisible
deadline.
"""

from __future__ import annotations

import contextlib

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from mcp_server.http_peer import HttpPeer
from scripts.remote_peers import opponent_limiter

# Pause between attempts to open an endpoint that is flapping, and how many.
# 36 x 5s = three minutes, chosen to cover a full up/down cycle: rstabcde's
# cop answered 502 to an open and 200 to a probe thirty seconds later, and
# cycles on roughly one to two minutes. A thirty-second cushion sat inside
# that cycle and would have missed as often as it hit.
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


async def reachable(url: str) -> str:
    """One cheap liveness probe. Raises while their side is not serving.

    A plain POST rather than an MCP session: we are asking whether anything
    is behind their tunnel, and a session opened to answer that would have to
    be torn down again on every attempt.

    Raises:
        httpx.HTTPStatusError: their tunnel answered but nothing is behind it
            (the 502 an ngrok agent returns with a dead upstream), or the
            server refused. Raised rather than returned so the retry sees the
            reason and the operator sees THEIR error, not a generic timeout.
    """
    async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT_SEC) as client:
        response = await client.post(url, headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }, json={
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {"protocolVersion": _PROTOCOL_VERSION, "capabilities": {},
                       "clientInfo": {"name": "zero-trust-cop", "version": "1"}},
        })
        response.raise_for_status()
        return url


@contextlib.asynccontextmanager
async def opponents(endpoints: dict, config, urls=None):
    """Open every endpoint the opponent serves; yield `(our_role) -> call`.

    ``urls`` narrows this to the endpoints the schedule will actually
    address. Opening every endpoint the opponent serves killed runs that
    needed only one: a single sub-game as police never reaches their cop, and
    their cop returning 502 took the whole run with it.

    Whatever is opened is opened ONCE and kept for the series -- reopening
    per sub-game would hand a peer a fresh session mid-series, and the sides
    swap often enough that the churn would be constant.
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


@contextlib.asynccontextmanager
async def lazy_opponents(endpoints: dict, config, dial=None,
                         attempts: int = 36, sleep=None):
    """Yield ``async (our_role) -> call``, opening each endpoint ON FIRST USE.

    Opening everything at series start held a session for the opponent's OTHER
    process idle through the whole of sub-game 1 -- 190+ seconds against a
    180s watchdog -- so by the time sub-game 2 addressed it, it was already
    reaped. Nine attempts died at the sub-game boundary and the boundary was
    never the cause; the connection had been dead for a minute before we got
    there.

    A session is opened once per endpoint and then reused, so every push
    inside a sub-game still rides one connection. And an endpoint that is
    down costs nothing until the schedule actually reaches it.

    An open that FAILS is retried: their cop returned 502 to our open and 200
    to a probe thirty seconds later. Retrying an open replays nothing -- the
    previous sub-game is already banked and the new one has pushed no turn --
    which is why this is safe here and not in ``connect_and_play``, where a
    reconnect would hand them a second copy of a series already under way.
    """
    import asyncio as _asyncio

    waiter = sleep or _asyncio.sleep
    from scripts.opponent_endpoints import endpoint_for

    opener = dial or opponent
    calls: dict = {}
    async with contextlib.AsyncExitStack() as stack:
        async def reach(role):
            url = endpoint_for(endpoints, role)
            if url not in calls:
                for attempt in range(attempts):
                    try:
                        calls[url] = await stack.enter_async_context(
                            opener(url, config)
                        )
                        break
                    except BaseException as failure:
                        # BaseException: anyio wraps their 502 in a task
                        # group, so it arrives as a BaseExceptionGroup.
                        if isinstance(failure, (KeyboardInterrupt, SystemExit)):
                            raise
                        if attempt == attempts - 1:
                            raise
                        await waiter(_REOPEN_WAIT_SEC)
            return calls[url]

        yield reach
