"""Per-turn two-phase commitment/reveal ordering.

Peers first publish commitments, then reveal their moves.  A reveal is refused
until both commitments are present so the second peer cannot wait to see an
opponent's move before choosing its own commitment.
"""

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

    def __init__(self, turn: int = 0):
        self._turn = turn
        self._commitments: dict[str, str] = {}
        self._moves: dict[str, str] = {}

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

    def commit(self, role: str, turn: int, h_commit: str) -> CommitOutcome:
        if role not in PEER_ROLES:
            return CommitOutcome("rejected", "invalid_role")
        if turn < self._turn:
            return CommitOutcome("rejected", "stale_turn")
        if turn > self._turn:
            self._turn = turn
            self._commitments.clear()
            self._moves.clear()
        if role in self._commitments:
            return CommitOutcome("rejected", "already_committed")

        self._commitments[role] = h_commit
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
