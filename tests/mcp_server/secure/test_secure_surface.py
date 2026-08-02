"""The registered tool surface, and a full authenticated turn (FR1, FR3).

`make_move` took a PLAINTEXT direction straight to the engine, with no
commitment, no signature, and no check that the caller was the role it
claimed. D3 replaces it; these tests pin that it is gone and that the
commit-reveal pipeline is what advances the engine.
"""

import asyncio

from mcp_server.server import create_app
from mcp_server.peer_keys import load_public_keys


def _tools(app):
    async def fetch():
        return {tool.name: tool.inputSchema for tool in await app.mcp.list_tools()}

    return asyncio.run(fetch())


def test_plaintext_make_move_is_no_longer_registered(app):
    assert "make_move" not in _tools(app)


def test_the_app_exposes_no_plaintext_move_callable(app):
    assert not hasattr(app, "make_move")


def test_the_authenticated_tools_are_registered(app):
    assert {"submit_commitment", "reveal_move"} <= set(_tools(app))


def test_the_wire_schema_parameter_names_are_pinned(app):
    """FastMCP derives the public schema from the signature: a rename is a
    protocol change, so the parameter names are part of the contract."""
    schemas = _tools(app)

    assert list(schemas["submit_commitment"]["properties"]) == [
        "role",
        "turn",
        "h_commit",
        "signature",
    ]
    assert list(schemas["reveal_move"]["properties"]) == [
        "role",
        "turn",
        "state",
        "move",
        "intent",
        "nonce",
        "signature",
    ]


def test_a_peer_loads_both_public_keys_from_its_own_workspace(secure_config_root):
    """A peer verifies its own submissions as well as its opponent's."""
    keys = load_public_keys("police", secure_config_root)

    assert set(keys) == {"police", "thief"}


def test_loading_public_keys_needs_no_private_key(secure_config_root, tmp_path):
    """The gitignored signing_key.pem is a CLIENT concern, not a server one."""
    assert not list(tmp_path.rglob("signing_key.pem"))

    assert load_public_keys("thief", secure_config_root)


def test_both_commit_then_both_reveal_advances_the_engine(
    app, peer_keys, make_commitment
):
    police = make_commitment(peer_keys["police"], "police", 0, move="south")
    thief = make_commitment(peer_keys["thief"], "thief", 0, move="north")

    async def play_turn():
        first = await app.submit_commitment(
            police["role"], 0, police["h_commit"], police["signature"]
        )
        second = await app.submit_commitment(
            thief["role"], 0, thief["h_commit"], thief["signature"]
        )
        revealed = []
        for entry in (police, thief):
            revealed.append(
                await app.reveal_move(
                    entry["role"], 0, entry["state"], entry["move"],
                    entry["intent"], entry["nonce"], entry["signature"],
                )
            )
        return first, second, revealed

    first, second, revealed = asyncio.run(play_turn())

    assert first["status"] == "waiting"
    assert second["status"] == "both_committed"
    assert revealed[0]["status"] == "waiting"
    assert revealed[1]["status"] == "resolved"
    assert app.match_state.turn_count == 1


def test_the_engine_does_not_advance_on_commitments_alone(
    app, peer_keys, make_commitment
):
    police = make_commitment(peer_keys["police"], "police", 0)
    thief = make_commitment(peer_keys["thief"], "thief", 0)

    async def commit_only():
        await app.submit_commitment(
            police["role"], 0, police["h_commit"], police["signature"]
        )
        await app.submit_commitment(
            thief["role"], 0, thief["h_commit"], thief["signature"]
        )

    asyncio.run(commit_only())

    assert app.match_state.turn_count == 0
