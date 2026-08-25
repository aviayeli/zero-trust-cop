"""Both our roles behind ONE port and one ``/mcp`` route (PRD_11b).

Two tunnels means handing an opponent two URLs plus a rule for choosing
between them -- dial the endpoint serving the role you are playing AGAINST --
and getting it backwards is not a crash. ``opponent_endpoints`` spells out the
cost: a whole sub-game pushed at a peer playing the same side, a pairing
collision on their end, silence on ours, thirty-five steps before either side
finds out. One endpoint deletes the rule.

THE ROUTING KEY IS OURS, NOT THEIRS, and the code forces that rather than
preference choosing it. ``negotiate`` -- the message that OPENS a sub-game --
may legally omit ``role`` (``wire_v3_session.NEGOTIATE_OPTIONAL``), so it
cannot be routed by what the opponent claims. And deriving our side from
theirs would make ``pairing.pairing_refusal`` tautological: it refuses when
``their_role == our_role``, which can never fire if ours is computed from
theirs. That check is the only place a mispairing is caught.

So this holds an ACTIVE ROLE of its own. ``claims_runner`` already walks
``role_schedule`` and knows which side we play each sub-game; it sets this,
and the opponent's claim is only ever CHECKED against it.

COMPOSITION, NOT REWRITE. ``create_app`` binds a role into nine things --
policy, gate, episode, match_state, keys, identity, inbox, own_role and the
``our_role`` inside ``negotiate``. Rather than unpick that, this builds BOTH
peers exactly as they are built today and dispatches to one of them. A
``FastMCP`` does not bind a socket until it is run, so the two inner apps cost
only their own state, and the split-port topology is provably untouched: it is
the same code reached the same way.
"""

from __future__ import annotations

from types import SimpleNamespace

from mcp.server.fastmcp import FastMCP

from mcp_server.server import PEER_ROLES, create_app

REFERENCE_TOOLS = ("negotiate", "receive_turn", "submit_audit",
                   "receive_control")
# The tools whose envelope names its origin, and may therefore be checked for
# a self-dial. `negotiate` is absent on purpose: `role` is optional there.
_SENDER_CHECKED = ("receive_turn", "submit_audit", "receive_control")
_ENVELOPE = {"receive_turn": "message", "submit_audit": "payload",
             "receive_control": "message", "negotiate": "message"}


def _self_dial(tool: str, envelope, active: str) -> str | None:
    """Refuse a message from the side WE are playing, or None.

    On two ports this could not arrive -- our cop's port was not our thief's.
    On one port it is exactly the shape a self-dial takes, with
    ``--opponent-url`` aimed at our own tunnel. ``await_turn`` already raises
    when our own turn appears in our own inbox; refusing here keeps it out of
    the inbox altogether.
    """
    if tool not in _SENDER_CHECKED or not isinstance(envelope, dict):
        return None
    if envelope.get("sender") != active:
        return None
    return (
        f"self-dial: this message declares sender {active!r}, which is the "
        "side WE are playing this sub-game. Both our roles answer this one "
        "endpoint, so an --opponent-url aimed at our own tunnel reaches us "
        "as our own opponent."
    )


def create_unified_app(config_root=None, port: int | None = None):
    """Serve both our peers on one port; dispatch on the side WE play.

    Returns a namespace carrying the four reference-v3 tools, the ``peers``
    they dispatch to (the same ``{role: app}`` mapping the runner already
    takes), ``set_active`` and the bound ``port``.

    Raises:
        ValueError: no unified port is configured and none was passed. A
            defaulted port would be the hardcoded tunable the constitution
            exists to prevent.
    """
    peers = {role: create_app(role, config_root=config_root)
             for role in PEER_ROLES}
    binding = peers["police"].binding
    bound = port if port is not None else binding.unified_port
    if not bound:
        raise ValueError(
            "no unified_port configured in [network]; add it to "
            "config/<role>/game.toml or pass port= explicitly"
        )

    state = {"active": PEER_ROLES[0]}

    def set_active(role: str) -> None:
        """Name the side we play THIS sub-game. The only way dispatch moves."""
        if role not in PEER_ROLES:
            raise ValueError(f"role must be one of {PEER_ROLES}, got {role!r}")
        state["active"] = role

    mcp = FastMCP("zero-trust-cop-unified", host=binding.host, port=bound,
                  log_level="ERROR")
    app = SimpleNamespace(mcp=mcp, peers=peers, port=bound,
                          set_active=set_active,
                          active=lambda: state["active"])

    for name in REFERENCE_TOOLS:
        setattr(app, name, _register(mcp, name, peers, state))
    return app


def _register(mcp, name: str, peers: dict, state: dict):
    """Register one dispatching tool and return its callable.

    The tool keeps the wire's own parameter name -- FastMCP derives the public
    JSON schema from the signature, so ``message`` and ``payload`` are part of
    the contract and a rename here is a protocol change.
    """
    key = _ENVELOPE[name]

    async def dispatch(envelope: dict) -> dict:
        active = state["active"]
        refusal = _self_dial(name, envelope, active)
        if refusal is not None:
            return {"status": "refused", "reason": refusal}
        return await getattr(peers[active], name)(**{key: envelope})

    dispatch.__name__ = name
    dispatch.__doc__ = (
        f"{name}, served for whichever side we are playing this sub-game. "
        "See mcp_server.reference_tools for the behaviour itself."
    )
    # Re-declared with the wire's parameter name so the published schema
    # matches the split-port surface exactly.
    if key == "message":
        async def tool(message: dict) -> dict:
            return await dispatch(message)
    else:
        async def tool(payload: dict) -> dict:
            return await dispatch(payload)

    tool.__name__ = name
    tool.__doc__ = dispatch.__doc__
    mcp.tool()(tool)
    return tool
