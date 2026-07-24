"""Turn resolution logic (FR5) for the game engine.

Composes engine.board, engine.player, and engine.actions to resolve a single
simultaneous cop/thief turn: independent bounds/barrier resolution for each
agent, followed by a capture check on the resolved positions.
"""

from dataclasses import dataclass

from engine.actions import Action
from engine.board import Board
from engine.player import PlayerState, intended_position


@dataclass
class TurnResult:
    """Outcome of resolving a single turn.

    Attributes:
        cop_position: The cop's resolved (row, col) position after the turn.
        thief_position: The thief's resolved (row, col) position after the turn.
        captured: True if the cop captured the thief this turn.
    """

    cop_position: tuple
    thief_position: tuple
    captured: bool


def _resolve_agent_position(board: Board, old_position: tuple, intended: tuple) -> tuple:
    """Resolve a single agent's move independently of the other agent.

    Args:
        board: The Board used for bounds/barrier checks.
        old_position: The agent's position before the move.
        intended: The agent's intended (possibly illegal) position.

    Returns:
        intended if it is in bounds and not a barrier, else old_position
        (i.e. the move resolves to STAY).
    """
    if board.in_bounds(intended) and not board.is_barrier(intended):
        return intended
    return old_position


def resolve_turn(
    board: Board,
    cop_state: PlayerState,
    thief_state: PlayerState,
    cop_action: Action,
    thief_action: Action,
) -> TurnResult:
    """Resolve one simultaneous cop/thief turn per the FR5 algorithm.

    Each agent's intended move is computed independently, then independently
    checked against board bounds/barriers (an illegal move resolves to
    STAY). Capture is then checked on the RESOLVED positions: either agent
    landing on the same cell, or the two agents swapping/crossing cells.

    This function is pure: it does not mutate cop_state or thief_state.

    Args:
        board: The Board for bounds/barrier checks.
        cop_state: The cop's current PlayerState.
        thief_state: The thief's current PlayerState.
        cop_action: The Action the cop takes this turn.
        thief_action: The Action the thief takes this turn.

    Returns:
        A TurnResult with the resolved positions and capture flag.
    """
    old_cop = cop_state.position
    old_thief = thief_state.position

    int_cop = intended_position(cop_state, cop_action)
    int_thief = intended_position(thief_state, thief_action)

    new_cop = _resolve_agent_position(board, old_cop, int_cop)
    new_thief = _resolve_agent_position(board, old_thief, int_thief)

    same_cell = new_cop == new_thief
    swap = new_cop == old_thief and new_thief == old_cop
    captured = same_cell or swap

    return TurnResult(
        cop_position=new_cop,
        thief_position=new_thief,
        captured=captured,
    )
