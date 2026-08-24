"""Assemble every surface a peer serves besides its own native one.

``server.py`` stays a composition root; this module knows which dialects
exist, which are default, and which have to be asked for.

Two are always on -- the league's reference-v3 surface rides beside our own
authenticated commit/reveal tools, because an opponent may speak either and a
peer that answers only one is unreachable to half the league.

The push dialect is NOT. It accepts unauthenticated submissions: its
``receive_commit`` carries no signature, so nothing binds a move to a peer
identity, and its ``receive_reveal`` carries no nonce, so nothing binds a
reveal to its commitment while the sub-game runs. Registering it silently
would widen the live wire in exactly the way our own dialect exists to
prevent, so it appears only when an operator names it (PRD_09 FR5).
"""

from __future__ import annotations

from types import SimpleNamespace

from mcp_server import reference_surface
from mcp_server.push_audit import PushStore
from mcp_server.push_tools import register_push_tools

# Optional extra surfaces, by name. None -- the default -- is the shipped
# wire: the two authenticated dialects and nothing else.
DIALECTS = ("push",)


def build(mcp, role: str, config_path: str, config_root=None, dialect=None):
    """Register every surface this peer serves and return them with state.

    Raises:
        ValueError: an unknown dialect name. Refused rather than ignored --
            silently dropping a typo would leave the operator believing a
            dialect is on while its tools are absent from ``tools/list``.
    """
    if dialect is not None and dialect not in DIALECTS:
        raise ValueError(
            f"dialect must be one of {DIALECTS} or None, got {dialect!r}"
        )

    reference = reference_surface.build(mcp, role, config_path, config_root)
    push_store = PushStore()
    push = register_push_tools(mcp, push_store) if dialect == "push" else {}

    return SimpleNamespace(
        inbox=reference.inbox,
        audits=reference.audits,
        terms=reference.terms,
        identity=reference.identity,
        push_store=push_store,
        tools={**reference.tools, **push},
    )
