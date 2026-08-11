"""The reward signal is TERMINAL-DOMINATED but no longer terminal-ONLY.

PLAN_05's original ruling was "sparse terminal rewards only". That ruling had
a degenerate consequence the audit caught: bumping a wall and taking a useful
step were worth exactly the same, so nothing in the signal separated a policy
that pursues from one that grinds into the north boundary forever.

Two small shaping terms fix that (``invalid_move_penalty`` and ``step_cost``,
exercised directly in ``test_shaping_terms.py``). What is asserted HERE is that
they stay in their place: the outcome reward still arrives exactly once per
role per game, and the reported GAME SCORE is that outcome alone.
"""

from dataclasses import dataclass, replace

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


def test_non_terminal_transitions_carry_only_shaping(
    config, training_settings, monkeypatch
):
    """Every non-terminal reward is a sum of the two configured shaping terms."""
    cop_settings, thief_settings = training_settings(num_games=2)
    seen = _record_learn_calls(monkeypatch)

    train_tournament(config, cop_settings, thief_settings, seed=7)

    allowed = {
        round(cop_settings.step_cost, 6),
        round(cop_settings.step_cost + cop_settings.invalid_move_penalty, 6),
    }
    non_terminal = [round(reward, 6) for _, reward, terminal in seen if not terminal]
    assert non_terminal, "expected the episodes to contain non-terminal turns"
    assert set(non_terminal) <= allowed


def test_a_blocked_move_really_does_occur_during_training(
    config, training_settings, monkeypatch
):
    """The penalty would be dead code if training never bumped a wall."""
    cop_settings, thief_settings = training_settings(num_games=20)
    seen = _record_learn_calls(monkeypatch)

    train_tournament(config, cop_settings, thief_settings, seed=7)

    penalised = round(cop_settings.step_cost + cop_settings.invalid_move_penalty, 6)
    assert penalised in {round(reward, 6) for _, reward, _ in seen}


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
    """Shaping steers LEARNING; it must never leak into the reported score."""
    cop_settings, thief_settings = training_settings(num_games=3)

    scores = train_tournament(config, cop_settings, thief_settings, seed=7)

    allowed = {
        (config.capture_cop, config.capture_thief),
        (config.survival_cop, config.survival_thief),
    }
    assert set(scores) <= allowed


def test_zeroing_both_shaping_terms_restores_the_old_sparse_signal(
    config, training_settings, monkeypatch
):
    """The shaping is configuration, not a hardcoded behaviour change."""
    cop_settings, thief_settings = training_settings(num_games=2)
    unshaped = dict(step_cost=0.0, invalid_move_penalty=0.0)
    seen = _record_learn_calls(monkeypatch)

    train_tournament(
        config,
        replace(cop_settings, **unshaped),
        replace(thief_settings, **unshaped),
        seed=7,
    )

    assert {reward for _, reward, terminal in seen if not terminal} == {0.0}
