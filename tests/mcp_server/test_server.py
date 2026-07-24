"""Tests for src/mcp_server/server.py — zero-trust P2P FastMCP server."""

import asyncio
import json
import os
import pytest

from mcp_server.server import create_app, peer_config_path, parse_args, PEER_ROLES
from engine.config import load_config


def test_peer_config_path_is_role_separated():
    """peer_config_path returns role-separated paths."""
    police_path = peer_config_path("police")
    thief_path = peer_config_path("thief")
    assert police_path == os.path.join("config", "police", "game.json")
    assert thief_path == os.path.join("config", "thief", "game.json")
    assert police_path != thief_path


def test_peer_config_path_honours_config_root_override():
    """peer_config_path respects config_root parameter."""
    path = peer_config_path("police", config_root="/tmp/x")
    assert path == os.path.join("/tmp/x", "police", "game.json")


def test_create_app_rejects_unknown_role():
    """create_app raises ValueError for unknown role."""
    with pytest.raises(ValueError):
        create_app("referee")


def test_no_module_level_app_singleton():
    """No module-level 'app' variable exists."""
    import mcp_server.server as server_mod
    assert not hasattr(server_mod, "app")


def test_each_peer_is_an_independent_instance():
    """Police and thief apps are independent instances with distinct roles."""
    police = create_app("police")
    thief = create_app("thief")
    assert police.mcp is not thief.mcp
    assert police.match_state is not thief.match_state
    assert police.config_path != thief.config_path
    assert police.own_role == "cop"
    assert thief.own_role == "thief"


def test_police_peer_loads_from_its_own_config_dir():
    """Each peer loads from its own config directory."""
    police = create_app("police")
    thief = create_app("thief")
    assert police.config_path.endswith(os.path.join("police", "game.json"))
    assert thief.config_path.endswith(os.path.join("thief", "game.json"))


def test_exactly_three_tools_registered_with_wire_schema():
    """FastMCP registers exactly 3 tools, and the public input schema names the
    parameter `role` — remote peers call over this contract, so a rename breaks P2P."""
    app = create_app("police")
    async def fetch_tools():
        return {t.name: t.inputSchema for t in await app.mcp.list_tools()}
    schemas = asyncio.run(fetch_tools())
    assert set(schemas) == {"get_observation", "make_move", "get_match_status"}
    assert list(schemas["get_observation"]["properties"]) == ["role"]
    assert list(schemas["make_move"]["properties"]) == ["role", "direction"]
    assert schemas["get_match_status"].get("properties", {}) == {}


def test_startup_wires_config_timeout():
    """MatchState receives response_timeout_sec from loaded config."""
    app = create_app("police")
    cfg = load_config(app.config_path)
    assert app.match_state._response_timeout_sec == cfg.response_timeout_sec


def test_get_observation_serves_only_own_role():
    """get_observation serves only own role; rejects other roles."""
    police = create_app("police")
    async def run_obs():
        cop_obs = await police.get_observation("cop")
        thief_obs = await police.get_observation("thief")
        return cop_obs, thief_obs
    cop_obs, thief_obs = asyncio.run(run_obs())
    assert cop_obs["role"] == "cop"
    assert "thief_position" not in cop_obs
    assert thief_obs["error"] == "invalid_role"


def test_make_move_first_submission_waits():
    """First make_move submission returns status='waiting'."""
    app = create_app("police")
    async def run_move():
        return await app.make_move("cop", "N")
    result = asyncio.run(run_move())
    assert result["status"] == "waiting"
    assert result["role"] == "cop"


def test_make_move_both_roles_resolve_turn():
    """Submitting both roles resolves turn and returns full state."""
    app = create_app("police")
    async def run_moves():
        a = await app.make_move("cop", "N")
        b = await app.make_move("thief", "S")
        return a, b
    a, b = asyncio.run(run_moves())
    assert a["status"] == "waiting"
    assert b["status"] == "resolved"
    assert "cop_position" in b
    assert "thief_position" in b
    assert "captured" in b
    assert "turn_count" in b
    assert "is_terminated" in b
    assert b["terminal_reason"] is None
    json.dumps(b)


def test_make_move_rejects_invalid_direction():
    """make_move rejects invalid direction."""
    app = create_app("police")
    async def run_move():
        return await app.make_move("cop", "DIAGONAL")
    result = asyncio.run(run_move())
    assert result["error"] == "invalid_direction"


def test_get_match_status_delegates():
    """get_match_status returns all required keys with correct values and JSON-serializable."""
    app = create_app("police")
    async def run_status():
        return await app.get_match_status()
    result = asyncio.run(run_status())
    assert result["turn_count"] == 0
    assert result["is_terminated"] is False
    assert result["pending_roles"] == []
    assert result["terminal_reason"] is None
    json.dumps(result)


def test_parse_args_requires_role():
    """parse_args requires --role and rejects missing role."""
    for role in PEER_ROLES:
        assert parse_args(["--role", role]).role == role
    with pytest.raises(SystemExit):
        parse_args([])
