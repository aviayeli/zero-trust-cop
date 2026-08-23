"""A league match runs ONE of our peers, not both.

The local simulation spawns police and thief together and plays them against
each other. Against another group we run only our own half — the opposing peer
is their process, on their machine, behind their tunnel. Starting both would
bind the port the opponent's traffic is meant to reach and quietly play a
second local game instead.
"""

from pathlib import Path

import pytest

from mcp_server.keygen import ensure_keys
from scripts.peer_processes import port_is_open, running_peers


@pytest.fixture
def isolated_root(secure_config_root):
    """A complete peer workspace with its own throwaway signing keys."""
    for pub in Path(secure_config_root).glob("*/peers/*.pub"):
        pub.unlink()
    ensure_keys(secure_config_root)
    return secure_config_root


@pytest.mark.parametrize("role,absent", [("police", "thief"), ("thief", "police")])
def test_only_the_requested_peer_is_started(isolated_root, role, absent):
    with running_peers(isolated_root, roles=(role,)) as bindings:
        assert set(bindings) == {role}
        assert port_is_open(bindings[role].dial_host, bindings[role].my_port)


def test_the_opponents_port_is_left_free_for_their_tunnel(isolated_root):
    """Our process must not occupy the port the remote peer is dialling."""
    with running_peers(isolated_root, roles=("police",)) as bindings:
        police = bindings["police"]
        assert port_is_open(police.dial_host, police.my_port)
        assert set(bindings) == {"police"}


def test_a_single_peer_is_still_torn_down_on_failure(isolated_root):
    """A crashed league match must not leave our listener bound."""
    seen = {}

    with pytest.raises(RuntimeError):
        with running_peers(isolated_root, roles=("police",)) as bindings:
            seen.update(bindings)
            raise RuntimeError("match blew up")

    police = seen["police"]
    assert not port_is_open(police.dial_host, police.my_port, timeout=0.5)


def test_both_peers_still_start_by_default(isolated_root):
    """The local simulation must keep working with no argument change."""
    with running_peers(isolated_root) as bindings:
        assert set(bindings) == {"police", "thief"}
