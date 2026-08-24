"""The handshake in the direction we never ran it (PRD_10 10.13).

Our server has verified THEIR negotiate since the reference-v3 phase. Nothing
ever sent one. The runner opened a session and started pushing turns, which
looked fine because our own `receive_turn` does not gate on a handshake — and
ali-ahm1 confirmed on 2026-08-24 that theirs does: their server queues turns
without gating and their GAME LOOP will not read that queue until negotiate
completes. Turns pushed first sit unread. Silent, and indistinguishable from
a peer that is simply slow.

So this is the same gate, outbound, and it runs the same three checks we
apply to them: their signature over their terms, their terms against ours,
and the pairing. The pairing check is not theoretical — eight of their calls
were refused by us for declaring the same role we were playing.
"""

import asyncio

import pytest

from mcp_server import interop
from mcp_server.negotiate_client import negotiate

TERMS = {"board_size": 7, "max_steps": 35}
IDENTITY = {"group_name": "aviayeli", "wire_shape": "reference-v3"}


class FakePeer:
    """Answers a negotiate the way a conformant opponent would."""

    def __init__(self, reply=None):
        self.calls = []
        self._reply = reply

    async def __call__(self, tool, **kwargs):
        self.calls.append((tool, kwargs))
        if self._reply is not None:
            return self._reply
        nonce = "theirs"
        return {
            "status": "accepted", "terms": dict(TERMS), "nonce": nonce,
            "signature": interop.terms_signature(TERMS, nonce),
            "role": "thief", "identity": {"group_name": "ali-ahm1"},
        }

    def sent(self):
        return self.calls[0][1]["message"]


def run(coro):
    return asyncio.run(coro)


def _negotiate(peer, role="police", sub_game=1):
    return run(negotiate(peer, TERMS, IDENTITY, role, sub_game,
                         nonce_source=lambda: "ours"))


def test_the_envelope_rides_under_one_key(peer_or_none=None):
    peer = FakePeer()
    _negotiate(peer)

    assert peer.calls[0][0] == "negotiate"
    assert set(peer.calls[0][1]) == {"message"}


def test_we_sign_our_own_terms_with_our_own_nonce():
    peer = FakePeer()
    _negotiate(peer)

    sent = peer.sent()
    assert sent["signature"] == interop.terms_signature(TERMS, "ours")
    assert sent["nonce"] == "ours"
    assert sent["terms"] == TERMS


def test_the_pairing_extras_ride_beside_the_terms_never_inside():
    """The terms are a flat SIGNED set; an extra key there breaks the hash."""
    peer = FakePeer()
    _negotiate(peer, role="police", sub_game=3)

    sent = peer.sent()
    assert sent["role"] == "police"
    assert sent["sub_game_number"] == 3
    assert sent["identity"] == IDENTITY
    assert "role" not in sent["terms"] and "sub_game_number" not in sent["terms"]


def test_a_counter_signed_acceptance_is_reported_as_verified():
    outcome = _negotiate(FakePeer())

    assert outcome["reply"]["status"] == "accepted"
    assert outcome["counter_signed"] is True


def test_a_bare_accepted_true_is_an_acceptance(peer=None):
    """ali-ahm1's server answers `{"accepted": true}` and counter-signs
    nothing. That IS their acceptance and it is what unblocks their game loop
    from reading our turns, so refusing it would stall a live series over a
    spelling. Verified separately from accepted: see the next test."""
    outcome = _negotiate(FakePeer({"accepted": True}))

    assert outcome["reply"] == {"accepted": True}


def test_an_unsigned_acceptance_is_reported_as_UNVERIFIED():
    """The three checks need their terms, their nonce and their signature. A
    reply carrying none of them cannot be checked, and saying it passed would
    assert a gate we never ran."""
    outcome = _negotiate(FakePeer({"accepted": True}))

    assert outcome["counter_signed"] is False


def test_accepted_false_is_a_refusal():
    with pytest.raises(RuntimeError, match="refused"):
        _negotiate(FakePeer({"accepted": False}))
