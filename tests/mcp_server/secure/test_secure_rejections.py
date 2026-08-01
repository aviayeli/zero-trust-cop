"""Everything the authenticated surface must REFUSE (FR2, FR3, FR4, FR5).

These are the properties training could not exercise and that the old
plaintext `make_move` had none of.
"""

import asyncio

from mcp_server.identity import sign


def test_a_commitment_signed_with_the_wrong_key_is_rejected(
    app, peer_keys, make_commitment
):
    """Signed by the thief, submitted as the police."""
    forged = make_commitment(peer_keys["thief"], "police", 0)

    outcome = asyncio.run(
        app.submit_commitment("police", 0, forged["h_commit"], forged["signature"])
    )

    assert outcome["error"] == "invalid_signature"


def test_a_rejected_commitment_leaves_no_state_behind(
    app, peer_keys, make_commitment
):
    forged = make_commitment(peer_keys["thief"], "police", 0)

    asyncio.run(
        app.submit_commitment("police", 0, forged["h_commit"], forged["signature"])
    )

    assert app.book.commitment_for("police") is None


def test_a_peer_cannot_submit_as_its_opponent(app, peer_keys, make_commitment):
    """The police key signing a submission LABELLED thief must not pass."""
    impersonation = make_commitment(peer_keys["police"], "thief", 0)

    outcome = asyncio.run(
        app.submit_commitment(
            "thief", 0, impersonation["h_commit"], impersonation["signature"]
        )
    )

    assert outcome["error"] == "invalid_signature"


def test_a_caller_supplied_turn_that_disagrees_is_rejected(
    app, peer_keys, make_commitment
):
    """MatchState.turn_count is authoritative; turn 0 is the real turn."""
    ahead = make_commitment(peer_keys["police"], "police", 5)

    outcome = asyncio.run(
        app.submit_commitment("police", 5, ahead["h_commit"], ahead["signature"])
    )

    assert outcome["error"] == "wrong_turn"


def test_a_signature_is_not_replayable_on_the_next_turn(
    app, peer_keys, make_commitment
):
    police = make_commitment(peer_keys["police"], "police", 0)
    thief = make_commitment(peer_keys["thief"], "thief", 0)

    async def play_then_replay():
        for entry in (police, thief):
            await app.submit_commitment(
                entry["role"], 0, entry["h_commit"], entry["signature"]
            )
        for entry in (police, thief):
            await app.reveal_move(
                entry["role"], 0, entry["state"], entry["move"],
                entry["intent"], entry["nonce"], entry["signature"],
            )
        # Turn is now 1; re-present the turn-0 commitment verbatim.
        return await app.submit_commitment(
            "police", 0, police["h_commit"], police["signature"]
        )

    replayed = asyncio.run(play_then_replay())

    assert app.match_state.turn_count == 1
    assert replayed["error"] == "wrong_turn"


def test_a_signature_lifted_to_the_new_turn_number_still_fails(
    app, peer_keys, make_commitment
):
    """Relabelling the turn breaks the signature, which binds the turn."""
    police = make_commitment(peer_keys["police"], "police", 0)
    thief = make_commitment(peer_keys["thief"], "thief", 0)

    async def play_then_relabel():
        for entry in (police, thief):
            await app.submit_commitment(
                entry["role"], 0, entry["h_commit"], entry["signature"]
            )
        for entry in (police, thief):
            await app.reveal_move(
                entry["role"], 0, entry["state"], entry["move"],
                entry["intent"], entry["nonce"], entry["signature"],
            )
        return await app.submit_commitment(
            "police", 1, police["h_commit"], police["signature"]
        )

    assert asyncio.run(play_then_relabel())["error"] == "invalid_signature"
