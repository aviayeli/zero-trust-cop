"""The published declaration must point at the ports the peers actually bind.

These were SWAPPED: the declaration advertised cop on 8802 and thief on 8801
while the peers bound police(cop) 8801 and thief 8802, so any external peer
following our own Step-0 artifact would have talked to the wrong role.
"""

from urllib.parse import urlsplit

import pytest

from mcp_server.declaration import build_declaration
from mcp_server.transport import load_network_settings

_ENGINE_ROLE = {"police": "cop", "thief": "thief"}


@pytest.mark.parametrize("peer_role", ["police", "thief"])
def test_the_declaration_advertises_the_port_the_peer_binds(peer_role):
    """The PORT is the claim under test, deliberately not the host.

    A peer exposed for league play binds ``0.0.0.0`` and is advertised at a
    tunnel URL, so pinning the host here would fail the moment the thing it
    describes actually happens. The role/port swap this file exists to catch
    is visible in the port alone.
    """
    binding = load_network_settings(peer_role)
    advertised = build_declaration()["mcp_servers"][_ENGINE_ROLE[peer_role]]
    port = urlsplit(advertised).port

    if port is None:
        # A tunnel URL carries no explicit port -- exactly "the moment the
        # thing it describes actually happens", which this file's own
        # docstring anticipated for the host and not for the port. There is
        # no port to compare, so the swap guard falls to the checks below.
        assert urlsplit(advertised).scheme in ("http", "https")
        assert urlsplit(advertised).hostname
        return
    assert port == binding.my_port


def test_the_two_advertised_endpoints_differ():
    servers = build_declaration()["mcp_servers"]

    assert servers["cop"] != servers["thief"]


def test_a_swapped_pair_of_tunnels_is_NOT_detectable_here(monkeypatch):
    """Stated so the residual risk is recorded rather than assumed away.

    Loopback endpoints carry the port, so a role/port swap is caught above.
    Tunnel hostnames are opaque: nothing in the declaration says which peer is
    behind `luxury-pregnancy-wilder`. The control is that `league_up.sh`
    advertises the URL it just created for that role, rather than an operator
    pasting two URLs by hand.
    """
    swapped = {"cop": "https://b.ngrok-free.dev/mcp",
               "thief": "https://a.ngrok-free.dev/mcp"}

    # Both are well-formed and distinct; no check here can tell them apart.
    assert swapped["cop"] != swapped["thief"]
    assert all(urlsplit(url).hostname for url in swapped.values())
