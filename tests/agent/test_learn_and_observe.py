"""Tests for decide, learn, and observe_opponent methods."""

import random
from dataclasses import replace
from unittest.mock import MagicMock

from agent.agent_core import AgentPolicy
from strategy.belief import BeliefTracker
from strategy.pheromones import PheromoneField
from strategy.qvalues import QValues


class TestThiefStayAndTruncation:
    """Test intent truncation."""

    def test_intent_truncated_to_hint_max_words(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """Intent is truncated to exactly hint_max_words words."""
        policy = AgentPolicy(
            "cop", game_config, strategy_settings, qvalues, pheromones, belief
        )

        full_intent = " ".join(["north"] + [f"word{n}" for n in range(24)])
        assert len(full_intent.split()) > 15

        truncated = policy.truncate_intent(
            full_intent, strategy_settings.hint_max_words
        )

        assert len(truncated.split()) == strategy_settings.hint_max_words
        assert truncated.split()[0] == "north"

    def test_decide_truncates_using_the_CONFIGURED_hint_max_words(
        self, game_config, qvalues, pheromones, belief, strategy_settings
    ):
        """decide must read hint_max_words from settings, not a hardcoded number.

        hint_max_words=0 makes the setting's effect observable: a policy that
        ignores the config still returns its one-word intent and fails here.
        """
        capped = replace(strategy_settings, hint_max_words=0)
        policy = AgentPolicy("cop", game_config, capped, qvalues, pheromones, belief)
        state = qvalues.state_key((0, 0), None, frozenset())

        _, intent = policy.decide(state, random.Random(42))

        assert intent == ""


class TestDecide:
    """Test the decide method (move + intent)."""

    def test_decide_returns_move_and_intent(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """decide returns (move, truncated_intent)."""
        policy = AgentPolicy("cop", game_config, strategy_settings, qvalues, pheromones, belief)
        state = qvalues.state_key((0, 0), None, frozenset())
        rng = random.Random(42)

        move, intent = policy.decide(state, rng)

        assert move in game_config.move_set
        assert isinstance(intent, str)
        assert len(intent) > 0


class TestObserveOpponent:
    """Test the observe_opponent method."""

    def test_observe_opponent_calls_advance_once_with_cell(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """pheromones.advance called exactly once with deposits=[cell]."""
        pheromones_mock = MagicMock(spec=PheromoneField)
        belief_mock = MagicMock(spec=BeliefTracker)
        policy = AgentPolicy("cop", game_config, strategy_settings, qvalues, pheromones_mock, belief_mock)

        policy.observe_opponent("opponent_role", "north", "N", (3, 3))

        pheromones_mock.advance.assert_called_once_with(deposits=[(3, 3)])

    def test_observe_opponent_advance_called_once_even_with_none_cell(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """pheromones.advance called once even when cell is None."""
        pheromones_mock = MagicMock(spec=PheromoneField)
        belief_mock = MagicMock(spec=BeliefTracker)
        policy = AgentPolicy("cop", game_config, strategy_settings, qvalues, pheromones_mock, belief_mock)

        policy.observe_opponent("opponent_role", "north", "N", None)

        pheromones_mock.advance.assert_called_once_with(deposits=[])


class TestLearn:
    """Test the learn method."""

    def test_learn_calls_qvalues_update_exactly_once(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """learn calls qvalues.update exactly once."""
        qvalues_mock = MagicMock(spec=QValues)
        policy = AgentPolicy("cop", game_config, strategy_settings, qvalues_mock, pheromones, belief)

        policy.learn((None, 0), "N", 10.0, (None, 0), terminal=False)

        qvalues_mock.update.assert_called_once()

    def test_learn_passes_terminal_true(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """learn passes terminal=True when asked."""
        qvalues_mock = MagicMock(spec=QValues)
        policy = AgentPolicy("cop", game_config, strategy_settings, qvalues_mock, pheromones, belief)

        policy.learn((None, 0), "N", 10.0, (None, 0), terminal=True)

        call_kwargs = qvalues_mock.update.call_args[1]
        assert call_kwargs["terminal"] is True
