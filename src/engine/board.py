"""Board management for the game engine."""

from engine.config import GameConfig
from engine.errors import IllegalBarrierPlacementError, BarrierLimitError


class Board:
    """Manages the game board state, including barrier placement."""

    def __init__(self, config: GameConfig):
        """Initialize the board from a GameConfig.

        Args:
            config: GameConfig instance containing grid_size and max_barriers.
        """
        self.config = config
        self._barriers = set()

    def in_bounds(self, pos) -> bool:
        """Check if a position is within the board bounds.

        Args:
            pos: Tuple (row, col) to check.

        Returns:
            True if 0 <= row < grid_size and 0 <= col < grid_size, False otherwise.
        """
        row, col = pos
        return 0 <= row < self.config.grid_size and 0 <= col < self.config.grid_size

    def is_barrier(self, pos) -> bool:
        """Check if a position has a barrier.

        Args:
            pos: Tuple (row, col) to check.

        Returns:
            True if a barrier exists at pos, False otherwise.
        """
        return pos in self._barriers

    @property
    def barrier_count(self) -> int:
        """Return the number of placed barriers.

        Returns:
            The count of barriers currently on the board.
        """
        return len(self._barriers)

    def place_barrier(self, pos, occupied=()):
        """Place a barrier at the given position.

        Args:
            pos: Tuple (row, col) where the barrier will be placed.
            occupied: Iterable of (row, col) cells currently occupied by agents.

        Raises:
            IllegalBarrierPlacementError: If pos is in occupied.
            BarrierLimitError: If barrier_count >= config.max_barriers.
        """
        # Check 1: Is the position occupied by an agent?
        if pos in occupied:
            raise IllegalBarrierPlacementError(
                f"Cannot place barrier at {pos}: cell is occupied"
            )

        # Check 2: Have we reached the barrier limit?
        if self.barrier_count >= self.config.max_barriers:
            raise BarrierLimitError(
                f"Cannot place barrier at {pos}: barrier limit of {self.config.max_barriers} reached"
            )

        # Add the barrier to the set
        self._barriers.add(pos)
