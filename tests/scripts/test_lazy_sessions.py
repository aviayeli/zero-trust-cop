"""Open a session when the sub-game needs it, not before (PRD_10 10.27).

`opponents()` opened every endpoint at series start and held them. Sub-game 1
runs 190+ seconds, so against a two-process opponent the session for the OTHER
process sat idle that whole time — past their 180s watchdog — and by the time
sub-game 2 addressed it, it was gone. `McpError: Session terminated`, or a 502
from a peer that had reaped it.

Nine attempts died at the sub-game boundary and the boundary was never the
cause: the session had been dead for a minute before we got there. rstabcde
completed counted series with two other groups, which is what made this
obviously ours rather than theirs.

Opening lazily also means an endpoint that is down costs nothing until the
schedule actually reaches it.
"""

import asyncio
import contextlib

from scripts.reference_dial import lazy_opponents


class Dialler:
    def __init__(self, fails=()):
        self.opened = []
        self.fails = set(fails)

    @contextlib.asynccontextmanager
    async def open(self, url, config):
        if url in self.fails:
            raise RuntimeError(f"502 for {url}")
        self.opened.append(url)
        yield lambda tool, **kw: url


ENDPOINTS = {"cop": "https://cop/mcp", "thief": "https://thief/mcp"}


def _reach(dialler, endpoints=None):
    async def go(fn):
        async with lazy_opponents(endpoints or ENDPOINTS, None,
                                  dial=dialler.open) as reach:
            return await fn(reach)
    return go


def test_nothing_is_opened_until_a_role_asks():
    d = Dialler()

    async def body(reach):
        return None

    asyncio.run(_reach(d)(body))

    assert d.opened == []


def test_playing_police_opens_only_their_thief():
    d = Dialler()

    async def body(reach):
        await reach("police")

    asyncio.run(_reach(d)(body))

    assert d.opened == ["https://thief/mcp"]


def test_a_second_ask_for_the_same_role_reuses_the_session():
    """Within one sub-game every push must ride the same connection."""
    d = Dialler()

    async def body(reach):
        await reach("police")
        await reach("police")

    asyncio.run(_reach(d)(body))

    assert d.opened == ["https://thief/mcp"]


def test_swapping_sides_opens_the_other_endpoint_then():
    d = Dialler()

    async def body(reach):
        await reach("police")
        await reach("thief")

    asyncio.run(_reach(d)(body))

    assert d.opened == ["https://thief/mcp", "https://cop/mcp"]


def test_a_dead_endpoint_costs_nothing_until_it_is_needed():
    """Their cop being down must not stop us playing sub-games as police."""
    d = Dialler(fails={"https://cop/mcp"})

    async def body(reach):
        await reach("police")
        return "played"

    assert asyncio.run(_reach(d)(body)) == "played"
