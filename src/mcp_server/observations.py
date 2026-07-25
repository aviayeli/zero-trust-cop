"""Pure view-shaping functions for the MCP server's three tool payloads.

Every function here takes already-fetched values (a MatchState-shaped
duck-typed object, a GameConfig-shaped object, or a TurnResult-shaped
object) and returns a plain dict matching PLAN_02_MCP_Server.md's Tool
Schemas section exactly. No I/O, no locking, no engine mutation, and no
import that executes engine logic at module load time — the MatchState
parameter is intentionally left without a concrete-class annotation since
`mcp_server.match_state` does not exist yet.
"""

from __future__ import annotations

_OPPONENT_OF = {"cop": "thief", "thief": "cop"}

_ERROR_MESSAGES = {
    "invalid_role": "role must be 'cop' or 'thief'",
    "invalid_direction": "invalid action token",
    "already_submitted": "an action was already submitted for this role this turn",
}


def build_observation(match_state, config, role: str) -> dict:
    """Shape the get_observation payload: the requesting role's own view.

    Excludes the opponent's position entirely (FR3).
    """
    position = match_state.cop_position if role == "cop" else match_state.thief_position
    return {
        "role": role,
        "position": position,
        "turn_count": match_state.turn_count,
        "is_terminated": match_state.is_terminated,
        "grid_size": config.grid_size,
        "barrier_count": match_state.barrier_count,
    }


def build_move_waiting(role: str, opponent: str | None = None) -> dict:
    """Shape the make_move "waiting" payload for the first submitter of a turn."""
    opponent = opponent if opponent is not None else _OPPONENT_OF[role]
    return {
        "status": "waiting",
        "role": role,
        "message": f"action buffered; waiting for {opponent}",
    }


def build_move_resolved(match_state, result, role: str) -> dict:
    """Shape the make_move "resolved" payload once both roles have submitted."""
    return {
        "status": "resolved",
        "role": role,
        "cop_position": result.cop_position,
        "thief_position": result.thief_position,
        "captured": result.captured,
        "turn_count": match_state.turn_count,
        "is_terminated": match_state.is_terminated,
        "terminal_reason": match_state.terminal_reason(),
    }


def build_move_error(reason: str) -> dict:
    """Shape the shared error payload for invalid role/direction/double-submit."""
    message = _ERROR_MESSAGES.get(reason, reason)
    return {"error": reason, "message": message}


def build_status(match_state) -> dict:
    """Shape the get_match_status payload. No scoring/points fields."""
    return {
        "turn_count": match_state.turn_count,
        "is_terminated": match_state.is_terminated,
        "pending_roles": match_state.pending_roles(),
        "terminal_reason": match_state.terminal_reason(),
    }
