"""Assemble the reference-v3 half of a peer's tool surface.

Split from ``server.py`` at the composition seam: the server stays a
composition root and this module knows what reference-v3 needs to exist --
the agreed terms, the identity block, and the inbox an inbound turn lands in.
``reference_tools`` holds what the tools DO; this holds what they are wired to.
"""

from __future__ import annotations

import json
from secrets import token_hex
from types import SimpleNamespace

from mcp_server.declaration import build_declaration
from mcp_server.reference_tools import register_reference_tools
from mcp_server.terms import terms_from_config

WIRE_SHAPE = "reference-v3"
_NONCE_BYTES = 16


def identity_block(role: str, config_root: str | None = None) -> dict:
    """What rides in ``negotiate`` under ``identity``.

    There is no step-0 TOOL and no step-0 turn on this wire: the hardware and
    model declaration travels here, and the sealed step-0 record is disclosed
    inside ``submit_audit``. A peer that waits for a ``declare_step0`` call
    waits forever.
    """
    declared = build_declaration(config_root)
    return {
        # BOTH spellings, same value. ZeroOne0 refused our handshake for want
        # of `group_id`; we sent only `group_name`. The SPEC requires an
        # identity block and pins no field name, so neither side was wrong
        # and both were stuck. Our own `_uid_for` reads `group_id` too, so
        # the uid cross-check never ran in either direction.
        # `identity` is a negotiate EXTRA, outside the flat signed terms:
        # carrying both changes no hash and breaks no signature.
        "group_id": declared["group_name"],
        "group_name": declared["group_name"],
        "members": declared["members"],
        # The opponent records what the GREETING carries, not what our
        # artifact says. Carrying it only in the declaration would have the
        # attachment read 2 while the handshake read nothing, and a reader
        # that defaults a missing field to 0 files the disagreement.
        "counted_games_played": declared["counted_games_played"],
        "wire_shape": WIRE_SHAPE,
        "role": role,
    }


def build(mcp, role: str, config_path: str, config_root: str | None = None):
    """Register the reference-v3 tools and return them plus their state.

    The inbox is this peer's own: the transport is symmetric push, so each
    side calls the other's ``receive_turn`` and polls the inbox it owns.
    """
    with open(config_path, encoding="utf-8") as contract:
        terms = terms_from_config(json.load(contract))
    inbox: list = []
    # Their disclosed chains, kept for the log: `receive_turn` carries a
    # digest, and `submit_audit` is the only place their play is revealed.
    audits: list = []
    # Returned as well as injected: the RUNNER needs the same identity block
    # to open a handshake, and rebuilding it there would be a second place
    # for the declaration to drift.
    identity = lambda: identity_block(role, config_root)  # noqa: E731
    tools = register_reference_tools(
        mcp, inbox, audits, terms, identity,
        lambda: token_hex(_NONCE_BYTES), role,
    )
    return SimpleNamespace(inbox=inbox, audits=audits, terms=terms,
                           tools=tools, identity=identity)
