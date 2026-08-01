"""The reward signal must be SPARSE: only the terminating transition pays.

PLAN_05's accepted Conductor ruling is "sparse terminal rewards only"; a
per-turn survival reward would pay an agent for merely existing and drown
out the terminal signal it is supposed to learn from.
"""

from dataclasses import dataclass

from agent.agent_core import AgentPolicy
from scripts.run_tournament import train_tournament
from scripts.tournament_loop import terminal_outcome


@dataclass
class _FakeResult:
    """Stand-in for a TurnResult, to reach both terminal branches directly."""

    captured: bool


def test_terminal_outcome_maps_a_capture():
    assert terminal_outcome(_FakeResult(captured=True)) == "capture"


def test_terminal_outcome_maps_running_out_of_moves_to_survival():
    assert terminal_outcome(_FakeResult(captured=False)) == "survival"


def _record_learn_calls(monkeypatch):
    """Spy on every AgentPolicy.learn call, keeping the real behaviour."""
    seen = []
    original = AgentPolicy.learn

    def spy(self, state, action, reward, next_state, terminal):
        seen.append((self.role, reward, terminal))
        return original(self, state, action, reward, next_state, terminal)

    monkeypatch.setattr(AgentPolicy, "learn", spy)
    return seen


def test_non_terminal_transitions_learn_from_zero(
    config, training_settings, monkeypatch
):
    cop_settings, thief_settings = training_settings(num_games=2)
    seen = _record_learn_calls(monkeypatch)

    train_tournament(config, cop_settings, thief_settings, seed=7)

    non_terminal = [reward for _, reward, terminal in seen if not terminal]
    assert non_terminal, "expected the episodes to contain non-terminal turns"
    assert set(non_terminal) == {0.0}


def test_exactly_one_paid_transition_per_role_per_game(
    config, training_settings, monkeypatch
):
    cop_settings, thief_settings = training_settings(num_games=3)
    seen = _record_learn_calls(monkeypatch)

    train_tournament(config, cop_settings, thief_settings, seed=7)

    paid = [(role, reward) for role, reward, terminal in seen if terminal]
    assert len(paid) == 6, "3 games x 2 roles = 6 paid transitions"
    assert all(reward != 0.0 for _, reward in paid)


def test_a_game_score_is_a_single_terminal_reward(config, training_settings):
    """A dense per-turn reward would push scores far above these values."""
    cop_settings, thief_settings = training_settings(num_games=3)

    scores = train_tournament(config, cop_settings, thief_settings, seed=7)

    allowed = {
        (config.capture_cop, config.capture_thief),
        (config.survival_cop, config.survival_thief),
    }
    assert set(scores) <= allowed
