"""Where a league match reaches its two peers, and on what leash.

Split out of ``run_remote_mcp_match`` for the same reason ``match_report`` was
split out of the local runner: resolving endpoints and opening sessions is a
separate concern from driving a match, and the module was at the 150-line
limit.

The asymmetry here is the whole point. One peer is ours, on loopback,
unthrottled. The other belongs to the opposing group and is reached only at
the URL they published.
"""

import contextlib

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from mcp_server.http_peer import HttpPeer
from mcp_server.rate_limiter import RateLimiter, throttle_settings
from mcp_server.transport import load_network_settings


def remote_endpoints(role, config_root=None):
    """Return ``(our own peer's URL, the opponent's published URL)``.

    Ours is built from ``dial_host``: a peer exposed for league play binds
    ``0.0.0.0``, which is not an address a client can connect to. Theirs is
    taken verbatim from ``opponent_url`` — it names their machine, not ours,
    and rebuilding it from our own bindings is precisely the bug that made a
    remote match impossible.
    """
    binding = load_network_settings(role, config_root)
    local = f"http://{binding.dial_host}:{binding.my_port}/mcp"
    return local, binding.opponent_url


def opponent_limiter(config):
    """The agreed throttle, which league play always applies.

    ``limiter_for`` returns None on loopback because both peers are ours and
    politeness to ourselves only costs minutes. Here the other end is another
    group's server, so the ``rate_limiter_gatekeeper`` block always binds: if
    they enforce it and we do not, WE are the side that gets dropped.
    """
    return RateLimiter(throttle_settings(config))


@contextlib.asynccontextmanager
async def connected_opponent(local_url, remote_url, config, timeout_seconds):
    """Open a session to our own peer and to the opposing group's.

    Yields:
        ``[local, remote]`` HttpPeer adapters, in the order the match loop
        expects, closed on the way out whether or not the match succeeded.
    """
    async with contextlib.AsyncExitStack() as stack:
        peers = []
        for url, limiter in (
            (local_url, None),
            (remote_url, opponent_limiter(config)),
        ):
            read, write, _ = await stack.enter_async_context(
                streamable_http_client(url)
            )
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            peers.append(HttpPeer(session, timeout_seconds, limiter=limiter))
        yield peers
