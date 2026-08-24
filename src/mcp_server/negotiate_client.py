"""The ``negotiate`` gate, OUTBOUND (PRD_10 10.13).

Our server has verified their handshake since the reference-v3 phase; nothing
ever sent one. The runner opened a session and pushed turns, which looked
sound because our own ``receive_turn`` does not gate on a handshake.

Theirs does, in the place that matters: ali-ahm1 confirmed on 2026-08-24 that
their server QUEUES turns ungated and their game loop will not read that
queue until negotiate has completed. Turns pushed first sit unread forever,
and to us that is indistinguishable from a peer that is merely slow.

So this runs the same three checks we already apply to them, in the direction
we never ran them:

* their SIGNATURE over the terms they sent, with the nonce they sent;
* their TERMS against ours, naming the first value that differs;
* the PAIRING -- ``role`` is the side THAT peer is playing, and two peers
  declaring the same one is a mispairing that both engines would otherwise
  play through coherently. Eight of ali-ahm1's calls were refused by us for
  exactly this before they fixed their URL routing.

Every failure RAISES. Continuing past a refused handshake pushes a whole
sub-game into a queue nobody reads.
"""

from __future__ import annotations

from secrets import token_hex

from mcp_server import interop
from mcp_server.negotiate_reply import _check, _require_acceptance

_NONCE_BYTES = 16


async def negotiate(call, our_terms: dict, identity: dict, our_role: str,
                    sub_game_number: int, nonce_source=None) -> dict:
    """Open one sub-game with the opponent and check what comes back.

    ``sub_game_number`` rides BESIDE ``terms``, never inside it: the terms are
    a flat signed set and an extra key there changes the hash both peers are
    verifying.

    Returns:
        ``{"reply": <their reply>, "counter_signed": bool}``. The flag is not
        decoration: ali-ahm1's server answers a bare ``{"accepted": true}``,
        which is a real acceptance -- it is what unblocks their game loop from
        reading our turns -- but it carries no terms, no nonce and no
        signature, so two of our three checks have nothing to run against.
        Reporting that as a passed gate would assert a verification we never
        performed.

    Raises:
        RuntimeError: they refused, the reply is not a handshake at all, or a
            check that COULD run failed. Named with the cause, because the
            operator is otherwise left diffing fourteen values that agree.
    """
    nonce = (nonce_source or (lambda: token_hex(_NONCE_BYTES)))()
    reply = await call("negotiate", message={
        "terms": dict(our_terms),
        "nonce": nonce,
        "signature": interop.terms_signature(our_terms, nonce),
        "identity": dict(identity),
        "sub_game_number": sub_game_number,
        "role": our_role,
    })
    _require_acceptance(reply)
    return {"reply": reply,
            "counter_signed": _check(reply, our_terms, our_role,
                                     sub_game_number)}
