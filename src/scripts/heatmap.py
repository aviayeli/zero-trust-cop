"""Belief-heatmap rendering: trace level, and red intensity proportional to it.

The pheromone field is the peer's probabilistic belief about where its
opponent is, so the display shades it from dark to bright red in proportion
to concentration rather than drawing a flat mark. Colour is opt-in: piped and
captured output must stay byte-clean, so the caller passes the decision in.
"""

EMPTY = "."
_LEVELS = "123456789"
# ANSI 256-colour reds, dark -> bright, walked in proportion to intensity.
_REDS = (52, 88, 124, 160, 196)
_RESET = "\033[0m"


def scent_symbol(intensity: float) -> str:
    """Map a concentration onto one trace character."""
    if intensity <= 0:
        return EMPTY
    level = int(intensity * len(_LEVELS))
    return _LEVELS[min(level, len(_LEVELS) - 1)]


def red_for(intensity: float) -> str:
    """The ANSI escape whose red brightness matches this concentration."""
    step = int(intensity * len(_REDS))
    return f"\033[38;5;{_REDS[min(step, len(_REDS) - 1)]}m"


def heat_cell(intensity: float, colour: bool) -> str:
    """A trace cell, shaded by belief strength when colour is enabled."""
    symbol = scent_symbol(intensity)
    if not colour or symbol == EMPTY:
        return symbol
    return f"{red_for(intensity)}{symbol}{_RESET}"
