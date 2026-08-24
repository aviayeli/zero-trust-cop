"""Turning an operator's wait window into the loop's poll budget.

The retry itself is `test_connect_and_play.py`; this is the arithmetic that
decides how long the loop waits for one of THEIR steps.
"""

from scripts.reference_launch import polls_for


def test_the_poll_window_still_derives_from_the_configured_interval():
    assert polls_for(30, 0.5) == 3600
    assert polls_for(0, 0.5) >= 1
