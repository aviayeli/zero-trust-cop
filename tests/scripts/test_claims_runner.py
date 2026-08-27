"""A whole reference-v3 series, sides swapping every sub-game (PRD_10 10.6).

Both peers are served for the whole series because the schedule turns over:
their turns land in the inbox of whichever of our peers is playing that
sub-game, and that peer changes every time. A run that served only the side
it starts as stalls the moment the schedule flips.

The per-sub-game RESET is asserted for the same reason it exists: a turn left
in the inbox across a boundary would satisfy a step of the NEXT sub-game with
a message about the previous one, and both peers would sign it.
"""


from types import SimpleNamespace

import pytest
from claims_series import (  # noqa: F401  -- `apps`/`config` are FIXTURES
    StubPolicy,
    _series,
    apps,
    config,
)


def test_a_six_sub_game_series_swaps_sides_every_time(apps):
    _, summaries = _series(apps)

    assert [s["role"] for s in summaries] == \
        ["police", "thief", "police", "thief", "police", "thief"]
    assert [s["sub_game"] for s in summaries] == [1, 2, 3, 4, 5, 6]


def test_starting_as_the_thief_flips_the_whole_schedule(apps):
    _, summaries = _series(apps, sub_games=3, first_role="thief")

    assert [s["role"] for s in summaries] == ["thief", "police", "thief"]


def test_one_audit_per_sub_game_declaring_the_side_we_played(apps):
    peer, summaries = _series(apps)

    assert [audit["sender"] for audit in peer.audits()] == \
        [s["role"] for s in summaries]


def test_the_inbox_is_emptied_between_sub_games(apps):
    """A turn surviving the boundary would satisfy the next sub-game's step 1.

    Three sub-games, so we play police TWICE. Without the reset that inbox
    would hold four turns and sub-game 3 would resolve step 1 against a
    message sealed in sub-game 1.
    """
    _series(apps, sub_games=3, max_steps=2)

    assert len(apps["police"].inbox) == 2


def test_their_smell_grid_feeds_our_belief(apps):
    _series(apps, sub_games=1, max_steps=2)

    assert apps["police"].policy.deposits == [(3, 3), (3, 3)]


def test_a_capture_claim_that_lands_ends_that_sub_game_early(apps, config):
    _, summaries = _series(apps, sub_games=2, max_steps=5,
                           claim=tuple(config.thief_start))

    thief_game = [s for s in summaries if s["role"] == "thief"][0]
    assert thief_game["terminal_reason"] == "capture"
    assert thief_game["steps"] == 2


def test_a_scheduled_role_with_no_peer_is_refused(config):
    with pytest.raises(ValueError, match="no peer for scheduled role"):
        _series({"police": SimpleNamespace(config=config, inbox=[], audits=[],
                                           policy=StubPolicy())}, sub_games=2)


# --- the inbound audit reaches the summary (PRD 22) --------------------------

def test_an_inbound_audit_is_harvested_into_the_sub_game_summary(apps):
    """The wiring between the two halves, which nothing else covers.

    `submit_audit` verifies and appends to app.audits inside the SERVER;
    build_log writes whatever the summary carries. Neither proves the runner
    moves one to the other. Removing that harvest left every other test green,
    so this is the one that fails when it goes.
    """
    disclosed = {"sender": "thief", "records": [{"payload": {"step": 1},
                                                 "nonce": "n", "commit": "c"}],
                 "result_claim": "survival", "verdict": {"status": "accepted"}}

    # Injected DURING the sub-game, as a real inbound submit_audit arrives.
    # Seeding it beforehand proves nothing: the runner clears the accumulator
    # at sub-game start, which is the behaviour the next test pins.
    original = apps["police"].policy.decide

    def decide(*args, **kwargs):
        if not apps["police"].audits:
            apps["police"].audits.append(disclosed)
        return original(*args, **kwargs)

    apps["police"].policy.decide = decide

    _, summaries = _series(apps, sub_games=1, max_steps=2)

    assert summaries[0]["their_disclosed_audits"] == [disclosed]


def test_the_audit_accumulator_is_cleared_between_sub_games(apps):
    """A later sub-game must not inherit an earlier one's audit. The clear
    sits beside app.inbox.clear() so the two cannot drift apart.

    THREE sub-games, not two: roles alternate, so the police app plays 1 and
    3 while 2 is the thief's. Checking sub-game 2 would inspect an app that
    was never seeded and would pass with the clear deleted.
    """
    apps["police"].audits.append({"sender": "thief", "records": [],
                                  "result_claim": "survival", "verdict": {}})

    _, summaries = _series(apps, sub_games=3, max_steps=2)

    police_games = [s for s in summaries if s["role"] == "police"]
    assert len(police_games) == 2
    assert police_games[-1]["their_disclosed_audits"] == []
