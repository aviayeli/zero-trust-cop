"""Actions and movement utilities for the game engine."""

from enum import Enum
from engine.errors import InvalidActionError


class Action(Enum):
    """Enumeration of valid actions in the game."""

    N = "N"
    S = "S"
    E = "E"
    W = "W"
    STAY = "STAY"


def parse_action(token: str) -> Action:
    """Parse a token string into an Action enum member.

    Args:
        token: The string token to parse (must be exact match, case-sensitive).

    Returns:
        The corresponding Action enum member.

    Raises:
        InvalidActionError: If token does not match any Action member.
    """
    try:
        return Action[token]
    except KeyError:
        raise InvalidActionError(f"Invalid action: {token}")


def action_delta(action: Action) -> tuple[int, int]:
    """Get the (row, col) delta for an action.

    The coordinate system has origin at top-left:
    - row increases downward (south)
    - col increases rightward (east)

    Args:
        action: The Action to get the delta for.

    Returns:
        A tuple (row_delta, col_delta).
    """
    deltas = {
        Action.N: (-1, 0),    # north = up = row decreases
        Action.S: (1, 0),     # south = down = row increases
        Action.E: (0, 1),     # east = right = col increases
        Action.W: (0, -1),    # west = left = col decreases
        Action.STAY: (0, 0),  # no movement
    }
    return deltas[action]
