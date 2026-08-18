"""Commit-reveal primitive for zero-trust P2P move exchange.

The two peers move simultaneously with no trusted arbiter, so neither may be
able to choose its move after learning the opponent's. Each peer publishes
h_commit — SHA256(State || Move || Intent || Nonce), binding the move and the
honesty flag to a fresh secret nonce — and reveals (move, intent, nonce) only once both commitments have been
exchanged. The opponent recomputes the digest to confirm the revealed move is
the one that was committed.

Scope: this proves a revealed move matches an earlier commitment by *whoever
holds the nonce*. It does not, on its own, establish WHO submitted it. That is
layered on top by ``identity.py``, whose Ed25519 signature over
``{role, turn, h_commit}`` is verified on BOTH the commit and the reveal
(``submissions.py``), so peer identity IS authenticated at the gate. Nothing
here encrypts anything in transit -- the wire is signed, not confidential
(PLAN.md §10.6).
"""

import hashlib
import json
from secrets import compare_digest, token_hex

# Nonce length in bytes (128 bits of unpredictability). Named rather than
# inlined so it can be lifted into config without touching any call site.
_NONCE_BYTES = 16


def canonical_json(payload: dict) -> bytes:
    """Serialize a payload to the project's canonical JSON wire format."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def positional_payload(state: str, move: str, intent: str, nonce: str) -> bytes:
    """The exact byte string both peers hash: ``State || Move || Intent || Nonce``.

    Rulebook 5.3 specifies literal positional concatenation, so that is what
    is emitted. Any divergence here silently breaks interop between the two
    groups' implementations -- and cannot be caught by either group alone,
    since each verifies against its own serialization.

    Caveat inherent to the specified format: plain concatenation has no field
    delimiters, so boundaries are positional only. The trailing nonce is
    fixed-length and ``intent`` is one of two known words, which bounds the
    ambiguity in practice, but a delimited form would be strictly safer.
    """
    return f"{state}{move}{intent}{nonce}".encode()


def _legacy_payload(state: str, move: str, intent: str, nonce: str) -> bytes:
    """The superseded sorted-key JSON form, retained for verification only.

    Artifacts sealed before the 5.3 alignment must stay verifiable; nothing
    emits this form any more.
    """
    return canonical_json(
        {"state": state, "move": move, "intent": intent, "nonce": nonce}
    )


def commit(state: str, move: str, intent: str) -> tuple[str, str]:
    """Bind (state, move, intent) to a freshly generated secret nonce.

    Returns (h_commit, nonce). Publish h_commit to the opponent; keep nonce
    secret until the reveal phase. The nonce is what hides the move: without
    it, the digest of a small move set would be trivially brute-forced.
    """
    nonce = token_hex(_NONCE_BYTES)
    payload = positional_payload(state, move, intent, nonce)
    return hashlib.sha256(payload).hexdigest(), nonce


def verify(
    state: str,
    move: str,
    intent: str,
    nonce: str,
    h_commit: str,
    *,
    allow_legacy: bool = False,
) -> bool:
    """True if the revealed values reproduce h_commit.

    Compares with secrets.compare_digest rather than ==, which would leak
    through timing how many leading characters matched and hand an opponent a
    search gradient toward a colliding reveal.

    ``allow_legacy`` additionally accepts the superseded sorted-key JSON form
    and DEFAULTS OFF. Nothing has emitted that form since the 5.3 alignment,
    so on the live wire accepting it only widens what a peer may commit
    under: two encodings of the same fields, one of which this project no
    longer speaks. Its single legitimate reader is the verification of
    artifacts sealed before the alignment, which must not become
    unverifiable -- so the fallback is GATED rather than deleted.

    The flag is keyword-only so that a sixth positional argument, at a call
    site written years from now, cannot silently re-open the wire.
    """
    builders = [positional_payload]
    if allow_legacy:
        builders.append(_legacy_payload)
    for build in builders:
        expected = hashlib.sha256(build(state, move, intent, nonce)).hexdigest()
        if compare_digest(expected, h_commit):
            return True
    return False
