"""Tests for additional thief deception variants."""

import pytest

from agent.agent_core import AgentPolicy
from strategy.belief import BeliefTracker


class TestMoreThiefDeception:
    """Test additional THIEF deception cases."""

    def test_thief_e_states_west(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """THIEF moving E states 'west' (opposite)."""
        policy = AgentPolicy("thief", game_config, strategy_settings, qvalues, pheromones, belief)
        belief = BeliefTracker(game_config, strategy_settings)

        intent = policy.intent_for_move("E")

        assert "west" in intent.lower()
        verdict = belief.record("opponent", intent, "E")
        assert verdict == "dishonest"

    def test_thief_w_states_east(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """THIEF moving W states 'east' (opposite)."""
        policy = AgentPolicy("thief", game_config, strategy_settings, qvalues, pheromones, belief)
        belief = BeliefTracker(game_config, strategy_settings)

        intent = policy.intent_for_move("W")

        assert "east" in intent.lower()
        verdict = belief.record("opponent", intent, "W")
        assert verdict == "dishonest"

    def test_thief_s_states_north(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """THIEF moving S states 'north' (opposite)."""
        policy = AgentPolicy("thief", game_config, strategy_settings, qvalues, pheromones, belief)
        belief = BeliefTracker(game_config, strategy_settings)

        intent = policy.intent_for_move("S")

        assert "north" in intent.lower()
        verdict = belief.record("opponent", intent, "S")
        assert verdict == "dishonest"

    def test_thief_stay_maps_to_stay_and_is_honest(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """THIEF moving STAY states 'stay' (truthful due to involution)."""
        policy = AgentPolicy("thief", game_config, strategy_settings, qvalues, pheromones, belief)
        belief = BeliefTracker(game_config, strategy_settings)

        intent = policy.intent_for_move("STAY")

        assert "stay" in intent.lower()
        verdict = belief.record("opponent", intent, "STAY")
        assert verdict == "honest"

    def test_unknown_move_raises_rather_than_producing_empty_intent(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """An unrecognised token must fail loudly, not yield an unscorable ''."""
        policy = AgentPolicy("thief", game_config, strategy_settings, qvalues, pheromones, belief)

        with pytest.raises(ValueError):
            policy.intent_for_move("NORTHWEST")
