"""The peer plays from its trained table, greedily (FR6, D5).

D5 rules match play GREEDY. The trained tables carry a residual epsilon of
~0.0135 after 2000 decayed games, so a peer that simply reused the training
settings would still play a random move roughly one turn in seventy-four —
throwing away points in a scored series to sample moves it already has values
for.
"""

import json
from pathlib import Path

import pytest

from mcp_server.server import create_app


class _AlwaysExploreRng:
    """``random() == 0.0`` explores for ANY epsilon strictly above zero."""

    def random(self):
        return 0.0

    def choice(self, options):
        return "EXPLORED"


def test_the_app_carries_a_policy_for_its_own_engine_role(app):
    assert app.policy.role == "cop"


def test_the_thief_peer_gets_the_thief_engine_role(secure_config_root):
    thief = create_app("thief", config_root=secure_config_root)

    assert thief.policy.role == "thief"


def test_the_peer_loads_a_non_empty_table(app):
    assert app.policy.qvalues.q_table


def test_match_play_epsilon_is_zero(app):
    """Asserted directly, not inferred from sampled behaviour."""
    assert app.policy.qvalues.epsilon == 0.0


def test_a_greedy_peer_never_explores(app):
    """With epsilon 0 the rng cannot divert the choice, however it answers."""
    chosen = app.policy.qvalues.select_action((None, 0), _AlwaysExploreRng())

    assert chosen != "EXPLORED"
    assert chosen == "S", "S holds the highest seeded value"


def test_a_missing_table_fails_loudly(secure_config_root):
    (Path(secure_config_root) / "police" / "q_table.json").unlink()

    with pytest.raises(FileNotFoundError):
        create_app("police", config_root=secure_config_root)


def test_a_state_layout_version_mismatch_fails_loudly(secure_config_root):
    table = Path(secure_config_root) / "police" / "q_table.json"
    payload = json.loads(table.read_text())
    payload["state_layout_version"] += 1
    table.write_text(json.dumps(payload))

    with pytest.raises(ValueError):
        create_app("police", config_root=secure_config_root)


def test_a_table_that_loads_but_is_EMPTY_is_rejected(secure_config_root):
    """A peer that looks trained and plays from nothing is the worst outcome.

    An empty table parses and version-checks perfectly well, so nothing in
    QValues.load rejects it; the peer would start and silently play the first
    move in move_set forever.
    """
    table = Path(secure_config_root) / "police" / "q_table.json"
    payload = json.loads(table.read_text())
    payload["q_values"] = []
    table.write_text(json.dumps(payload))

    with pytest.raises(ValueError):
        create_app("police", config_root=secure_config_root)


def test_the_peer_does_not_read_the_production_data_directory(app):
    """Tests must never depend on, or disturb, the committed deliverables."""
    assert "data/" not in app.policy.settings.qtable_path


def test_the_peer_table_knows_its_engine_role_for_the_fallback(app):
    """Without a role the off-manifold fallback silently disables itself."""
    assert app.policy.qvalues.role == "cop"


def test_the_thief_peer_table_knows_its_own_role(secure_config_root):
    thief = create_app("thief", config_root=secure_config_root)

    assert thief.policy.qvalues.role == "thief"
