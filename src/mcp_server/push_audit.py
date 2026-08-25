"""What the opponent pushed us, and the deferred audit over it (PRD_09 FR4).

Split from ``push_tools`` at the state/registration seam when that module
reached the 150-line limit. This half decides what an audit can honestly
CONCLUDE; ``push_tools`` decides how the messages arrive.

The dialect's whole verification story lives here, and it is a short one: the
opponent's nonces arrive only at sub-game end, and unless each entry carries
the payload its ``h_commit`` sealed there is no preimage to rebuild. This
module says ``unverifiable`` in that case. Saying ``accepted`` would assert an
audit that never ran.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mcp_server import interop


@dataclass
class PushStore:
    """What the opponent has pushed us this sub-game.

    Their nonces arrive only at the end, so ``commits`` and ``reveals`` sit
    unverified until then -- that is the protocol, not an omission.
    """

    commits: dict = field(default_factory=dict)
    reveals: dict = field(default_factory=dict)
    acks: list = field(default_factory=list)
    claims: list = field(default_factory=list)
    step0: dict | None = None
    nonces: list = field(default_factory=list)


def audit_nonces(store: PushStore, entries: list) -> dict:
    """Re-hash whatever can be rebuilt; be explicit about what cannot.

    An entry must carry the payload its ``h_commit`` sealed. A bare nonce
    leaves no preimage to reconstruct, so it counts as unverifiable rather
    than as a pass.
    """
    verified, mismatches, unrebuildable = 0, [], 0
    for entry in entries:
        if not isinstance(entry, dict) or "payload" not in entry:
            unrebuildable += 1
            continue
        step = entry.get("step")
        expected = store.commits.get(step)
        if expected is None:
            unrebuildable += 1
            continue
        if interop.commit(entry["payload"], entry.get("nonce", "")) == expected:
            verified += 1
        else:
            mismatches.append(step)

    if mismatches:
        status = "tampered"
    elif unrebuildable:
        status = "unverifiable"
    else:
        status = "accepted"
    result = {"status": status, "verified": verified, "mismatches": mismatches}
    if unrebuildable:
        result["reason"] = (
            f"{unrebuildable} entr{'y' if unrebuildable == 1 else 'ies'} carried "
            "no payload to rebuild the preimage from, so the commitment could "
            "not be recomputed. Send each nonce with the payload it sealed."
        )
    return result
