"""Player state and movement for the game engine."""

from dataclasses import dataclass

from engine.actions import Action, action_delta


@dataclass
class PlayerState:
    """Represents the state of a player in the game.

    Attributes:
        position: A tuple (row, col) representing the player's location.
        role: A string representing the player's role (e.g., "cop" or "thief").
    """

    position: tuple[int, int]
    role: str


def intended_position(state: PlayerState, action: Action) -> tuple[int, int]:
    """Compute the intended position after taking an action.

    This is a pure function that returns where a player would move if the
    action were executed, without any bounds checking or barrier awareness.
    The state is not mutated.

    Args:
        state: The current PlayerState.
        action: The Action to take.

    Returns:
        A tuple (row, col) representing the intended position after the action.
        May be out-of-grid coordinates.
    """
    drow, dcol = action_delta(action)
    return (state.position[0] + drow, state.position[1] + dcol)
