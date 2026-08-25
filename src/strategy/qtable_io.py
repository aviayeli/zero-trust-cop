"""Reading and writing a Q-table, split from the table itself.

``strategy/qvalues.py`` sits on the 150-line limit and PRD_18 added real
behaviour to it, so the persistence pair moved out. The seam is genuine rather
than arithmetic: everything here is about a FILE -- its encoding, its version
gate, and the tuple/list round trip JSON forces -- and nothing here has an
opinion about what a value means or which move it favours.

The version gate is the load-bearing part. A table written under an older
state layout would load without complaint and then be indexed with keys it was
never trained on: a silently wrong agent, which is worse than a refusal.
"""

from __future__ import annotations

import json
from pathlib import Path

STATE_LAYOUT_VERSION = 1


def _resolve(settings, path) -> Path:
    return Path(settings.qtable_path if path is None else path)


def save_table(q_table: dict, settings, path=None) -> None:
    """Write the table and its state-layout version as reversible records."""
    destination = _resolve(settings, path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    for (state, action), value in q_table.items():
        relative, mask = state
        entries.append([None if relative is None else list(relative),
                        mask, action, value])
    destination.write_text(json.dumps(
        {"state_layout_version": STATE_LAYOUT_VERSION, "q_values": entries}))


def load_table(settings, path=None) -> dict:
    """Read a table back, refusing one written under another state layout.

    Raises:
        ValueError: the layout version differs. Loading it anyway would index
            the table with keys it was never trained on.
    """
    payload = json.loads(_resolve(settings, path).read_text())
    if payload["state_layout_version"] != STATE_LAYOUT_VERSION:
        raise ValueError("Q-table state layout version does not match")
    loaded: dict = {}
    for relative, mask, action, value in payload["q_values"]:
        state = (None if relative is None else tuple(relative), mask)
        loaded[(state, action)] = value
    return loaded
