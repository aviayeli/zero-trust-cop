"""Two endpoints, because the opponent may run two processes (PRD_10 10.21).

ali-ahm1 served both roles on one endpoint and the role rode in the message,
so a single `--opponent-url` was enough. rstabcde run cop and thief as two
separate processes on two tunnels — and the sides SWAP every sub-game, so the
endpoint we push to changes with them.

The mapping is the part worth stating: we push to the endpoint serving the
role THEY are playing, which is the OPPOSITE of ours. In a sub-game where we
are police, their thief endpoint is the one that must receive our turns.
Getting this inverted is not a crash — it is a whole sub-game pushed at a
peer that is playing the same side as us, which reads on their end as a
pairing collision and on ours as silence.
"""

import pytest

from scripts.opponent_endpoints import endpoint_for, resolve_endpoints

COP = "https://their-cop.ngrok-free.dev/mcp"
THIEF = "https://their-thief.ngrok-free.dev/mcp"


def test_one_endpoint_serves_both_roles():
    """The single-process opponent. One URL, used whichever side we play."""
    endpoints = resolve_endpoints(single=COP, cop=None, thief=None)

    assert endpoint_for(endpoints, "police") == COP
    assert endpoint_for(endpoints, "thief") == COP


def test_two_endpoints_are_chosen_by_the_side_THEY_play():
    endpoints = resolve_endpoints(single=None, cop=COP, thief=THIEF)

    assert endpoint_for(endpoints, "police") == THIEF, "we are cop, so they are thief"
    assert endpoint_for(endpoints, "thief") == COP, "we are thief, so they are cop"


def test_naming_only_one_of_the_two_is_refused():
    """Half a mapping plays half a series into a void that answers 200."""
    with pytest.raises(ValueError, match="both"):
        resolve_endpoints(single=None, cop=COP, thief=None)


def test_naming_no_endpoint_at_all_is_refused():
    with pytest.raises(ValueError, match="opponent"):
        resolve_endpoints(single=None, cop=None, thief=None)


def test_mixing_the_single_form_with_the_split_form_is_refused():
    """Two answers to the same question, and no way to tell which was meant."""
    with pytest.raises(ValueError, match="either"):
        resolve_endpoints(single=COP, cop=COP, thief=THIEF)


def test_an_unknown_role_is_refused_rather_than_defaulted():
    endpoints = resolve_endpoints(single=None, cop=COP, thief=THIEF)

    with pytest.raises(ValueError, match="role"):
        endpoint_for(endpoints, "detective")
