"""A wildcard BIND address is not a DIAL address.

Exposing a peer for league play means binding ``0.0.0.0`` so a tunnel can
forward to it. But ``0.0.0.0`` names no host to connect TO: it is "every
interface I listen on", and handing it to a client is a category error that
happens to work on Linux and fails elsewhere.

Both call sites that dial a peer (``run_local_mcp_match.peer_url`` and
``peer_processes.wait_for_port``) previously reused the bind host verbatim, so
opening the peers to the network silently pointed the local match at
``http://0.0.0.0:8802/mcp``. The translation is made explicit here.
"""

import pytest

from mcp_server.transport import dial_host, load_network_settings


@pytest.mark.parametrize(
    "bound,expected",
    [
        ("0.0.0.0", "127.0.0.1"),
        ("::", "::1"),
        ("", "127.0.0.1"),
    ],
)
def test_a_wildcard_bind_dials_loopback(bound, expected):
    assert dial_host(bound) == expected


@pytest.mark.parametrize("bound", ["127.0.0.1", "192.168.1.5", "peer.example"])
def test_a_concrete_host_is_dialled_verbatim(bound):
    """Only the wildcards are translated; a real host must not be rewritten."""
    assert dial_host(bound) == bound


@pytest.mark.parametrize("role", ["police", "thief"])
def test_the_peers_bind_the_wildcard_for_league_play(role):
    """Blocker A: a tunnelled opponent cannot reach a loopback-only listener."""
    assert load_network_settings(role).host == "0.0.0.0"


@pytest.mark.parametrize("role", ["police", "thief"])
def test_an_exposed_peer_is_still_dialled_over_loopback(role):
    """Binding publicly must not change where OUR OWN client connects."""
    assert load_network_settings(role).dial_host == "127.0.0.1"
