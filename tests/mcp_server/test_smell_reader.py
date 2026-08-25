"""Reading an inbound grid — THEIR serialiser's output, not ours (SPEC 5).

Split from `test_smell_trail.py`, which covers what we emit. Everything here
is about tolerating what arrives: a key we cannot parse is a reason to learn
nothing from that cell, never a reason to end a live match, and ties break
the way the kit's `hottest` breaks them so a replay agrees across teams.
"""


from mcp_server.smell_trail import strongest_cell


def test_a_grid_with_no_trace_reads_as_no_cell():
    assert strongest_cell({}) is None


def test_a_malformed_key_is_ignored_rather_than_raising():
    """Their grid is THEIR serialiser's output; a bad key must not kill a match."""
    assert strongest_cell({"not-a-cell": 0.9}) is None
