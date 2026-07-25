"""Decaying opponent-belief pheromones.

Each cell follows ``tau(t + 1) = max(0, (1 - rho) * tau(t) + delta)``;
the ``max(0, ...)`` is a hard invariant.  The configured footprint is a 5x5
box whose non-zero cells form a 13-cell Manhattan diamond, leaving its corners
at zero.  Kernels at board edges are clipped, never wrapped or redistributed.
"""

from collections.abc import Iterable

from engine.config import GameConfig


class PheromoneField:
    """A config-injected, sparse heatmap of opponent traces."""

    _ROUND_DIGITS = 12

    def __init__(self, config: GameConfig):
        self._config = config
        self._field: dict[tuple[int, int], float] = {}
        self._radius = config.pheromone_grid_size // 2
        if config.pheromone_grid_size <= 0 or config.pheromone_grid_size % 2 == 0:
            raise ValueError("pheromone_grid_size must be a positive odd number")

    def deposit(self, cell: tuple[int, int]) -> None:
        """Add one clipped, Manhattan-falloff observation kernel."""
        self._validate_cell(cell)
        self._add_kernel(cell)

    def advance(self, deposits: Iterable[object] = ()) -> None:
        """Decay all cells, then apply observation kernels or direct deltas.

        A normal item is a cell and deposits one kernel.  ``(cell, delta)`` is
        a direct per-cell delta, retained to make the recurrence's signed-delta
        clamp testable.
        """
        decay = 1 - self._config.pheromone_decay
        for cell, concentration in tuple(self._field.items()):
            self._set(cell, decay * concentration)
        for item in deposits:
            if self._is_direct_delta(item):
                cell, delta = item
                self._validate_cell(cell)
                self._set(cell, self._field.get(cell, 0.0) + delta)
            else:
                self.deposit(item)

    def intensity(self, cell: tuple[int, int]) -> float:
        """Return a cell concentration, rejecting coordinates outside the board."""
        self._validate_cell(cell)
        return self._field.get(cell, 0.0)

    def heatmap(self) -> dict[tuple[int, int], float]:
        """Return a copy of the non-zero belief concentrations."""
        return dict(self._field)

    def strongest(self) -> tuple[int, int] | None:
        """Return the greatest-concentration cell, or ``None`` for no trace."""
        if not self._field:
            return None
        return max(self._field, key=lambda cell: self._field[cell])

    def _add_kernel(self, centre: tuple[int, int]) -> None:
        scale = self._radius + 1
        for row in range(centre[0] - self._radius, centre[0] + self._radius + 1):
            for col in range(centre[1] - self._radius, centre[1] + self._radius + 1):
                if not self._in_bounds((row, col)):
                    continue
                distance = abs(row - centre[0]) + abs(col - centre[1])
                if distance <= self._radius:
                    delta = self._config.pheromone_center_intensity * (scale - distance) / scale
                    self._set((row, col), self._field.get((row, col), 0.0) + delta)

    def _set(self, cell: tuple[int, int], value: float) -> None:
        concentration = max(0.0, round(value, self._ROUND_DIGITS))
        if concentration:
            self._field[cell] = concentration
        else:
            self._field.pop(cell, None)

    def _validate_cell(self, cell: tuple[int, int]) -> None:
        if not self._in_bounds(cell):
            raise ValueError(f"cell outside board: {cell!r}")

    def _in_bounds(self, cell: object) -> bool:
        if not isinstance(cell, tuple) or len(cell) != 2:
            return False
        row, col = cell
        return isinstance(row, int) and isinstance(col, int) and (
            0 <= row < self._config.grid_size and 0 <= col < self._config.grid_size
        )

    @staticmethod
    def _is_direct_delta(item: object) -> bool:
        return (
            isinstance(item, tuple)
            and len(item) == 2
            and isinstance(item[0], tuple)
            and isinstance(item[1], (int, float))
        )
