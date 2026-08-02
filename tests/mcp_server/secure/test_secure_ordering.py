"""Two-phase ordering and commitment integrity (FR3, FR4).

A reveal is refused until BOTH commitments are in, so the second peer cannot
wait to see an opponent's move before choosing its own.
"""

import asyncio

from mcp_server.identity import sign


def test_a_reveal_before_both_commitments_is_refused(
    app, peer_keys, make_commitment
):
    police = make_commitment(peer_keys["police"], "police", 0)

    async def reveal_early():
        await app.submit_commitment(
            "police", 0, police["h_commit"], police["signature"]
        )
        return await app.reveal_move(
            "police", 0, police["state"], police["move"],
            police["intent"], police["nonce"], police["signature"],
        )

    assert asyncio.run(reveal_early())["error"] == "reveal_before_commit"


def test_a_reveal_that_does_not_match_its_commitment_is_refused(
    app, peer_keys, make_commitment
):
    """The anti-front-running property: commit to N, then try to play S."""
    police = make_commitment(peer_keys["police"], "police", 0, move="north")
    thief = make_commitment(peer_keys["thief"], "thief", 0)

    async def substitute_move():
        for entry in (police, thief):
            await app.submit_commitment(
                entry["role"], 0, entry["h_commit"], entry["signature"]
            )
        return await app.reveal_move(
            "police", 0, police["state"], "south",
            police["intent"], police["nonce"], police["signature"],
        )

    outcome = asyncio.run(substitute_move())

    assert outcome["error"] == "broken_commitment"
    assert app.match_state.turn_count == 0


def test_a_reveal_signed_by_the_wrong_key_is_refused(
    app, peer_keys, make_commitment
):
    police = make_commitment(peer_keys["police"], "police", 0)
    thief = make_commitment(peer_keys["thief"], "thief", 0)

    async def forged_reveal():
        for entry in (police, thief):
            await app.submit_commitment(
                entry["role"], 0, entry["h_commit"], entry["signature"]
            )
        forged = sign(peer_keys["thief"], "police", 0, police["h_commit"])
        return await app.reveal_move(
            "police", 0, police["state"], police["move"],
            police["intent"], police["nonce"], forged,
        )

    assert asyncio.run(forged_reveal())["error"] == "invalid_signature"
