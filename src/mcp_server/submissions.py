"""Authenticate and order peer submissions before they reach the engine.

``MatchState.turn_count`` is authoritative: a caller-supplied turn cannot be
trusted because it could label a reveal as future work or clear a book's
in-progress commitments.
"""

from mcp_server import observations
from mcp_server.directions import is_intent, to_token
from mcp_server.identity import verify_signature
from engine.actions import parse_action
from engine.errors import InvalidActionError


class SubmissionGate:
    """Validate authenticated commitment/reveal messages for one match."""

    def __init__(self, match_state, book, public_keys: dict, engine_role: dict):
        """Store injected peer public keys and peer-to-engine role mapping."""
        self.match_state = match_state
        self.book = book
        self.public_keys = public_keys
        self.engine_role = engine_role
        self.forfeited_by: list = []

    def expire_if_stalled(self) -> list:
        """Forfeit the match against any peer that stalled this turn (D7).

        Checked lazily, like MatchState's own expiry: a stalled match produces
        no further traffic except the compliant peer polling its status.
        """
        if not self.forfeited_by:
            self.forfeited_by = self.book.stalled_roles()
            self.match_state.forfeit(self.forfeited_by)
        return self.forfeited_by

    def submit_commitment(self, role, turn, h_commit, signature) -> dict:
        """Authenticate a commitment before adding it to the commitment book."""
        if self.expire_if_stalled():
            return observations.build_move_error("match_forfeited")
        if role not in self.public_keys:
            return observations.build_move_error("invalid_role")
        if turn != self.match_state.turn_count:
            return observations.build_move_error("wrong_turn")
        if not verify_signature(self.public_keys[role], role, turn, h_commit, signature):
            return observations.build_move_error("invalid_signature")

        outcome = self.book.commit(role, turn, h_commit)
        if outcome.status == "waiting":
            return observations.build_move_waiting(role, self._opponent(role))
        if outcome.status == "both_committed":
            return {"status": "both_committed", "role": role}
        return observations.build_move_error(outcome.reason)

    async def reveal_move(self, role, turn, state, move, intent, nonce, signature) -> dict:
        """Authenticate and reveal a move, resolving the engine when both reveal."""
        if self.expire_if_stalled():
            return observations.build_move_error("match_forfeited")
        if role not in self.public_keys:
            return observations.build_move_error("invalid_role")
        if turn != self.match_state.turn_count:
            return observations.build_move_error("wrong_turn")
        h_commit = self.book.commitment_for(role)
        if h_commit is None:
            return observations.build_move_error("reveal_before_commit")
        if not verify_signature(self.public_keys[role], role, turn, h_commit, signature):
            return observations.build_move_error("invalid_signature")
        if not is_intent(intent):
            return observations.build_move_error("invalid_intent")
        try:
            parse_action(to_token(move))
        except (InvalidActionError, ValueError):
            return observations.build_move_error("invalid_direction")

        outcome = self.book.reveal(role, turn, state, move, intent, nonce)
        if outcome.status == "waiting":
            return observations.build_move_waiting(role, self._opponent(role))
        if outcome.status == "rejected":
            return observations.build_move_error(outcome.reason)

        result = None
        for peer_role, peer_move in outcome.moves.items():
            submitted = await self.match_state.submit(
                self.engine_role[peer_role], to_token(peer_move)
            )
            if submitted.status == "rejected":
                return observations.build_move_error(submitted.reason)
            if submitted.status == "resolved":
                result = submitted.result
        return observations.build_move_resolved(
            self.match_state, result, role
        )

    def _opponent(self, role):
        """Return the other peer from the injected peer-to-engine mapping."""
        return next(peer for peer in self.engine_role if peer != role)
