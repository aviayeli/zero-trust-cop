"""Our negotiate answers in BOTH spellings (PRD_10 10.15).

We say `status: "accepted"`; ali-ahm1 says `accepted: true`. A client reading
only its own key sees the other's answer as absent — and on 2026-08-24 that
stalled a live series with both peers negotiated, both endpoints returning
200, and neither side pushing a turn. Extra keys are tolerated on this wire,
so carrying both removes the guess.

The refusal case matters more than the acceptance: a peer reading only
`accepted` must not read a refusal as silence and play on regardless.
"""

import asyncio
import json
from pathlib import Path

from mcp_server import interop
from mcp_server.terms import terms_from_config


def _our_terms(app):
    return terms_from_config(
        json.loads(Path(app.config_path).read_text(encoding="utf-8"))
    )


def test_an_acceptance_carries_BOTH_spellings(app):
    """We answer `status: "accepted"`; ali-ahm1 answers `accepted: true`.

    A client reading only its own spelling sees the other's acceptance as
    absent and reads it as a refusal — which is how a live series stalled on
    2026-08-24 with both peers negotiated, both returning 200, and neither
    pushing a turn. Extra keys are tolerated on this wire (the extension
    seam), so carrying both costs nothing and removes the guess.
    """
    ours = _our_terms(app)
    nonce = "00112233445566778899aabbccddeeff"
    result = asyncio.run(app.negotiate({
        "terms": ours, "nonce": nonce,
        "signature": interop.terms_signature(ours, nonce),
        "identity": {"group_name": "ali-ahm1"},
        "sub_game_number": 1, "role": "thief",
    }))

    assert result["status"] == "accepted"
    assert result["accepted"] is True


def test_a_refusal_says_no_in_both_spellings_too(app):
    """The mirror case matters more: a peer reading only `accepted` must not
    read a REFUSAL as silence and play on."""
    result = asyncio.run(app.negotiate({"terms": {"a": 1}, "nonce": "n",
                                        "signature": "wrong"}))

    assert result["status"] == "refused"
    assert result["accepted"] is False
