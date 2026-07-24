"""MatchState: the async action-buffering core of the MCP server.

Implements PLAN_02_MCP_Server.md's locked algorithm: a 2-slot per-turn action
buffer guarded by a single asyncio.Lock, a lazy wall-clock timeout (no blocking
sleep), one GameEpisode.step trigger once both roles submit, and terminal_reason
derivation. Bridge layer only: it imports parse_action/InvalidActionError for
token validation and delegates all resolution to an injected GameEpisode's
step() — it never re-implements engine logic.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from engine.actions import parse_action
from engine.errors import InvalidActionError


@dataclass
class SubmitOutcome:
    """status: "waiting" | "resolved" | "rejected". `result` holds the TurnResult
    when resolved; `reason` holds a machine code when rejected."""

    status: str
    result: "object | None" = None
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
        self._response_timeout_sec = response_timeout_sec
        self._clock = clock
        self._cop_action: str | None = None
        self._thief_action: str | None = None
        self._deadline: float | None = None
        self._lock = asyncio.Lock()

    async def submit(self, role: str, token: str) -> SubmitOutcome:
        """Validate + buffer one role's action; resolve when both slots fill.

        The read-modify-(step) sequence runs inside the asyncio.Lock so exactly
        one GameEpisode.step fires per turn even under concurrent calls (FR8).
        """
        async with self._lock:
            self._expire_if_stale()

            if role not in ("cop", "thief"):
                return SubmitOutcome("rejected", reason="invalid_role")
            try:
                parse_action(token)
            except InvalidActionError:
                return SubmitOutcome("rejected", reason="invalid_direction")
            if self._slot_filled(role):
                return SubmitOutcome("rejected", reason="already_submitted")

            was_empty = not self._any_filled()
            self._set_slot(role, token)
            if was_empty:
                self._deadline = self._clock() + self._response_timeout_sec

            if self._cop_action is not None and self._thief_action is not None:
                result = self._episode.step(self._cop_action, self._thief_action)
                self._clear()
                return SubmitOutcome("resolved", result=result)
            return SubmitOutcome("waiting")

    def pending_roles(self) -> list:
        """Roles with a buffered, unresolved action this turn (raw buffer; a
        stale half-filled turn is forfeited lazily on the next submit)."""
        return self._filled_roles()

    def terminal_reason(self) -> str | None:
        """'capture' | 'max_moves_reached' | None (capture checked first, per
        GameEpisode.step precedence)."""
        ep = self._episode
        if not ep.is_terminated:
            return None
        if ep.history and ep.history[-1].result.captured:
            return "capture"
        if ep.turn_count >= ep.config.max_moves:
            return "max_moves_reached"
        return None

    # --- internal buffer helpers ------------------------------------------

    def _slot_filled(self, role: str) -> bool:
        return (self._cop_action if role == "cop" else self._thief_action) is not None

    def _set_slot(self, role: str, token: str) -> None:
        if role == "cop":
            self._cop_action = token
        else:
            self._thief_action = token

    def _any_filled(self) -> bool:
        return self._cop_action is not None or self._thief_action is not None

    def _filled_roles(self) -> list:
        roles = []
        if self._cop_action is not None:
            roles.append("cop")
        if self._thief_action is not None:
            roles.append("thief")
        return roles

    def _clear(self) -> None:
        self._cop_action = None
        self._thief_action = None
        self._deadline = None

    def _expire_if_stale(self) -> None:
        """Forfeit a half-filled turn whose deadline has passed (option a)."""
        stale = self._deadline is not None and self._clock() > self._deadline
        if stale and len(self._filled_roles()) == 1:
            self._clear()

    # --- read-only passthrough accessors ----------------------------------

    @property
    def turn_count(self) -> int:
        return self._episode.turn_count

    @property
    def is_terminated(self) -> bool:
        return self._episode.is_terminated

    @property
    def cop_position(self):
        return self._episode.cop_state.position

    @property
    def thief_position(self):
        return self._episode.thief_state.position

    @property
    def barrier_count(self) -> int:
        return self._episode.board.barrier_count
