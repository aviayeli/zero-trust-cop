"""A fake opponent endpoint for the pre-game probe's tests (PRD_11).

Lives here rather than in either test module because both drive the same
peer: `test_netcheck` covers reachability and the tool surface,
`test_netcheck_terms` covers the handshake and the terms comparison, and a
double copied into two files is a double that drifts between them.

Nothing here opens a socket. The probe under test is read-only, and so is
every case that exercises it.
"""

import asyncio
import contextlib
import json

from mcp_server import interop
from mcp_server.terms import terms_from_config
from scripts import netcheck

TOOLS = ("negotiate", "receive_turn", "submit_audit", "receive_control")


def load_terms(contract="config/game.json"):
    """Our real agreed terms — the ones a live probe would actually send."""
    with open(contract, encoding="utf-8") as shared:
        return terms_from_config(json.load(shared))


class FakePeer:
    """Answers `list_tools` and `negotiate`, and records every call."""

    def __init__(self, tools=TOOLS, reply=None, opens=True):
        self.tools = list(tools)
        self.reply = reply
        self.opens = opens
        self.calls = []

    def opener(self):
        peer = self

        @contextlib.asynccontextmanager
        async def open_peer():
            if peer.opens is not True:
                raise peer.opens
            yield peer

        return open_peer

    async def list_tools(self):
        self.calls.append(("list_tools", {}))
        return list(self.tools)

    async def call(self, tool, **kwargs):
        self.calls.append((tool, kwargs))
        if tool == "negotiate":
            return self.reply
        raise AssertionError(f"probe called an unexpected tool: {tool}")


def signed_reply(terms, nonce="probe-nonce"):
    """What a conformant peer counter-signs a handshake with."""
    return {
        "status": "accepted",
        "terms": dict(terms),
        "nonce": nonce,
        "signature": interop.terms_signature(terms, nonce),
        "role": "thief",
    }


def run_probe(peer, our_terms, our_role="police"):
    return asyncio.run(
        netcheck.probe(peer.opener(), our_terms,
                       {"group_id": "aviayeli"}, our_role)
    )


def verdict_for(report, name):
    """One check's verdict, failing loudly if the probe never ran it."""
    for check in report:
        if check["check"] == name:
            return check
    raise AssertionError(f"no {name!r} check in {[c['check'] for c in report]}")
