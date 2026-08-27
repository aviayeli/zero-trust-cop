"""One call per sub-game, addressed to the side THEY are playing (10.21).

`play_series` took a single `call` and used it for the whole series, which is
correct only when one endpoint serves both the opponent's roles. Against a
two-process opponent the destination changes every sub-game with the sides.
"""

import asyncio
from types import SimpleNamespace

import pytest
from claims_series import TERMS, FakeOpponent, StubPolicy, _nothing, play_series

from engine.config import load_config


@pytest.fixture
def config():
    return load_config("config/game.json")


@pytest.fixture
def apps(config):
    return {role: SimpleNamespace(config=config, inbox=[], audits=[], policy=StubPolicy(),
                                  terms=dict(TERMS),
                                  identity=lambda: {"group_name": "aviayeli"})
            for role in ("police", "thief")}


def test_each_sub_game_uses_the_call_for_the_side_we_play(apps):
    """The factory is asked once per sub-game, with the role we play in it."""
    asked = []
    peer = FakeOpponent({r: a.inbox for r, a in apps.items()})

    def call_for(role):
        asked.append(role)
        return peer

    asyncio.run(play_series(apps, None, sub_games=4, seed=1, wait=_nothing,
                            max_steps=1, max_polls=3, call_for=call_for))

    assert asked == ["police", "thief", "police", "thief"]


def test_a_plain_callable_still_serves_the_whole_series(apps):
    """The single-endpoint opponent: one call, every sub-game, unchanged."""
    peer = FakeOpponent({r: a.inbox for r, a in apps.items()})

    summaries = asyncio.run(play_series(apps, peer, sub_games=2, seed=1,
                                        wait=_nothing, max_steps=1, max_polls=3))

    assert [s["sub_game"] for s in summaries] == [1, 2]
