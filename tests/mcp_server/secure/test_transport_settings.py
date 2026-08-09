"""Network binding is configured, never a literal in Python (D1).

The canonical block is ``[network]``: ``my_port`` is where this peer
listens and ``opponent_url`` is where it reaches the other half.
"""

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


def test_peers_stay_on_the_loopback_interface():
    """A local simulation must not expose a peer to the network."""
    for role in ("police", "thief"):
        assert load_network_settings(role).host == "127.0.0.1"


def test_each_peer_points_at_the_other_ones_port():
    """The opponent URL must name the port the opponent actually binds."""
    police = load_network_settings("police")
    thief = load_network_settings("thief")

    assert police.opponent_url == f"http://{thief.host}:{thief.my_port}/mcp"
    assert thief.opponent_url == f"http://{police.host}:{police.my_port}/mcp"


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
