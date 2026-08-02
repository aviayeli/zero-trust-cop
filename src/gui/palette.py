"""Colour rules shared by the live heatmap and the replay viewer.

Kept free of Tkinter so the rules are testable without a display: a headless
CI box can still assert that a stronger belief renders a brighter red and
that a tampered log gets the red banner.
"""

VERIFIED_TEXT = "Verified OK"
TAMPERED_TEXT = "TAMPERED!"
VERIFIED_COLOUR = "#1a7f37"
TAMPERED_COLOUR = "#c62828"
EMPTY_COLOUR = "#f5f5f5"

COP_COLOUR = "#1565c0"
THIEF_COLOUR = "#f9a825"
CAPTURE_COLOUR = "#6a1b9a"
BARRIER_COLOUR = "#37474f"


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Confine a probability to [0, 1] so a stray value cannot break a colour."""
    return max(low, min(high, value))


def heat_colour(intensity: float) -> str:
    """A red whose saturation is PROPORTIONAL to belief strength.

    Zero is the neutral empty shade; higher concentrations keep full red and
    drain green and blue, so the grid reads as a heatmap rather than a set of
    flat marks.
    """
    intensity = clamp(intensity)
    if intensity <= 0:
        return EMPTY_COLOUR
    fade = int(round(235 * (1.0 - intensity)))
    return f"#ff{fade:02x}{fade:02x}"


def badge(ok: bool) -> tuple:
    """(text, colour) for the verdict stamp: green when clean, red when not."""
    if ok:
        return VERIFIED_TEXT, VERIFIED_COLOUR
    return TAMPERED_TEXT, TAMPERED_COLOUR
