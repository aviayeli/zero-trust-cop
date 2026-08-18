"""Per-episode opponent selection, weighted from configuration.

The mix is the entire point of the phase: 40% scripted, 40% the co-evolving
learner, 20% random. If selection silently collapsed onto one bucket we would
be back to self-play with extra steps, and the resulting tables would look
trained while carrying exactly the flaw this phase exists to remove.

So the distribution is asserted, not assumed, and the weights come from
`config/training.json` rather than literals.
"""

import json
from collections import Counter

import pytest

from scripts.opponent_pool import load_training_settings, pick_bucket

BUCKETS = ("scripted", "learning", "random")


@pytest.fixture(scope="module")
def settings():
    return load_training_settings()


def test_the_mix_is_read_from_configuration(settings):
    """No inlined 0.4/0.4/0.2 anywhere in source."""
    declared = json.loads(open("config/training.json", encoding="utf-8").read())

    assert settings.opponent_mix == declared["opponent_mix"]
    assert settings.episodes == declared["episodes"]


def test_the_declared_weights_sum_to_one(settings):
    assert sum(settings.opponent_mix.values()) == pytest.approx(1.0)


def test_every_bucket_is_reachable(settings):
    """A weight that never fires is a bucket that does not exist."""
    import random

    drawn = Counter(
        pick_bucket(settings.opponent_mix, random.Random(seed).random())
        for seed in range(400)
    )

    assert set(drawn) == set(BUCKETS)


def test_selection_matches_the_declared_proportions(settings):
    """Within tolerance, the realised mix must be the configured one."""
    import random

    rng = random.Random(20260818)
    drawn = Counter(pick_bucket(settings.opponent_mix, rng.random()) for _ in range(6000))

    for bucket, weight in settings.opponent_mix.items():
        assert drawn[bucket] / 6000 == pytest.approx(weight, abs=0.03)


def test_selection_is_deterministic_for_a_given_draw(settings):
    """Reproducibility: the same draw must always name the same bucket."""
    assert pick_bucket(settings.opponent_mix, 0.5) == pick_bucket(
        settings.opponent_mix, 0.5
    )


def test_the_boundaries_land_in_the_expected_buckets():
    mix = {"scripted": 0.4, "learning": 0.4, "random": 0.2}

    assert pick_bucket(mix, 0.0) == "scripted"
    assert pick_bucket(mix, 0.39) == "scripted"
    assert pick_bucket(mix, 0.41) == "learning"
    assert pick_bucket(mix, 0.81) == "random"
    assert pick_bucket(mix, 0.999) == "random"
