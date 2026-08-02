"""GUI colour rules, asserted without opening a window.

The rules live apart from Tkinter precisely so a headless machine can still
check them: a display-dependent test would simply be skipped in CI and the
heatmap could silently render every cell the same shade.
"""

import pytest

from gui.palette import (
    EMPTY_COLOUR,
    TAMPERED_COLOUR,
    TAMPERED_TEXT,
    VERIFIED_COLOUR,
    VERIFIED_TEXT,
    badge,
    clamp,
    heat_colour,
)


def test_an_empty_cell_is_neutral_not_red():
    assert heat_colour(0.0) == EMPTY_COLOUR


def test_belief_strength_is_monotonic_in_redness():
    """Stronger belief must never render paler than weaker belief."""
    shades = [heat_colour(i / 10) for i in range(1, 11)]
    greens = [int(shade[3:5], 16) for shade in shades]

    assert greens == sorted(greens, reverse=True), "red must deepen with belief"
    assert len(set(shades)) == len(shades), "each level must be distinguishable"


def test_full_belief_is_pure_red():
    assert heat_colour(1.0) == "#ff0000"


def test_every_colour_is_a_valid_hex_triplet():
    for step in range(0, 11):
        colour = heat_colour(step / 10)
        assert len(colour) == 7 and colour.startswith("#")
        int(colour[1:], 16)


@pytest.mark.parametrize("wild", [-5.0, 1.5, 99.0])
def test_out_of_range_probabilities_cannot_break_a_colour(wild):
    colour = heat_colour(wild)

    assert len(colour) == 7
    int(colour[1:], 16)


def test_clamp_confines_to_the_unit_interval():
    assert clamp(-1) == 0.0 and clamp(2) == 1.0 and clamp(0.4) == 0.4


def test_a_clean_log_gets_the_green_badge():
    assert badge(True) == (VERIFIED_TEXT, VERIFIED_COLOUR)


def test_a_tampered_log_gets_the_red_banner():
    assert badge(False) == (TAMPERED_TEXT, TAMPERED_COLOUR)


def test_the_two_badges_are_never_confusable():
    clean_text, clean_colour = badge(True)
    dirty_text, dirty_colour = badge(False)

    assert clean_text != dirty_text and clean_colour != dirty_colour
