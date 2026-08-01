"""One peer's CLIENT side: decide a move, commit to it, sign the commitment.

The server VERIFIES commitments; this builds them. Keeping the two apart is
what lets a peer be zero-trust about its opponent while still being able to
prove its own submissions.

Ordering that is easy to get backwards: ``AgentPolicy.decide`` truncates the
intent to ``hint_max_words`` and returns the truncated text, and THAT is what
is hashed. So the digest covers the truncated intent, and a peer cannot commit
to one intent and reveal another.
"""

from dataclasses import dataclass

from mcp_server.crypto import commit
from mcp_server.identity import sign


@dataclass(frozen=True)
class Submission:
    """Everything needed to commit a move and later reveal it."""

    role: str
    turn: int
    h_commit: str
    signature: str
    state: str
    move: str
    intent: str
    nonce: str


def state_token(turn, own_position, opponent_position) -> str:
    """Bind a commitment to the turn and the positions it was made under.

    A digest that ignored the state could be replayed in a different one.
    """
    return f"{turn}|{tuple(own_position)}|{opponent_position}"


class PeerClient:
    """Produce one peer's signed, committed submissions."""

    def __init__(self, peer_role, policy, signing_key, rng):
        """Store the peer's identity, policy, private key and injected RNG."""
        self.peer_role = peer_role
        self.policy = policy
        self.signing_key = signing_key
        self.rng = rng

    def prepare(self, turn, own_position, opponent_position, board) -> Submission:
        """Choose this turn's move and return its signed commitment."""
        state_key = self.policy.state_key(own_position, opponent_position, board)
        move, intent = self.policy.decide(state_key, self.rng)

        state = state_token(turn, own_position, opponent_position)
        h_commit, nonce = commit(state, move, intent)
        return Submission(
            role=self.peer_role,
            turn=turn,
            h_commit=h_commit,
            signature=sign(self.signing_key, self.peer_role, turn, h_commit),
            state=state,
            move=move,
            intent=intent,
            nonce=nonce,
        )
