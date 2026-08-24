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
        "group_name": declared["group_name"],
        "members": declared["members"],
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
    tools = register_reference_tools(
        mcp, inbox, terms, lambda: identity_block(role, config_root),
        lambda: token_hex(_NONCE_BYTES),
    )
    return SimpleNamespace(inbox=inbox, terms=terms, tools=tools)
