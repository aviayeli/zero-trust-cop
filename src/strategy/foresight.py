"""Lag compensation via smoothed extrapolation (Council review, PRD_18).

The naive approach amplifies jumps when the tracked argmax sits still and then
leaps L cells at once — extrapolating (0,0) for L-1 turns masks the velocity.
Smoothing over a window of observations recovers a per-turn velocity instead,
and clamping on the board prevents the projection from escaping. The gate is
scale-free confidence: max/sum of the field values, which discriminates between
noise (0.13-0.30) and signal (0.8+) without needing a tuned threshold.
"""

from __future__ import annotations


def confidence(field: dict) -> float:
    """Likelihood the field peak is real, not accumulated noise.

    Returns max/sum of field values: a scale-free measure that stays between
    0 and 1 regardless of how many observations fed the field. An empty field
    has no signal, so return 0.0 rather than dividing by zero.
    """
    if not field:
        return 0.0
    return max(field.values()) / sum(field.values())


class Foresight:
    """Projects a target forward along its trajectory, under confidence.

    One instance per game: the belief history and tuning are per-game state,
    and carrying either across a boundary would judge a new board by an old walk.
    """

    def __init__(
        self, grid_size: int, min_confidence: float, horizon: int, window: int
    ):
        """Initialize with game board size and projection tuning.

        ``grid_size`` bounds the board (0..grid_size-1). ``min_confidence`` is
        the threshold for the scale-free confidence gate: below it, we return
        the raw belief without extrapolation because we do not trust the signal.
        ``horizon`` is how many turns ahead to project. ``window`` is the number
        of observations to smooth over for velocity estimation.
        """
        self.grid_size = grid_size
        self.min_confidence = min_confidence
        self.horizon = horizon
        self.window = window
        self._history: list = []

    def target(self, belief: tuple | None, conf: float) -> tuple | None:
        """Return the projected target, or the belief if projection is unsafe.

        If ``belief`` is None there is nothing to track. If ``conf`` falls below
        the gate, extrapolating noise moves us away from the only evidence we
        have, so we return the raw belief. If we have fewer than ``window``
        observations, one sample is not a velocity, so we hold and wait.

        Otherwise, compute the smoothed per-turn displacement from the oldest
        and newest entries in the window, project ahead by ``horizon`` turns,
        clamp the result to the board, and return it as a rounded tuple of ints.
        """
        if belief is None:
            return None

        belief = tuple(belief)
        self._history.append(belief)
        self._history = self._history[-self.window :]

        if conf < self.min_confidence or len(self._history) < self.window:
            return belief

        oldest = self._history[0]
        newest = self._history[-1]

        vr = (newest[0] - oldest[0]) / self.window
        vc = (newest[1] - oldest[1]) / self.window

        row = belief[0] + self.horizon * vr
        col = belief[1] + self.horizon * vc

        row = max(0, min(self.grid_size - 1, round(row)))
        col = max(0, min(self.grid_size - 1, round(col)))

        return (row, col)
