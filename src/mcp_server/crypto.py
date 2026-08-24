"""Commit-reveal primitive for zero-trust P2P move exchange.

The two peers move simultaneously with no trusted arbiter, so neither may be
able to choose its move after learning the opponent's. Each peer publishes
h_commit -- SHA256(canonical_json({state, move, intent}) | nonce), binding the
move and the honesty flag to a fresh secret nonce -- and reveals
(move, intent, nonce) only once both commitments have been exchanged. The
opponent recomputes the digest to confirm the revealed move is the one that
was committed.

The construction is the league's REFERENCE form (``mcp_server.interop``). The
book publishes three inconsistent ones -- its ch.5 listing seals the nonce
inside the object, an audit snippet hashes only ``nonce|move`` -- and this is
the one the lecturer's own tooling runs, the one the community interop kit
pins with shared vectors, and the only one of the three that binds the whole
record: the audit-snippet form leaves ``state`` and ``intent`` rewritable
after the fact. It also delimits the fields that the previously emitted
positional concatenation ran together (PLAN.md §10.2, now closed).

Scope: this proves a revealed move matches an earlier commitment by *whoever
holds the nonce*. It does not, on its own, establish WHO submitted it. That is
layered on top by ``identity.py``, whose Ed25519 signature over
``{role, turn, h_commit}`` is verified on BOTH the commit and the reveal
(``submissions.py``), so peer identity IS authenticated at the gate. Nothing
here encrypts anything in transit -- the wire is signed, not confidential
(PLAN.md §10.6).
"""

import hashlib
from secrets import compare_digest, token_hex

from mcp_server.interop import NONCE_SEPARATOR, canonical_str

# Nonce length in bytes (128 bits of unpredictability). Named rather than
# inlined so it can be lifted into config without touching any call site.
_NONCE_BYTES = 16


def canonical_json(payload: dict) -> bytes:
    """Serialize a payload to the project's canonical JSON wire format.

    ``ensure_ascii=False``: non-ASCII is emitted as native UTF-8, never
    ``\\uXXXX``-escaped. An implementation that escapes produces a different
    hash for any payload carrying Hebrew or emoji, and since the opponent
    re-hashes our revealed payloads at audit, that mismatch reads as tampering
    and voids the match for BOTH sides.
    """
    return canonical_str(payload).encode("utf-8")


def reference_payload(state: str, move: str, intent: str, nonce: str) -> bytes:
    """The exact bytes both peers hash: ``canonical({state,move,intent}) | nonce``.

    The nonce is appended to the canonical STRING rather than sealed inside
    the hashed object, and the separator is a SINGLE pipe (U+007C) -- not a
    bare concatenation, not ``||``. All three read plausibly in prose, only
    one reproduces the league vectors, and the wrong ones fail every handshake
    with nothing to go on but "digest mismatch".
    """
    canonical = canonical_str({"state": state, "move": move, "intent": intent})
    return f"{canonical}{NONCE_SEPARATOR}{nonce}".encode("utf-8")


def positional_payload(state: str, move: str, intent: str, nonce: str) -> bytes:
    """The superseded ``State || Move || Intent || Nonce`` form (Rulebook 5.3).

    Retained for verification only; nothing emits it since the alignment on
    the reference form. Its documented weakness is why: plain concatenation
    has no field delimiters, so ``("ab", "c")`` and ``("a", "bc")`` share one
    preimage. The trailing nonce is fixed-length and ``intent`` was one of two
    known words, which bounded the ambiguity in practice -- but only bounded it.
    """
    return f"{state}{move}{intent}{nonce}".encode("utf-8")


def _nonce_sealed_payload(state: str, move: str, intent: str, nonce: str) -> bytes:
    """The book ch.5 listing form: nonce sealed INSIDE the canonical object.

    The oldest of our three encodings, and the first to be superseded. Kept
    verifiable for artifacts sealed under it.
    """
    return canonical_json(
        {"state": state, "move": move, "intent": intent, "nonce": nonce}
    )


# Ordered newest-first: the emitted form, then the superseded ones a verifier
# may opt into. Nothing outside ``verify`` may reach the legacy builders.
_LEGACY_BUILDERS = (positional_payload, _nonce_sealed_payload)


def commit(state: str, move: str, intent: str) -> tuple[str, str]:
    """Bind (state, move, intent) to a freshly generated secret nonce.

    Returns (h_commit, nonce). Publish h_commit to the opponent; keep nonce
    secret until the reveal phase. The nonce is what hides the move: without
    it, the digest of a small move set would be trivially brute-forced.
    """
    nonce = token_hex(_NONCE_BYTES)
    payload = reference_payload(state, move, intent, nonce)
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

    ``allow_legacy`` additionally accepts the two superseded encodings and
    DEFAULTS OFF. Nothing has emitted either since the alignment on the
    reference form, so on the live wire accepting them only widens what a peer
    may commit under: three encodings of the same fields, two of which this
    project no longer speaks. Their single legitimate reader is the
    verification of artifacts sealed earlier, which must not become
    unverifiable -- so the fallbacks are GATED rather than deleted.

    The flag is keyword-only so that a sixth positional argument, at a call
    site written years from now, cannot silently re-open the wire.
    """
    builders = [reference_payload]
    if allow_legacy:
        builders.extend(_LEGACY_BUILDERS)
    for build in builders:
        expected = hashlib.sha256(build(state, move, intent, nonce)).hexdigest()
        if compare_digest(expected, h_commit):
            return True
    return False
