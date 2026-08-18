"""The thief README's claims about its own Q-table, checked against the table.

`STRATEGY_BLOCK` in `scripts/thief_readme.py` is INSERTED content, not a
substitution anchor. The matrix rules fail loudly when the cop README moves
underneath them; nothing did that for these figures, so when the 2026-08-11
retrain grew the thief table the block kept asserting **128 entries across 46
states, topping out at 4.9968** against a table holding **391 across 144** and
peaking at **4.9999** — and shipped that to the public thief repository.

Reading the table at runtime closes the gap for every future retrain. Unlike
the conversion tests these are valid on BOTH branches: they compare a module
constant against a data file, never against a README, and the thief branch is
where the figures actually ship.
"""

import json
import re

from pathlib import Path

from strategy.settings import load_strategy_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# The three figures the strategy block states about the thief's own table.
_FIGURES = re.compile(
    r"holds (\d+) entries across\s+(\d+) states, topping out at \*\*(\d+\.\d+)\*\*"
)


def _shipped_table_facts():
    """(entries, states, peak) read from the table the thief actually ships."""
    path = load_strategy_settings("thief").qtable_path
    records = json.loads((PROJECT_ROOT / path).read_text(encoding="utf-8"))
    entries = records["q_values"]
    states = {(tuple(rel) if rel else None, mask) for rel, mask, _, _ in entries}
    return len(entries), len(states), max(value for *_, value in entries)


def _documented_figures(block):
    """The same three figures, as the README states them."""
    quoted = _FIGURES.search(block)
    assert quoted, "the thief strategy block no longer states its table figures"
    return int(quoted[1]), int(quoted[2]), float(quoted[3])


def test_the_documented_entry_count_matches_the_table(regenerator):
    documented, _, _ = _documented_figures(regenerator.STRATEGY_BLOCK)

    assert documented == _shipped_table_facts()[0]


def test_the_documented_state_count_matches_the_table(regenerator):
    _, documented, _ = _documented_figures(regenerator.STRATEGY_BLOCK)

    assert documented == _shipped_table_facts()[1]


def test_the_documented_peak_q_value_matches_the_table(regenerator):
    """Quoted to four decimal places, so compare at that precision."""
    _, _, documented = _documented_figures(regenerator.STRATEGY_BLOCK)

    assert documented == round(_shipped_table_facts()[2], 4)


def config_capture_thief():
    from engine.config import load_config

    return load_config(str(PROJECT_ROOT / "config" / "game.json")).capture_thief


def test_the_peak_matches_the_argument_the_block_makes(regenerator):
    """The block's ARGUMENT must stay true; it has now moved twice.

    Self-play left the peak just under `capture_thief` and the prose said the
    thief was being caught. Phase 11 pushed it past 5. Diverse training pins it
    AT 5 while the evader became genuinely strong — so the strength argument
    now rests on the table's breadth, not its height, and the prose says that.
    This guards the claim rather than the number.
    """
    _, _, peak = _shipped_table_facts()

    assert peak >= config_capture_thief(), "the peak fell BELOW capture_thief"
    assert "pinned almost exactly to" in regenerator.STRATEGY_BLOCK
    assert "90.0% survival" in regenerator.STRATEGY_BLOCK
