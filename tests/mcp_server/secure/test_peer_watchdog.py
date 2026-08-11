"""A silent peer must cost the match, not the process.

``call_tool`` over streamable HTTP has no deadline of its own: a peer that
accepts the connection and then stops answering leaves the caller awaiting a
reply that never comes, and the whole tournament hangs on one stalled process.
``watchdog_timeout_sec`` is already published in ``game.json`` for exactly this
purpose, and this is where it is enforced.

The outcome is a TECHNICAL LOSS, raised as a typed error, because that is what
the rulebook calls a peer that fails to answer — not a crash, and not a hang.
"""

import json

import anyio
import pytest

from engine.config import load_config
from mcp_server.http_peer import HttpPeer, TechnicalLossError

SHARED_CONFIG_PATH = "config/game.json"
_FAST_TIMEOUT = 0.05


class _Payload:
    """The content shape ``call_tool`` returns: one text part holding JSON."""

    def __init__(self, payload):
        self.content = [type("Part", (), {"text": json.dumps(payload)})()]


class _AnsweringSession:
    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return _Payload(self._payload)


class _StalledSession:
    """A peer that accepted the request and will never answer it."""

    def __init__(self):
        self.cancelled = False

    async def call_tool(self, name, arguments):
        try:
            await anyio.sleep(30)
        except BaseException:
            self.cancelled = True
            raise


def test_a_stalled_peer_raises_a_technical_loss_instead_of_hanging():
    session = _StalledSession()
    peer = HttpPeer(session, _FAST_TIMEOUT)

    with pytest.raises(TechnicalLossError):
        anyio.run(peer.get_match_status)

    assert session.cancelled, "the stalled call must be cancelled, not orphaned"


def test_the_technical_loss_names_the_tool_and_the_deadline():
    peer = HttpPeer(_StalledSession(), _FAST_TIMEOUT)

    with pytest.raises(TechnicalLossError) as raised:
        anyio.run(peer.get_observation, "police")

    assert "get_observation" in str(raised.value)
    assert str(_FAST_TIMEOUT) in str(raised.value)


def test_every_wire_method_is_guarded():
    """A watchdog on one method only would leave the others able to hang."""
    calls = {
        "submit_commitment": ("police", 0, "digest", "signature"),
        "reveal_move": ("police", 0, "state", "N", "north", "nonce", "sig"),
        "get_match_status": (),
        "get_observation": ("police",),
    }
    for name, arguments in calls.items():
        peer = HttpPeer(_StalledSession(), _FAST_TIMEOUT)
        with pytest.raises(TechnicalLossError):
            anyio.run(getattr(peer, name), *arguments)


def test_a_peer_that_answers_in_time_is_untouched():
    session = _AnsweringSession({"status": "resolved", "turn": 0})
    peer = HttpPeer(session, _FAST_TIMEOUT)

    assert anyio.run(peer.get_match_status) == {"status": "resolved", "turn": 0}
    assert session.calls == [("get_match_status", {})]


def test_the_watchdog_is_configured_and_not_inlined():
    """The deadline is whatever the shared config publishes."""
    config = load_config(SHARED_CONFIG_PATH)
    peer = HttpPeer(_AnsweringSession({}), config.watchdog_timeout_sec)

    assert peer.timeout_seconds == config.watchdog_timeout_sec
    assert config.watchdog_timeout_sec > 0


def test_a_peer_cannot_be_built_without_a_deadline():
    """An optional timeout would let a call site silently reintroduce the hang."""
    with pytest.raises(TypeError):
        HttpPeer(_AnsweringSession({}))
