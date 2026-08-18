"""Which opponent the learner faces this episode, and how often.

The mix IS the phase: 40% a scripted greedy opponent, 40% the co-evolving
learner, 20% random. Collapse it onto one bucket and this is self-play with
extra steps — producing tables that look trained while carrying exactly the
overfitting the phase exists to remove (PLAN.md §10.10).

Weights live in ``config/training.json`` because they are OUR training policy,
not part of the contract negotiated with the opposing group.
"""

import json
import os
from dataclasses import dataclass

_DEFAULT_CONFIG_ROOT = "config"
_FILENAME = "training.json"


@dataclass(frozen=True)
class TrainingSettings:
    """The diverse-opponent training policy."""

    episodes: int
    layout_seeds: int
    opponent_mix: dict


def training_settings_path(config_root: str | None = None) -> str:
    root = config_root or os.environ.get("ZTC_CONFIG_ROOT", _DEFAULT_CONFIG_ROOT)
    return os.path.join(root, _FILENAME)


def load_training_settings(config_root: str | None = None) -> TrainingSettings:
    """Load the training policy, failing loudly on any missing key.

    Raises:
        ValueError: the declared opponent weights do not sum to 1.
    """
    with open(training_settings_path(config_root), encoding="utf-8") as source:
        payload = json.load(source)
    mix = payload["opponent_mix"]
    total = sum(mix.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"opponent_mix must sum to 1, got {total}")
    return TrainingSettings(
        episodes=payload["episodes"],
        layout_seeds=payload["layout_seeds"],
        opponent_mix=mix,
    )


def pick_bucket(mix: dict, draw: float) -> str:
    """Name the bucket a uniform ``draw`` in [0, 1) falls into.

    Takes the draw rather than an RNG so a caller's reproducibility is its own
    business, and so the boundaries are directly testable.
    """
    threshold = 0.0
    for bucket, weight in mix.items():
        threshold += weight
        if draw < threshold:
            return bucket
    return bucket
