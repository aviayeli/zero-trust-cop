"""The `smell_grid` a reference-v3 turn carries (PRD_10 FR6).

BOTH peers emit, every turn, their own full accumulated trail. That is SPEC
§5's "each peer emits its own", confirmed with ali-ahm1 on 2026-08-24, and it
is also what the fixture says in its own vocabulary: `smell_grid` is REQUIRED
on every TurnMessage regardless of sender. A peer that sends `{}` receives its
opponent's positions while disclosing none of its own -- and with the sides
swapping every sub-game, that asymmetry is worth a series.

The kernel is CHEBYSHEV: a full `pheromone_grid_size` box, corners included,
falling off by max(|dr|, |dc|). Our internal `strategy.pheromones.
PheromoneField` uses a MANHATTAN diamond and keeps it. They are two different
functions on purpose and neither may quietly become the other:

* ``PheromoneField`` is what WE BELIEVE about the opponent. Its footprint is
  baked into the trained tables' state layout, so changing it would silently
  invalidate every shipped Q-value.
* this is what we DISCLOSE about ourselves. Its shape is an inter-team term,
  settled by agreement rather than by our strategy.

The decay is SUBTRACTIVE -- a flat ``decay_per_step`` off every non-zero
cell, clamped at zero -- which is the other place these two functions part
company: ``PheromoneField`` decays GEOMETRICALLY, and its own docstring says
so. Both are defensible readings of a term spelled ``decay_per_step: 0.1``,
which is exactly why it had to be settled by agreement rather than by
reasoning. Agreed with ali-ahm1 on 2026-08-24 as ``subtractive_chebyshev_v1``.
Their name for it; the vendored CORE fixtures carry the VALUE and define no
recurrence, so this citation is the agreement, not the kit.

The practical difference: a lone 0.9 deposit is gone on the ninth step here
and merely faint after forty under the geometric form. Trails are short.

Nothing here is sealed. ``smell_grid`` is not part of the committed payload,
so a kernel or decay disagreement costs a difference in what each side learns
-- it can never surface as a false tamper verdict at audit, which is also why
it would have gone unnoticed for a whole series.

CONFIGURED CONSTANTS (``config/game.json``, never literals here):
``pheromone_center_intensity``, ``pheromone_decay``, ``pheromone_grid_size``.
"""

from __future__ import annotations

# Re-exported: reading THEIR grid lives in `smell_reader`, but callers
# think in one protocol and importing it from here keeps them honest.
from mcp_server.smell_reader import strongest_cell

# Places every value is rounded to. The kit's CORE vector rounds to 3 and
# compares dicts exactly, so a value carried at full float precision is a
# mismatch even when it is arithmetically identical.
_ROUND_PLACES = 3


class SmellTrail:
    """One peer's own scent trail, in the shape it crosses the wire.

    Implements ``subtractive_chebyshev_v1`` (SPEC 5) exactly:

    * radial emission, ``half = grid_size // 2``,
      ``falloff = intensity / (half + 1)``, each in-bounds cell taking
      ``round(max(0, intensity - falloff * chebyshev), 3)``;
    * the emitted field merged into the trail **by MAX**, never summed --
      summing lets a revisited cell exceed ``center_intensity`` and produces a
      trail the opponent's model does not predict;
    * decay by a flat constant per step, clamped at zero and rounded;
    * emission gated on ``min_center_intensity``, so a centre too faint to
      register emits nothing at all.

    Raises:
        ValueError: an even or non-positive ``pheromone_grid_size``. The
            kernel has a centre cell, so the box must be odd; refused rather
            than rounded, because a peer silently emitting a 4x4 footprint
            discloses a different amount than the term it agreed to.
    """

    def __init__(self, config):
        if config.pheromone_grid_size <= 0 or config.pheromone_grid_size % 2 == 0:
            raise ValueError("pheromone_grid_size must be a positive odd number")
        self._config = config
        self._half = config.pheromone_grid_size // 2
        self._field: dict = {}

    def step(self, cell: tuple) -> None:
        """One full turn: emit at the cell we now occupy, merge, then decay.

        Emit-then-decay is the reference's order, taken from the kit's own
        ``sparring/rules/scent.py``; the book's model is the other way round
        and is a separate registration (SPEC 5.1). The transmitted centre is
        therefore ``emit_intensity - decay_per_step``, not the raw kernel.
        """
        self.emit(tuple(cell))
        self.decay()

    def decay(self) -> None:
        """Every known intensity drops by the constant, clamped and rounded."""
        loss = self._config.pheromone_decay
        for cell, value in tuple(self._field.items()):
            self._set(cell, value - loss)

    def load(self, field: dict) -> None:
        """Replace the trail wholesale. For replay and for the kit's vectors."""
        self._field = {}
        for cell, value in field.items():
            self._set(tuple(cell), value)

    def grid(self) -> dict:
        """``{'r,c': intensity}`` -- only values above zero cross the wire."""
        return {
            f"{row},{col}": value
            for (row, col), value in self._field.items()
        }

    def emit(self, centre: tuple) -> None:
        """One radial kernel, CLIPPED at the board edge, merged by MAX.

        Nothing is emitted at all when the centre would not meet
        ``min_center_intensity``: a trace too faint to register is not a
        trace, and emitting it anyway would put a cell on the wire the
        opponent's model never expects to see.
        """
        intensity = self._config.pheromone_center_intensity
        if intensity < self._min_centre():
            return
        falloff = intensity / (self._half + 1)
        size = self._config.grid_size
        for row in range(centre[0] - self._half, centre[0] + self._half + 1):
            for col in range(centre[1] - self._half, centre[1] + self._half + 1):
                if not (0 <= row < size and 0 <= col < size):
                    continue
                distance = max(abs(row - centre[0]), abs(col - centre[1]))
                value = intensity - falloff * distance
                self._set((row, col), max(self._field.get((row, col), 0.0), value))

    def _min_centre(self) -> float:
        """The agreed emission floor, absent from older contracts."""
        return getattr(self._config, "pheromone_min_center_intensity", 0.0)

    def _set(self, cell: tuple, value: float) -> None:
        rounded = round(max(0.0, value), _ROUND_PLACES)
        if rounded > 0:
            self._field[cell] = rounded
        else:
            self._field.pop(cell, None)
