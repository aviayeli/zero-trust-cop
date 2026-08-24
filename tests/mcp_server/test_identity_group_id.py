"""The greeting must name the group in BOTH spellings (PRD_10 10.29).

ZeroOne0 refused our handshake because our greeting carries no `group_id` —
neither top-level nor under `identity`. We send `group_name`; their parser
reads `group_id`. The kit's SPEC requires an `identity` block and does not
pin the field name, so neither side is wrong and both are stuck.

Our own code had the mismatch internally: `reference_negotiate._uid_for`
looks for THEIR `group_id`, while `identity_block` sends OUR `group_name`.
The uid cross-check therefore never ran in either direction.

`identity` is a negotiate EXTRA, outside the flat signed terms, so carrying
both keys changes no hash and breaks no signature. Same value, two names.
"""

from mcp_server.reference_surface import identity_block


def test_the_greeting_carries_group_id():
    assert identity_block("police")["group_id"] == "aviayeli"


def test_it_still_carries_group_name():
    """Ours and every artifact we have written reads `group_name`."""
    assert identity_block("police")["group_name"] == "aviayeli"


def test_both_names_hold_the_same_value():
    identity = identity_block("thief")

    assert identity["group_id"] == identity["group_name"]


def test_the_rest_of_the_block_is_unchanged():
    identity = identity_block("thief")

    assert identity["role"] == "thief"
    assert identity["wire_shape"] == "reference-v3"
    assert identity["members"]
