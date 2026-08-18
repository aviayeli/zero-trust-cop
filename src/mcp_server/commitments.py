"""Per-turn two-phase commitment/reveal ordering.

Peers first publish commitments, then reveal their moves.  A reveal is refused
until both commitments are present so the second peer cannot wait to see an
opponent's move before choosing its own commitment.
"""

import time
from dataclasses import dataclass

from mcp_server.crypto import verify
from mcp_server.identity import PEER_ROLES


@dataclass
class CommitOutcome:
    """status: "waiting" | "both_committed" | "rejected"."""

    status: str
    reason: str | None = None


@dataclass
class RevealOutcome:
    """status: "waiting" | "resolved" | "rejected"."""

    status: str
    moves: "dict | None" = None
    reason: str | None = None


class CommitmentBook:
    """Hold the two peers' commitments and verified move reveals for one turn."""

    def __init__(self, turn: int = 0, timeout_seconds=None, clock=time.monotonic):
        """``timeout_seconds`` None disables forfeits (the in-process trainer)."""
        self._turn = turn
        self._commitments: dict[str, str] = {}
        self._moves: dict[str, str] = {}
        self._timeout_seconds = timeout_seconds
        self._clock = clock
        self._deadline = None

    def stalled_roles(self) -> list:
        """Roles that have not completed this turn once the deadline passed (D7).

        The clock starts at the FIRST commitment. Blame is attributed to the
        phase that is actually blocked: while a commitment is outstanding only
        the silent committer is at fault, because a reveal is REFUSED until
        both commitments are in — so its opponent is blocked, not stalling.
        """
        if self._deadline is None or self._clock() <= self._deadline:
            return []
        missing = [role for role in PEER_ROLES if role not in self._commitments]
        if missing:
            return missing
        return [role for role in PEER_ROLES if role not in self._moves]

    def _start_deadline(self) -> None:
        if self._timeout_seconds is not None and self._deadline is None:
            self._deadline = self._clock() + self._timeout_seconds

    def state(self) -> str:
        if len(self._moves) == len(PEER_ROLES):
            return "resolved"
        if self._moves:
            return "half_revealed"
        if len(self._commitments) == len(PEER_ROLES):
            return "both_committed"
        if self._commitments:
            return "half"
        return "empty"

    def commitment_for(self, role: str) -> str | None:
        """Return the stored commitment digest for a role this turn, or None."""
        return self._commitments.get(role)

    def commit(self, role: str, turn: int, h_commit: str) -> CommitOutcome:
        if role not in PEER_ROLES:
            return CommitOutcome("rejected", "invalid_role")
        if turn < self._turn:
            return CommitOutcome("rejected", "stale_turn")
        if turn > self._turn:
            self._turn = turn
            self._commitments.clear()
            self._moves.clear()
            self._deadline = None
        if role in self._commitments:
            return CommitOutcome("rejected", "already_committed")

        self._commitments[role] = h_commit
        self._start_deadline()
        if len(self._commitments) == len(PEER_ROLES):
            return CommitOutcome("both_committed")
        return CommitOutcome("waiting")

    def reveal(
        self,
        role: str,
        turn: int,
        state: str,
        move: str,
        intent: str,
        nonce: str,
    ) -> RevealOutcome:
        if role not in PEER_ROLES:
            return RevealOutcome("rejected", reason="invalid_role")
        if turn < self._turn:
            return RevealOutcome("rejected", reason="stale_turn")
        if turn > self._turn:
            return RevealOutcome("rejected", reason="future_turn")
        if len(self._commitments) != len(PEER_ROLES):
            return RevealOutcome("rejected", reason="reveal_before_commit")
        if role in self._moves:
            return RevealOutcome("rejected", reason="already_revealed")
        if not verify(state, move, intent, nonce, self._commitments[role]):
            return RevealOutcome("rejected", reason="broken_commitment")

        self._moves[role] = move
        if len(self._moves) == len(PEER_ROLES):
            return RevealOutcome("resolved", moves=dict(self._moves))
        return RevealOutcome("waiting")
