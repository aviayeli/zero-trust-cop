"""Network binding is configured, never a literal in Python (D1).

The canonical block is ``[network]``: ``my_port`` is where this peer
listens and ``opponent_url`` is where it reaches the other half.
"""

from urllib.parse import urlsplit

import pytest

from mcp_server.transport import load_network_settings


@pytest.mark.parametrize("role", ["police", "thief"])
def test_each_peer_declares_a_host_and_port(role):
    settings = load_network_settings(role)

    assert isinstance(settings.host, str)
    assert isinstance(settings.my_port, int)


def test_the_two_peers_bind_different_ports():
    """Both peers listen at once; a shared port would collide on startup."""
    police = load_network_settings("police")
    thief = load_network_settings("thief")

    assert police.my_port != thief.my_port


def test_the_configured_ports_are_the_ruled_ones():
    """cop listens on 8802 and thief on 8801, NOT the other way round.

    Pinned as literals on purpose: the pairing below only proves the two
    configs are self-consistent, so a matched double-swap would satisfy it
    while advertising the wrong role to every external peer.
    """
    assert load_network_settings("police").my_port == 8802
    assert load_network_settings("thief").my_port == 8801


def test_peers_bind_every_interface_so_a_tunnel_can_reach_them():
    """Blocker A: ngrok forwards to the listener, and a loopback-only peer
    is unreachable from outside. Exposure is deliberate — the wire is
    authenticated but not encrypted — and `dial_host` keeps our OWN client
    on loopback regardless (`test_dial_host.py`)."""
    for role in ("police", "thief"):
        assert load_network_settings(role).host == "0.0.0.0"


@pytest.mark.parametrize("role,opponent", [("police", "thief"), ("thief", "police")])
def test_a_loopback_opponent_url_names_the_port_the_opponent_binds(role, opponent):
    """Guards a port swap in the LOCAL pairing without pinning league play.

    Once `opponent_url` is repointed at the other group's tunnel it names
    their host, not ours, so the check applies only while it stays on
    loopback. The URL is required to be dialable either way.
    """
    mine = load_network_settings(role)
    theirs = load_network_settings(opponent)
    parts = urlsplit(mine.opponent_url)

    assert parts.scheme in ("http", "https")
    assert parts.hostname
    if parts.hostname in ("127.0.0.1", "localhost", "::1"):
        assert parts.port == theirs.my_port


def test_a_public_tunnel_url_is_available_and_empty_by_default():
    """League play sets this to an ngrok/Localtonet URL; local play leaves it."""
    assert load_network_settings("police").public_url == ""


def test_a_missing_network_key_fails_loudly(tmp_path):
    """No defaults: a half-configured peer must not silently bind elsewhere."""
    role_dir = tmp_path / "police"
    role_dir.mkdir()
    (role_dir / "game.toml").write_text('[network]\nhost = "127.0.0.1"\n')

    with pytest.raises(KeyError):
        load_network_settings("police", config_root=str(tmp_path))


def test_a_missing_network_block_fails_loudly(tmp_path):
    role_dir = tmp_path / "thief"
    role_dir.mkdir()
    (role_dir / "game.toml").write_text("[strategy]\nlearning_rate = 0.1\n")

    with pytest.raises(KeyError):
        load_network_settings("thief", config_root=str(tmp_path))
