"""The runner must dial the OPPONENT, not a second copy of ourselves.

`opponent_url` was loaded into NetworkSettings from the very first phase and
then read by nothing: every runner built both endpoints out of our own
bindings and spawned both peers locally. A league match therefore could not be
played at all, and the misconfiguration had no local symptom — the loopback
simulation passed either way.

These tests pin the two halves that must differ: where our own peer is
reached, and where the other group's is.
"""

import pytest

from engine.config import load_config
from mcp_server.transport import load_network_settings
from scripts.remote_peers import opponent_limiter, remote_endpoints

NGROK = "https://groupb-thief.ngrok-free.app/mcp"


@pytest.fixture
def tunnelled_root(tmp_path):
    """A police workspace whose opponent is reachable only over a tunnel."""
    role_dir = tmp_path / "police"
    role_dir.mkdir()
    (role_dir / "game.toml").write_text(
        '[network]\nhost = "0.0.0.0"\nmy_port = 8802\n'
        f'opponent_url = "{NGROK}"\n'
        'public_url = "https://avi-cop.ngrok-free.app"\n'
        "poll_interval_sec = 0.5\n"
    )
    return str(tmp_path)


def test_the_opponent_is_dialled_at_its_published_tunnel(tunnelled_root):
    """The bug in one line: this used to resolve to our own loopback port."""
    _local, remote = remote_endpoints("police", tunnelled_root)

    assert remote == NGROK


def test_our_own_peer_is_dialled_over_loopback_though_bound_publicly(
    tunnelled_root,
):
    """Binding 0.0.0.0 for the tunnel must not redirect our OWN client."""
    local, _remote = remote_endpoints("police", tunnelled_root)

    assert local == "http://127.0.0.1:8802/mcp"


def test_the_two_endpoints_are_never_the_same_peer(tunnelled_root):
    """Mirrored local truth needs two DISTINCT engines to compare."""
    local, remote = remote_endpoints("police", tunnelled_root)

    assert local != remote


@pytest.mark.parametrize("role", ["police", "thief"])
def test_the_shipped_configs_resolve_both_endpoints(role):
    """The real config must produce a dialable pair for either role."""
    local, remote = remote_endpoints(role)

    assert local.startswith("http://127.0.0.1:")
    assert remote.startswith("http")


def test_the_opponents_server_is_throttled_to_the_agreed_rate():
    """The gatekeeper block exists to keep us from overrunning THEIR server.

    Unlike the loopback simulation there is a real peer on the other end, so
    the agreed limit applies to every remote call rather than none of them.
    """
    limiter = opponent_limiter(load_config("config/police/game.json"))

    assert limiter.concurrency == 2
    assert limiter.min_interval_sec == pytest.approx(2.0)


@pytest.mark.parametrize("role", ["police", "thief"])
def test_the_poll_interval_is_configured_not_hardcoded(role):
    """How often we ask 'is the turn done yet' is a tunable, so it lives in config."""
    interval = load_network_settings(role).poll_interval_sec

    assert isinstance(interval, float)
    assert 0 < interval < load_config("config/police/game.json").watchdog_timeout_sec
