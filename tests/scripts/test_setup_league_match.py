"""The two pre-game steps that no test can catch and every match needs.

Both failures this automates are silent until the match is already running.
An unadvertised tunnel means the opposing group reads our declaration and
dials `127.0.0.1`, reaching their own machine. A missing opponent key means
every submission they sign is refused as `invalid_signature` — on turn 0, in
front of the league.

So both are validated BEFORE anything is written: a malformed key must not be
able to replace a working one.
"""

import json

import pytest

from mcp_server.identity import load_peer_public_key
from scripts.setup_league_match import (
    install_opponent_key,
    main,
    set_public_url,
)

NGROK = "https://avi-cop.ngrok-free.app"
KEY = "a" * 64  # 32 bytes of valid hex


@pytest.fixture
def root(tmp_path):
    """A config root holding just what these two steps touch."""
    (tmp_path / "police" / "peers").mkdir(parents=True)
    (tmp_path / "police" / "peers" / "thief.pub").write_text("b" * 64)
    (tmp_path / "declaration.json").write_text(
        json.dumps(
            {
                "group_name": "aviayeli",
                "mcp_servers": {
                    "cop": "http://127.0.0.1:8802/mcp",
                    "thief": "http://127.0.0.1:8801/mcp",
                },
            }
        )
    )
    return str(tmp_path)


def declared(root):
    return json.loads((__import__("pathlib").Path(root) / "declaration.json").read_text())


def test_our_tunnel_replaces_the_loopback_endpoint(root):
    set_public_url(NGROK, config_root=root)

    assert declared(root)["mcp_servers"]["cop"] == f"{NGROK}/mcp"


def test_the_mcp_path_is_added_because_the_endpoint_is_not_the_root(root):
    """ngrok hands out a bare host; the declaration must name the MCP endpoint."""
    set_public_url(f"{NGROK}/", config_root=root)

    assert declared(root)["mcp_servers"]["cop"].endswith("/mcp")


def test_an_endpoint_that_already_names_mcp_is_not_doubled(root):
    set_public_url(f"{NGROK}/mcp", config_root=root)

    assert declared(root)["mcp_servers"]["cop"] == f"{NGROK}/mcp"


def test_the_other_role_is_left_alone(root):
    """Each peer has its own tunnel; setting one must not claim the other."""
    set_public_url(NGROK, config_root=root)

    assert declared(root)["mcp_servers"]["thief"] == "http://127.0.0.1:8801/mcp"


def test_a_tcp_forwarder_url_is_refused_before_anything_is_written(root):
    """The mistake the ngrok dashboard invites, caught while it is still ours."""
    with pytest.raises(ValueError):
        set_public_url("tcp://0.tcp.ngrok.io:12345", config_root=root)

    assert declared(root)["mcp_servers"]["cop"] == "http://127.0.0.1:8802/mcp"


def test_the_opponents_key_is_installed_where_our_server_reads_it(root, tmp_path):
    source = tmp_path / "groupb.pub"
    source.write_text(KEY)

    install_opponent_key(str(source), config_root=root)

    assert load_peer_public_key("police", "thief", root)


def test_a_malformed_key_never_replaces_a_working_one(root, tmp_path):
    """Validate first: a bad paste must not disarm the peer we can verify."""
    source = tmp_path / "broken.pub"
    source.write_text("not-hexadecimal")
    installed = __import__("pathlib").Path(root) / "police" / "peers" / "thief.pub"

    with pytest.raises(ValueError):
        install_opponent_key(str(source), config_root=root)

    assert installed.read_text() == "b" * 64


def test_a_key_of_the_wrong_length_is_refused(root, tmp_path):
    source = tmp_path / "short.pub"
    source.write_text("abcd")

    with pytest.raises(ValueError):
        install_opponent_key(str(source), config_root=root)


def test_both_steps_run_from_the_command_line(root, tmp_path, capsys):
    source = tmp_path / "groupb.pub"
    source.write_text(KEY)

    main(["--public-url", NGROK, "--opponent-key", str(source),
          "--config-root", root])

    assert declared(root)["mcp_servers"]["cop"] == f"{NGROK}/mcp"
    assert load_peer_public_key("police", "thief", root)
    assert "ready" in capsys.readouterr().out.lower()


def test_doing_nothing_is_refused_rather_than_reported_as_success(root):
    """A no-argument run that printed 'done' would be the worst outcome."""
    with pytest.raises(SystemExit):
        main(["--config-root", root])


def test_a_bad_key_aborts_before_the_declaration_is_touched(root, tmp_path):
    """Half-applied setup is worse than none: it looks done and is not."""
    source = tmp_path / "broken.pub"
    source.write_text("not-hexadecimal")

    with pytest.raises(ValueError):
        main(["--public-url", NGROK, "--opponent-key", str(source),
              "--config-root", root])

    assert declared(root)["mcp_servers"]["cop"] == "http://127.0.0.1:8802/mcp"
