"""Verify a disclosed reference-v3 chain (PRD_10 FR8).

Split out of ``reference_tools`` at the judge/transport seam: that module
decides how a message arrives, this one decides what the evidence supports.
The split also keeps both under the 150-line limit with room left, which the
combined version no longer had.

Two checks, in this order:

1. **Self-consistency.** Re-hash ``payload`` with ``nonce`` and compare to the
   record's own ``commit``, using OUR serializer. This is where a
   canonicalization difference surfaces, which is why ``ensure_ascii=False``
   is load-bearing.
2. **The wire.** Compare the disclosed ``commit`` to the digest that peer
   actually PUSHED at that step, in a ``receive_turn`` we accepted before the
   outcome was known.

(1) alone is a checksum, not a commitment: a peer that rewrites its whole
chain after the sub-game -- payload, nonce and commit together -- passes it
perfectly. (2) is what makes the seal binding.

A step we never received is NOT faulted. The sealed step-0 host-spec record
is disclosed here and never transmitted as a turn, so it has no pushed digest
to be compared against, and a peer whose turn we dropped is not a cheat.
"""

from __future__ import annotations

from mcp_server import interop


def step_of(record: dict):
    """The step a record belongs to, or None.

    The agreed record is ``{payload, nonce, commit}`` with no top-level
    ``step``, so the payload is asked first and the flat key is the fallback.
    """
    payload = record.get("payload")
    if isinstance(payload, dict) and isinstance(payload.get("step"), int):
        return payload["step"]
    step = record.get("step")
    return step if isinstance(step, int) else None


def label(record: dict, position: int):
    """Name a record for a mismatch report; never raise on the tamper path."""
    step = step_of(record)
    return position if step is None else step


def pushed_commit(inbox, step):
    """The digest they pushed at ``step``, or None if it never reached us."""
    if step is None:
        return None
    for message in reversed(list(inbox)):
        if message.get("step") == step:
            return message.get("commit")
    return None


def _fault(record: dict, named, inbox) -> str | None:
    """Why this record fails, or None."""
    if interop.commit(record["payload"], record["nonce"]) != record["commit"]:
        return f"step {named}: record does not re-hash to its own commit"

    pushed = pushed_commit(inbox, step_of(record))
    if pushed is not None and pushed != record["commit"]:
        return (
            f"step {named}: disclosed commit {record['commit']} is not the "
            f"digest pushed at that step, {pushed}"
        )
    return None


def verify_records(records: list, inbox) -> dict:
    """Judge a whole disclosed chain.

    Returns:
        ``status`` (``accepted`` | ``tampered``), how many records survived,
        the mismatched steps, and -- only when something failed -- a ``reason``
        naming each fault, so the opponent can see WHICH check it lost rather
        than a bare verdict.
    """
    faults = []
    for position, record in enumerate(records, start=1):
        named = label(record, position)
        reason = _fault(record, named, inbox)
        if reason is not None:
            faults.append((named, reason))

    result = {
        "status": "tampered" if faults else "accepted",
        "records_verified": len(records) - len(faults),
        "mismatches": [named for named, _ in faults],
    }
    if faults:
        result["reason"] = "; ".join(reason for _, reason in faults)
    return result
