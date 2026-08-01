"""The published declaration must point at the ports the peers actually bind.

These were SWAPPED: the declaration advertised cop on 8802 and thief on 8801
while the peers bound police(cop) 8801 and thief 8802, so any external peer
following our own Step-0 artifact would have talked to the wrong role.
"""

import pytest

from mcp_server.declaration import build_declaration
from mcp_server.transport import load_transport_settings

_ENGINE_ROLE = {"police": "cop", "thief": "thief"}


@pytest.mark.parametrize("peer_role", ["police", "thief"])
def test_the_declaration_advertises_the_port_the_peer_binds(peer_role):
    binding = load_transport_settings(peer_role)
    advertised = build_declaration()["mcp_servers"][_ENGINE_ROLE[peer_role]]

    assert advertised == f"http://{binding.host}:{binding.port}/mcp"


def test_the_two_advertised_endpoints_differ():
    servers = build_declaration()["mcp_servers"]

    assert servers["cop"] != servers["thief"]
