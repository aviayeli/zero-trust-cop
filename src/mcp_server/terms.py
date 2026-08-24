"""Extract the AGREED TERMS -- the subset of game.json both peers must match.

The terms are the preimage of the pre-game agreement signature and of
``game_uid`` (book App. F). They are extracted, never taken wholesale: a uid
derived from the entire ``game.json`` is stable, reproducible and identical
across all four of our own artifacts, so those join each other perfectly and
only the CROSS-team join fails -- silently, because the uid never crosses the
wire and every game value in the two reports can agree exactly while the uid
does not.

The mapping exists because our config groups values by subsystem while the
terms are flat and use the book's names. Only the KEY NAMES live here; every
VALUE is read from ``game.json``, so no tunable is inlined in source.

Missing keys propagate as KeyError rather than defaulting. A silently
defaulted term hashes to a uid the opponent cannot reach, which is the exact
failure this module exists to prevent -- a loud setup error is strictly better.
"""

from __future__ import annotations

# term name -> (config section, key within that section)
_TERM_SOURCES = {
    "board_size": ("board_and_agents", "grid_size"),
    "thief_start": ("board_and_agents", "thief_start"),
    "cop_start": ("board_and_agents", "cop_start"),
    "axis_origin_corner": ("board_and_agents", "axis_origin_corner"),
    "axis_start_index": ("board_and_agents", "axis_start_index"),
    "max_steps": ("movement_and_barriers", "max_moves"),
    "barriers_max": ("movement_and_barriers", "max_barriers"),
    "smell_grid_size": ("pheromones", "pheromone_grid_size"),
    "decay_per_step": ("pheromones", "pheromone_decay"),
    "emit_intensity": ("pheromones", "pheromone_center_intensity"),
    "min_center_intensity": ("pheromones", "pheromone_min_center_intensity"),
    "setting": ("world", "map_area"),
    "hint_max_words": ("world", "hint_max_words"),
    "num_games": ("network_and_league", "num_games"),
}

# The closed key set, sorted. An extra or renamed key changes every hash the
# terms feed, so the set is asserted against in the test suite rather than
# left to drift.
TERMS_KEYS = tuple(sorted(_TERM_SOURCES))


def terms_from_config(config: dict) -> dict:
    """Flatten ``game.json`` into the agreed terms dict.

    Raises:
        KeyError: a term is absent from the config. Never defaulted -- see the
            module docstring.
    """
    return {
        term: config[section][key]
        for term, (section, key) in _TERM_SOURCES.items()
    }


def opponent_of(config: dict, group_id: str) -> str:
    """The OTHER party named in the contract's ``agreed_between`` pair.

    Both peers ship the same agreed contract, so the pair is already shared
    and neither side has to be told who it is playing. Deriving the opponent
    from it -- rather than from a command-line label -- is what keeps the two
    sides' ``game_id`` and ``game_uid`` identical.

    Raises:
        ValueError: the pair is not exactly two parties, or does not include
            us. Both would silently derive ids against the wrong pair, and a
            uid the opponent never computes is invisible until settlement.
    """
    pair = config.get("agreed_between")
    if not isinstance(pair, list) or len(pair) != 2:
        raise ValueError(
            f"agreed_between must name exactly two parties, got {pair!r}"
        )
    if group_id not in pair:
        raise ValueError(
            f"group_id {group_id!r} is not one of the agreed_between parties "
            f"{pair!r}; ids derived against the wrong pair are invisible "
            "until settlement"
        )
    return pair[0] if pair[1] == group_id else pair[1]
