"""MatchState: the async action-buffering core of the MCP server.

Implements PLAN_02_MCP_Server.md's locked algorithm: a 2-slot per-turn action
buffer guarded by a single asyncio.Lock, a lazy wall-clock timeout (no
blocking sleep), one GameEpisode.step trigger once both roles submit, and
terminal_reason derivation. Bridge layer only: it delegates all resolution to
an injected GameEpisode's step() and never re-implements engine logic. The
slot mechanics live in action_buffer.ActionBuffer.

It also owns FORFEIT state (audit V5). That state was previously held by
SubmissionGate and patched onto get_match_status alone, so a peer polling
get_observation saw a live match while the status tool reported a technical
loss. Terminal state belongs to the one object every tool already reads.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from mcp_server.action_buffer import ActionBuffer

TECHNICAL_LOSS = "technical_loss"


@dataclass
class SubmitOutcome:
    """status: "waiting" | "resolved" | "rejected". `result` holds the TurnResult
    when resolved; `reason` holds a machine code when rejected."""

    status: str
    result: object | None = None
    reason: str | None = None


class MatchState:
    """Buffers async cop/thief actions; resolves a turn once both are in.

    Wraps an injected GameEpisode (exposing step, turn_count, is_terminated,
    history, config.max_moves, cop_state.position, thief_state.position,
    board.barrier_count). `clock` is injectable (default time.monotonic) so
    timeout behaviour is deterministically testable.
    """

    def __init__(self, episode, response_timeout_sec: float, clock=time.monotonic):
        self._episode = episode
        self._buffer = ActionBuffer(response_timeout_sec, clock)
        self._forfeited_by: list = []
        self._lock = asyncio.Lock()

    async def submit(self, role: str, token: str) -> SubmitOutcome:
        """Validate + buffer one role's action; resolve when both slots fill.

        The read-modify-(step) sequence runs inside the asyncio.Lock so exactly
        one GameEpisode.step fires per turn even under concurrent calls (FR8).
        """
        async with self._lock:
            self._buffer.expire_if_stale()

            if not self._buffer.is_known_role(role):
                return SubmitOutcome("rejected", reason="invalid_role")
            if not self._buffer.is_valid_token(token):
                return SubmitOutcome("rejected", reason="invalid_direction")
            if self._buffer.filled(role):
                return SubmitOutcome("rejected", reason="already_submitted")

            self._buffer.accept(role, token)
            if self._buffer.both_filled():
                result = self._episode.step(*self._buffer.actions())
                self._buffer.clear()
                return SubmitOutcome("resolved", result=result)
            return SubmitOutcome("waiting")

    def reset(self) -> None:
        """Start the next sub-game clean: board, buffer and forfeits.

        The buffer matters as much as the board. A slot left half filled
        across a sub-game boundary would resolve the next sub-game's first
        turn against a move submitted for the previous one -- and both peers
        would have signed something the other never saw.
        """
        self._episode.reset()
        self._buffer.clear()
        self._forfeited_by = []

    def forfeit(self, roles) -> None:
        """End the match against every non-responsive peer (D7 / V5).

        An empty list is a no-op, so a healthy match is never terminated by a
        stall check that found nothing.
        """
        if roles:
            self._forfeited_by = list(roles)

    @property
    def forfeited_by(self) -> list:
        """The roles that forfeited, or an empty list while the match is live."""
        return list(self._forfeited_by)

    def pending_roles(self) -> list:
        """Roles with a buffered, unresolved action this turn (raw buffer; a
        stale half-filled turn is forfeited lazily on the next submit)."""
        return self._buffer.filled_roles()

    def terminal_reason(self) -> str | None:
        """'capture' | 'max_moves_reached' | 'technical_loss' | None.

        A real game outcome outranks a forfeit: if the episode actually
        finished, that is what happened, and a later stall check must not
        relabel it.
        """
        episode = self._episode
        if episode.is_terminated:
            if episode.history and episode.history[-1].result.captured:
                return "capture"
            if episode.turn_count >= episode.config.max_moves:
                return "max_moves_reached"
            return None
        return TECHNICAL_LOSS if self._forfeited_by else None

    @property
    def response_timeout_sec(self) -> float:
        """The configured per-turn deadline, in seconds."""
        return self._buffer.response_timeout_sec

    @property
    def turn_count(self) -> int:
        return self._episode.turn_count

    @property
    def is_terminated(self) -> bool:
        return bool(self._forfeited_by) or self._episode.is_terminated

    @property
    def cop_position(self):
        return self._episode.cop_state.position

    @property
    def thief_position(self):
        return self._episode.thief_state.position

    @property
    def barrier_count(self) -> int:
        return self._episode.board.barrier_count
