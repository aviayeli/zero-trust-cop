"""Open only the endpoints the schedule actually uses (PRD_10 10.26).

`opponents()` opened BOTH of a two-process opponent's endpoints up front. So a
one-sub-game run as police — which never addresses their cop — died when
their cop returned 502, before sub-game 1 could start. Under a deadline that
is the difference between a completed game and nothing: their cop had been
down and up four times that hour and we needed none of it.

The endpoints a series needs follow from the schedule, and the schedule is a
pure function of how many sub-games and which side we start.
"""

import pytest

from scripts.opponent_endpoints import endpoints_needed, resolve_endpoints

COP = "https://their-cop/mcp"
THIEF = "https://their-thief/mcp"


@pytest.fixture
def split():
    return resolve_endpoints(None, COP, THIEF)


def test_one_sub_game_as_police_needs_only_their_thief(split):
    assert endpoints_needed(split, 1, "police") == [THIEF]


def test_one_sub_game_as_thief_needs_only_their_cop(split):
    assert endpoints_needed(split, 1, "thief") == [COP]


def test_two_sub_games_need_both(split):
    """The sides swap, so the second sub-game addresses the other process."""
    assert sorted(endpoints_needed(split, 2, "police")) == sorted([COP, THIEF])


def test_a_single_endpoint_opponent_needs_it_once_however_long_the_series():
    one = resolve_endpoints(COP, None, None)

    assert endpoints_needed(one, 6, "police") == [COP]
