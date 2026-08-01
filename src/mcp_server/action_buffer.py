"""The per-turn two-slot action buffer behind MatchState.

Extracted so ``match_state.py`` has headroom to own forfeit state, which the
audit found scattered onto one tool instead (V5). This holds one slot per
engine role plus the lazy wall-clock deadline; it knows nothing about
episodes and never resolves a turn — that stays with MatchState.

Expiry is lazy by design: a half-filled turn is forfeited on the NEXT
submission rather than by a background timer, so nothing has to be running
for the rule to hold.
"""

from engine.actions import parse_action
from engine.errors import InvalidActionError

ENGINE_ROLES = ("cop", "thief")


class ActionBuffer:
    """Buffers at most one action per engine role for the current turn."""

    def __init__(self, response_timeout_sec: float, clock):
        self.response_timeout_sec = response_timeout_sec
        self._clock = clock
        self._actions: dict = {role: None for role in ENGINE_ROLES}
        self._deadline: float | None = None

    @staticmethod
    def is_known_role(role: str) -> bool:
        return role in ENGINE_ROLES

    @staticmethod
    def is_valid_token(token: str) -> bool:
        """Validate a move token without letting the engine error escape."""
        try:
            parse_action(token)
        except InvalidActionError:
            return False
        return True

    def filled(self, role: str) -> bool:
        return self._actions[role] is not None

    def filled_roles(self) -> list:
        return [role for role in ENGINE_ROLES if self._actions[role] is not None]

    def both_filled(self) -> bool:
        return all(self._actions[role] is not None for role in ENGINE_ROLES)

    def actions(self) -> tuple:
        """The buffered (cop, thief) tokens, in engine order."""
        return tuple(self._actions[role] for role in ENGINE_ROLES)

    def accept(self, role: str, token: str) -> None:
        """Store one role's action, starting the deadline on the first one."""
        was_empty = not self.filled_roles()
        self._actions[role] = token
        if was_empty:
            self._deadline = self._clock() + self.response_timeout_sec

    def clear(self) -> None:
        for role in ENGINE_ROLES:
            self._actions[role] = None
        self._deadline = None

    def expire_if_stale(self) -> None:
        """Forfeit a half-filled turn whose deadline has passed."""
        stale = self._deadline is not None and self._clock() > self._deadline
        if stale and len(self.filled_roles()) == 1:
            self.clear()
