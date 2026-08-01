"""Transport binding is configured, never a literal in Python (D1)."""

import pytest

from mcp_server.transport import load_transport_settings


@pytest.mark.parametrize("role", ["police", "thief"])
def test_each_peer_declares_a_host_and_port(role):
    settings = load_transport_settings(role)

    assert isinstance(settings.host, str)
    assert isinstance(settings.port, int)


def test_the_two_peers_bind_different_ports():
    """Both peers listen at once; a shared port would collide on startup."""
    police = load_transport_settings("police")
    thief = load_transport_settings("thief")

    assert police.port != thief.port


def test_the_configured_ports_are_the_ruled_ones():
    assert load_transport_settings("police").port == 8801
    assert load_transport_settings("thief").port == 8802


def test_peers_stay_on_the_loopback_interface():
    """A local simulation must not expose a peer to the network."""
    for role in ("police", "thief"):
        assert load_transport_settings(role).host == "127.0.0.1"


def test_a_missing_transport_key_fails_loudly(tmp_path):
    """No defaults: a half-configured peer must not silently bind elsewhere."""
    role_dir = tmp_path / "police"
    role_dir.mkdir()
    (role_dir / "game.toml").write_text('[transport]\nhost = "127.0.0.1"\n')

    with pytest.raises(KeyError):
        load_transport_settings("police", config_root=str(tmp_path))


def test_a_missing_transport_block_fails_loudly(tmp_path):
    role_dir = tmp_path / "thief"
    role_dir.mkdir()
    (role_dir / "game.toml").write_text("[strategy]\nlearning_rate = 0.1\n")

    with pytest.raises(KeyError):
        load_transport_settings("thief", config_root=str(tmp_path))
