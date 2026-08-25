"""The league's cross-team byte constructions (community interop kit, CORE).

Every hash in here is re-computed by the OPPONENT, so none of it can be
validated by self-consistency: sign and verify with the same wrong separator
and every local test still passes. Conformance is pinned against the kit's
shared fixtures in ``tests/mcp_server/test_interop_vectors.py``.

Two canonical forms live here, deliberately:

* ``canonical_str`` -- compact, ``sort_keys``, ``ensure_ascii=False``. Used by
  every commit, signature and id. ``ensure_ascii=False`` is load-bearing: a
  Hebrew or emoji ``hint`` escaped to ``\\uXXXX`` hashes differently, the
  opponent's audit re-hash misses, and a clean match is scored as tampering
  for BOTH sides.
* the SPACED form inside ``report_consensus_signature`` -- the one settlement
  hash that uses json.dumps' default ``(", ", ": ")`` separators. It is not a
  bug to be normalized away; the reference tooling computes it that way and
  settlement is where two teams must agree or neither scores.

The book publishes three mutually inconsistent commit constructions (its ch.5
listing seals the nonce INSIDE the object; an audit snippet hashes only
``nonce|move``). This module implements the third -- the lecturer's reference
form -- which is what the kit pins and the only one of the three that binds
the whole record: the audit-snippet form leaves ``state`` and ``intent``
rewritable after the fact.
"""

from __future__ import annotations

import hashlib
import json
import uuid

# Separator between a canonical payload and its nonce. A SINGLE pipe (U+007C):
# not a bare concatenation, not "||". All three read plausibly in prose, only
# one reproduces the vectors, and the wrong ones fail every handshake with
# nothing to go on but "signature mismatch".
NONCE_SEPARATOR = "|"

# The Hebrew key the settlement signature is stored under, inserted AFTER the
# signature is computed so the field is excluded from its own preimage.
CONSENSUS_KEY = "חתימת_קונסנזוס_משותפת"


def canonical_str(payload) -> str:
    """The one canonical form: compact, key-sorted, native UTF-8.

    Keys sort by Unicode CODE POINT, which is what Python's ``sort_keys``
    already does. Runtimes that sort UTF-16 code units (JS, Java, C#) order
    an astral key against a high-BMP one the other way round.
    """
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def canonical_bytes(payload) -> bytes:
    return canonical_str(payload).encode("utf-8")


def canonical_hash(payload) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def commit(payload: dict, nonce: str) -> str:
    """``SHA256( canonical_json(payload) | nonce )``.

    The nonce is appended to the canonical STRING, not sealed inside the
    hashed object. Each peer seals its own record and publishes only the
    digest; nonces are revealed at the end-of-game audit, where both peers
    re-hash every revealed ``(payload, nonce)`` and must reproduce it.
    """
    return hashlib.sha256(
        f"{canonical_str(payload)}{NONCE_SEPARATOR}{nonce}".encode()
    ).hexdigest()


def terms_signature(terms: dict, nonce: str) -> str:
    """Pre-game agreement signature -- the commit construction over the terms.

    Each peer signs with its own nonce; the opponent re-verifies over the
    terms it received (which must value-equal its own) using the signer's
    nonce. Any canonicalization difference makes the peers refuse to start.
    """
    return commit(terms, nonce)


def _sorted_pair(group_a: str, group_b: str) -> list[str]:
    """SORT the pair -- never name ourselves first.

    Both ids are pure functions of shared inputs, so neither peer has to be
    told which order to use and there is no convention left to settle. A peer
    that builds ``"<us>-vs-<them>"`` derives a different id on each side of
    the same match: two sets of artifact filenames, and two final reports
    that cannot be joined by ``game_id`` at all.
    """
    return sorted([group_a, group_b])


def game_id(group_a: str, group_b: str) -> str:
    """The human-readable match id naming all four submission artifacts."""
    return "-vs-".join(_sorted_pair(group_a, group_b))


def game_uid(terms: dict, group_a: str, group_b: str) -> str:
    """``UUID( SHA256( canonical(terms) | g_a | g_b )[:16] )``, pair sorted.

    Derive it from the EXTRACTED terms, not from the whole ``game.json``.
    Hashing the full config yields a uid that is stable, reproducible and
    identical across all four of our own artifacts -- so they join each other
    perfectly and only the cross-team join fails, silently.
    """
    pair = NONCE_SEPARATOR.join(_sorted_pair(group_a, group_b))
    seed = f"{canonical_str(terms)}{NONCE_SEPARATOR}{pair}"
    return str(uuid.UUID(bytes=hashlib.sha256(seed.encode("utf-8")).digest()[:16]))


def report_consensus_signature(report: dict) -> str:
    """Settlement consensus signature -- the SPACED canonical form.

    ``sort_keys=True, ensure_ascii=False`` but json.dumps' DEFAULT separators.
    Computed over the report BEFORE ``CONSENSUS_KEY`` is inserted, so verify
    by popping that key, re-serializing spaced, and re-hashing.
    """
    spaced = json.dumps(report, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(spaced.encode("utf-8")).hexdigest()


def sign_report(report: dict) -> dict:
    """Sign-then-insert: the signature is absent from its own preimage."""
    return {**report, CONSENSUS_KEY: report_consensus_signature(report)}
