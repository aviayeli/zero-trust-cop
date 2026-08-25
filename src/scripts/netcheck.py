"""Probe an opponent's endpoint BEFORE committing a series to it (PRD_11).

``connect_and_play`` retries a failing open for the whole ``--wait-minutes``
window -- right for a launch, useless as a diagnostic: a typo in their URL, a
dead tunnel, and a peer disagreeing on ``num_games`` all present as the same
thirty-minute silence.

Four checks, in dependency order, each running only if the one before it
passed: reporting "terms disagree" against a down peer is how an operator ends
up editing a ``game.json`` that was already correct. This is the KERNEL --
the checks, driven by a peer handle the caller supplies; transport and command
line are in ``scripts.netcheck_cli``, split at the 150-line limit.

READ-ONLY, and the handshake is the part that needs saying. ``negotiate`` is
the only tool here carrying terms, and it OPENS a sub-game. The probe sends
``sub_game_number = 0``, which appears in no schedule either side plays
(``role_schedule`` is 1-indexed), so it cannot collide with a real one. No
turn is pushed, no audit submitted, no artifact written.
"""

from __future__ import annotations

import contextlib
from secrets import token_hex

from mcp_server import interop
from mcp_server.negotiate_reply import _first_difference, _require_acceptance

REQUIRED_TOOLS = ("negotiate", "receive_turn", "submit_audit",
                  "receive_control")
PROBE_SUB_GAME = 0  # outside the 1-indexed schedule either side plays
_REPLY_TERMS = ("terms", "nonce", "signature")
_NONCE_BYTES = 16


def _verdict(check: str, ok: bool, detail: str) -> dict:
    return {"check": check, "ok": ok, "detail": detail}


def _reason(failure: BaseException) -> str:
    """The LEAF cause, named. anyio wraps a refused connection in a task group
    whose str() names nothing, and a down tunnel is the likeliest failure."""
    while isinstance(failure, BaseExceptionGroup) and failure.exceptions:
        failure = failure.exceptions[0]
    return f"{type(failure).__name__}: {failure}"


def _fatal(failure: BaseException) -> bool:
    # An interrupt is ours, never a verdict about the opponent.
    return isinstance(failure, (KeyboardInterrupt, SystemExit))


def exit_code(report: list) -> int:
    """0 only when every check that ran passed, so this can gate a launch."""
    return 0 if report and all(check["ok"] for check in report) else 1


def missing_tools(listed) -> tuple:
    """Which reference-v3 tools this peer does not serve."""
    return tuple(t for t in REQUIRED_TOOLS if t not in set(listed))


async def probe(open_peer, our_terms: dict, identity: dict, our_role: str,
                nonce_source=None) -> list:
    """Run the checks against one endpoint and return their verdicts."""
    async with contextlib.AsyncExitStack() as stack:
        try:
            peer = await stack.enter_async_context(open_peer())
        except BaseException as failure:
            # BaseException: anyio wraps their 502 in a task group.
            if _fatal(failure):
                raise
            return [_verdict("reachable", False, _reason(failure))]

        report = [_verdict("reachable", True, "MCP session initialised"),
                  await _surface(peer)]
        if not report[-1]["ok"]:
            return report
        return report + await _handshake(peer, our_terms, identity, our_role,
                                         nonce_source)


async def _surface(peer) -> dict:
    """Does this peer serve the reference-v3 tools at all?"""
    try:
        listed = await peer.list_tools()
    except BaseException as failure:
        if _fatal(failure):
            raise
        return _verdict("surface", False, _reason(failure))
    absent = missing_tools(listed)
    if absent:
        return _verdict("surface", False, f"not served: {', '.join(absent)}")
    return _verdict("surface", True,
                    f"all {len(REQUIRED_TOOLS)} reference-v3 tools served")


async def _handshake(peer, our_terms, identity, our_role, nonce_source) -> list:
    """Open a probe handshake, then judge the terms it carries back."""
    nonce = (nonce_source or (lambda: token_hex(_NONCE_BYTES)))()
    try:
        reply = await peer.call("negotiate", message={
            "terms": dict(our_terms),
            "nonce": nonce,
            "signature": interop.terms_signature(our_terms, nonce),
            "identity": dict(identity),
            "sub_game_number": PROBE_SUB_GAME,
            "role": our_role,
        })
    except BaseException as failure:
        if _fatal(failure):
            raise
        return [_verdict("handshake", False, _reason(failure))]

    try:
        # All three live spellings of yes; refusing an unfamiliar one
        # would report a healthy peer as dead.
        _require_acceptance(reply)
    except RuntimeError as refusal:
        return [_verdict("handshake", False, str(refusal))]
    return [_verdict("handshake", True, "accepted"),
            _terms_verdict(reply, our_terms)]


def _terms_verdict(reply: dict, our_terms: dict) -> dict:
    """Compare their terms with ours -- or say plainly that we could not.

    A bare ``{"accepted": true}`` is a real acceptance carrying nothing to
    compare; reporting it as a pass would assert a check that never ran."""
    if any(key not in reply for key in _REPLY_TERMS):
        return _verdict("terms", False, "UNVERIFIED: their acceptance carried "
                        f"no {'/'.join(_REPLY_TERMS)}; nothing was compared")
    if interop.terms_signature(reply["terms"], reply["nonce"]) != reply["signature"]:
        return _verdict("terms", False, "their signature does not verify over "
                        "the terms sent; want SHA256(canonical(terms)|nonce)")
    disagreement = _first_difference(our_terms, reply["terms"])
    if disagreement:
        return _verdict("terms", False, disagreement)
    return _verdict("terms", True,
                    f"all {len(our_terms)} agreed terms value-equal")


def main(argv=None):
    """Re-exported so ``python -m scripts.netcheck`` is the runnable name."""
    from scripts.netcheck_cli import main as _main
    return _main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
