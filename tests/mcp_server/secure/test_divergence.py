"""The pure divergence detector (D2 mirrored local truth).

Kept apart from the match tests: this is a plain function over two
payloads, and it must be provably able to REPORT a disagreement, not
merely stay silent when there is none.
"""

from scripts.match_loop import divergence


def test_divergence_is_silent_when_the_peers_agree():
    payload = {"turn_count": 1, "cop_position": (0, 0), "thief_position": (3, 3),
               "captured": False, "is_terminated": False}

    assert divergence([payload, dict(payload)]) is None


def test_divergence_tolerates_json_lists_against_tuples():
    """Positions arrive as tuples in-process and as lists over the wire."""
    mine = {"turn_count": 1, "cop_position": (0, 0), "thief_position": (3, 3),
            "captured": False, "is_terminated": False}
    theirs = dict(mine, cop_position=[0, 0], thief_position=[3, 3])

    assert divergence([mine, theirs]) is None


def test_divergence_names_the_field_that_disagrees():
    mine = {"turn_count": 1, "cop_position": (0, 0), "thief_position": (3, 3),
            "captured": False, "is_terminated": False}
    theirs = dict(mine, thief_position=(2, 2))

    clash = divergence([mine, theirs])

    assert clash is not None and "thief_position" in clash
