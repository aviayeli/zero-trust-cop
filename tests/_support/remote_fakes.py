"""Two INDEPENDENT peer servers, faked, for the remote-opponent loop.

Each fake owns its own turn counter and positions rather than sharing one
world, because that is the real topology: our peer and the opposing group's
are separate MatchStates, kept in step only by both clients pushing to both.
Sharing state here would hide the drift the loop exists to detect.

``resolves_inline`` picks which side of the reveal race is being scripted.
The gate answers ``resolved`` only to the SECOND revealer, so True means the
opponent got there first and this server can settle the turn for us; False
means ours landed first and the turn resolves later, out of band.
"""

from mcp_server.observations import scoring_block
from mcp_server.peer_client import Submission


class FakePeer:
    """One peer server's tool surface, with its own independent state."""

    def __init__(
        self, config, board, engine_role, turns_to_play,
        resolves_inline=False, stalled=False, commit_lag=0,
    ):
        self.config = config
        self.board = board
        self.engine_role = engine_role
        self.turns_to_play = turns_to_play
        self.resolves_inline = resolves_inline
        self.stalled = stalled
        self.refuse_with = None  # injected fault
        # Reveals to refuse per turn with `reveal_before_commit`, standing
        # in for an opponent whose commitment has not landed here yet.
        self.commit_lag = commit_lag
        self.refused_reveals = 0
        self._refused_this_turn = 0
        self.turn_offset = 0  # injected disagreement
        self.turn = 0
        self.cop = tuple(config.cop_start)
        self.thief = tuple(config.thief_start)
        self.pending = False
        self.commitments = []
        self.reveals = []
        self.order = []
        self.status_polls = 0

    def _advance(self):
        """Settle a turn, nudging the thief so positions demonstrably change."""
        row, column = self.thief
        self.thief = (row, (column + 1) % self.config.grid_size)
        self.turn += 1
        self.pending = False
        self._refused_this_turn = 0

    @property
    def terminated(self):
        return self.turn >= self.turns_to_play

    @property
    def reason(self):
        return "max_moves_reached" if self.terminated else None

    def _error(self):
        return {"error": self.refuse_with, "message": self.refuse_with}

    async def get_observation(self, role):
        assert role == self.engine_role, "a peer answers only for its own role"
        return {
            "role": role,
            "position": self.cop if role == "cop" else self.thief,
            "turn_count": self.turn + self.turn_offset,
            "is_terminated": self.terminated,
            "grid_size": self.config.grid_size,
            "barrier_count": self.board.barrier_count,
            "axis_origin_corner": self.config.axis_origin_corner,
            "axis_start_index": self.config.axis_start_index,
            "max_moves": self.config.max_moves,
            "scoring": scoring_block(self.config),
        }

    async def submit_commitment(self, role, turn, h_commit, signature):
        self.order.append("commit")
        self.commitments.append((role, turn, h_commit))
        if self.refuse_with:
            return self._error()
        return {"status": "waiting", "role": role}

    async def reveal_move(self, role, turn, state, move, intent, nonce, signature):
        self.order.append("reveal")
        if self._refused_this_turn < self.commit_lag:
            self._refused_this_turn += 1
            self.refused_reveals += 1
            return {
                "error": "reveal_before_commit",
                "message": "both commitments are not in yet",
            }
        self.reveals.append((role, turn, move, intent))
        if self.refuse_with:
            return self._error()
        if not self.resolves_inline:
            self.pending = True
            return {"status": "waiting", "role": role}
        self._advance()
        return {
            "status": "resolved",
            "role": role,
            "cop_position": self.cop,
            "thief_position": self.thief,
            "captured": False,
            "turn_count": self.turn + self.turn_offset,
            "is_terminated": self.terminated,
            "terminal_reason": self.reason,
        }

    async def get_match_status(self):
        """Polling is also when the opponent's out-of-band reveal shows up."""
        self.status_polls += 1
        if self.pending and not self.stalled:
            self._advance()
        return {
            "turn_count": self.turn + self.turn_offset,
            "is_terminated": self.terminated,
            "pending_roles": [],
            "terminal_reason": self.reason,
            "forfeited_by": [],
        }


class FakeClient:
    """Our signing client, reduced to the one thing the loop asks of it."""

    def __init__(self, peer_role):
        self.peer_role = peer_role

    def prepare(self, turn, own_position, opponent_position, board):
        return Submission(
            role=self.peer_role, turn=turn, h_commit=f"h{turn}",
            signature=f"sig{turn}", move="M:N", intent="truth", nonce=f"n{turn}",
            state=f"{turn}|{tuple(own_position)}|{tuple(opponent_position)}",
        )
