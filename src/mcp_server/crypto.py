"""Commit-reveal primitive for zero-trust P2P move exchange.

The two peers move simultaneously with no trusted arbiter, so neither may be
able to choose its move after learning the opponent's. Each peer publishes
h_commit — a SHA-256 digest binding (state, move, intent) to a fresh secret
nonce — and reveals (move, intent, nonce) only once both commitments have been
exchanged. The opponent recomputes the digest to confirm the revealed move is
the one that was committed.

Scope: this proves a revealed move matches an earlier commitment by *whoever
holds the nonce*. It does NOT authenticate who submitted it, and it does not
encrypt anything in transit. Peer identity remains unauthenticated.
"""

import hashlib
import json
from secrets import compare_digest, token_hex

# Nonce length in bytes (128 bits of unpredictability). Named rather than
# inlined so it can be lifted into config without touching any call site.
_NONCE_BYTES = 16


def _canonical_payload(state: str, move: str, intent: str, nonce: str) -> bytes:
    """The exact byte string both peers hash.

    Any divergence here silently breaks interop between the two groups'
    implementations, so the serialization is pinned: sorted keys and no
    whitespace, giving one canonical form per payload.
    """
    return json.dumps(
        {"state": state, "move": move, "intent": intent, "nonce": nonce},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def commit(state: str, move: str, intent: str) -> tuple[str, str]:
    """Bind (state, move, intent) to a freshly generated secret nonce.

    Returns (h_commit, nonce). Publish h_commit to the opponent; keep nonce
    secret until the reveal phase. The nonce is what hides the move: without
    it, the digest of a small move set would be trivially brute-forced.
    """
    nonce = token_hex(_NONCE_BYTES)
    payload = _canonical_payload(state, move, intent, nonce)
    return hashlib.sha256(payload).hexdigest(), nonce


def verify(state: str, move: str, intent: str, nonce: str, h_commit: str) -> bool:
    """True if the revealed values reproduce h_commit.

    Compares with secrets.compare_digest rather than ==, which would leak
    through timing how many leading characters matched and hand an opponent a
    search gradient toward a colliding reveal.
    """
    payload = _canonical_payload(state, move, intent, nonce)
    expected = hashlib.sha256(payload).hexdigest()
    return compare_digest(expected, h_commit)
