"""The push dialect is OPT-IN, and refuses before it records (PRD_09 FR5).

This surface accepts UNAUTHENTICATED submissions: their `receive_commit`
carries no signature, so nothing binds a move to a peer identity. That is the
exact thing our own dialect exists to prevent, so it must not be reachable
unless somebody asked for it. The first test here is the one that keeps the
live wire from widening by accident.
"""

import asyncio

import pytest

from mcp_server.server import create_app

OURS = {"submit_commitment", "reveal_move", "get_observation", "get_match_status"}
REFERENCE_V3 = {"negotiate", "receive_turn", "submit_audit", "receive_control"}
PUSH = {"receive_step0", "receive_commit", "receive_reveal", "receive_ack",
        "receive_capture_claim", "receive_final_audit"}

COMMIT = "a" * 64

# Unlike reference-v3's single envelope argument, the push dialect is FLAT:
# their tools/list shows receive_commit(role, step, h_commit). Their client
# calls us with those names, so our signatures must match theirs exactly.


def _names(app):
    async def fetch():
        return {tool.name for tool in await app.mcp.list_tools()}

    return asyncio.run(fetch())


@pytest.fixture
def push_app(secure_config_root):
    return create_app("police", config_root=secure_config_root, dialect="push")


def test_without_the_flag_the_push_tools_do_not_exist(app):
    """The default surface must be unchanged, exactly."""
    names = _names(app)

    assert names == OURS | REFERENCE_V3
    assert not (names & PUSH)


def test_with_the_flag_the_six_appear_beside_the_others(push_app):
    names = _names(push_app)

    assert PUSH <= names
    assert OURS <= names and REFERENCE_V3 <= names


def test_the_flag_defaults_off(secure_config_root):
    assert not (_names(create_app("police", config_root=secure_config_root)) & PUSH)


def test_an_unknown_dialect_is_refused_rather_than_ignored(secure_config_root):
    """Silently ignoring a typo would leave the operator believing the dialect
    is on while the tools are absent."""
    with pytest.raises(ValueError, match="dialect"):
        create_app("police", config_root=secure_config_root, dialect="pusk")


# --- the CLI gate ----------------------------------------------------------


def test_the_cli_defaults_the_dialect_off():
    """The shipped command must not widen the wire."""
    from mcp_server.server import parse_args

    assert parse_args(["--role", "police"]).dialect is None


def test_the_cli_accepts_the_push_dialect():
    from mcp_server.server import parse_args

    assert parse_args(["--role", "police", "--dialect", "push"]).dialect == "push"


def test_the_cli_refuses_an_unknown_dialect():
    from mcp_server.server import parse_args

    with pytest.raises(SystemExit):
        parse_args(["--role", "police", "--dialect", "pusk"])
