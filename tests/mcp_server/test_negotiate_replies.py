"""What we accept back from a handshake, and what we refuse (PRD_10 10.13).

Split from `test_negotiate_client.py` at the 150-line limit. That module pins
what we SEND; this pins how we judge the reply.

Two spellings are live. Ours is `status: "accepted"` with the terms
counter-signed; ali-ahm1's is a bare `{"accepted": true}` that signs nothing.
Both are real acceptances — theirs is what unblocks their game loop from
reading our turns — so refusing it would stall a series over a word. But an
unsigned acceptance leaves two of our three checks with nothing to run
against, and the caller is TOLD that rather than left to assume a gate ran.

The pairing check is the exception: it needs only `role`, so it survives a
bare acceptance. It is also the one that matters most — a mispairing is
played through coherently by both engines and surfaces only when a human
reads the result.
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


def test_a_refusal_is_raised_with_their_reason():
    """Playing on after a refusal pushes turns into a queue nobody reads."""
    peer = FakePeer({"status": "refused", "reason": "terms disagree on max_steps"})

    with pytest.raises(RuntimeError, match="terms disagree on max_steps"):
        _negotiate(peer)


def test_a_role_collision_in_their_reply_is_raised():
    """`role` is the side THAT peer is playing. Both saying 'police' means one
    of us has the wrong endpoint, and both engines would run a coherent game."""
    peer = FakePeer({"status": "accepted", "terms": dict(TERMS),
                     "nonce": "n", "signature": interop.terms_signature(TERMS, "n"),
                     "role": "police"})

    with pytest.raises(RuntimeError, match="both peers declare role"):
        _negotiate(peer, role="police")


def test_terms_that_disagree_are_named_not_reported_as_a_mismatch():
    theirs = dict(TERMS, max_steps=40)
    peer = FakePeer({"status": "accepted", "terms": theirs, "nonce": "n",
                     "signature": interop.terms_signature(theirs, "n"),
                     "role": "thief"})

    with pytest.raises(RuntimeError, match="max_steps"):
        _negotiate(peer)


def test_a_reply_whose_signature_does_not_verify_is_raised():
    peer = FakePeer({"status": "accepted", "terms": dict(TERMS), "nonce": "n",
                     "signature": "not-the-hash", "role": "thief"})

    with pytest.raises(RuntimeError, match="signature"):
        _negotiate(peer)


def test_a_reply_that_is_not_a_negotiate_at_all_is_raised():
    """A peer answering 200 with something else is not a handshake."""
    with pytest.raises(RuntimeError, match="no spelling we know"):
        _negotiate(FakePeer({"hello": "there"}))


def test_our_own_spelling_without_a_counter_signature_is_unverified_too():
    """Consistent with a bare `accepted: true`: accepted, not verified."""
    outcome = _negotiate(FakePeer({"status": "accepted"}))

    assert outcome["counter_signed"] is False


def test_the_pairing_check_survives_a_reply_that_signs_nothing():
    """The one check that needs only `role` — and the one that matters most,
    since both engines play a mispairing through coherently."""
    with pytest.raises(RuntimeError, match="both peers declare role"):
        _negotiate(FakePeer({"accepted": True, "role": "police"}), role="police")


def test_a_bare_ok_true_is_an_acceptance():
    """ZeroOne0's server answers `{"ok": true}` — a THIRD spelling, after our
    `status` and rstabcde's `accepted`. We refused it, `connect_and_play`
    swallowed the refusal and retried silently, and a live window looked
    exactly like a peer that was down: their endpoint answered 200 the whole
    time and our log stayed empty.
    """
    outcome = _negotiate(FakePeer({"ok": True}))

    assert outcome["reply"] == {"ok": True}
    assert outcome["counter_signed"] is False


def test_ok_false_is_a_refusal():
    with pytest.raises(RuntimeError, match="refused"):
        _negotiate(FakePeer({"ok": False}))


def test_a_reply_with_no_yes_in_any_spelling_is_still_raised():
    with pytest.raises(RuntimeError, match="no spelling we know"):
        _negotiate(FakePeer({"hello": "there"}))
