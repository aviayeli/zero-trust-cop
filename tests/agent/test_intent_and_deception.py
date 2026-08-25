"""Tests for intent generation and deception logic."""


from agent.agent_core import AgentPolicy
from strategy.belief import BeliefTracker


class TestCopIntent:
    """Test COP's honest intent (states actual move direction)."""

    def test_cop_states_actual_direction_north(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """COP moving N states 'north'."""
        policy = AgentPolicy("cop", game_config, strategy_settings, qvalues, pheromones, belief)
        belief = BeliefTracker(game_config, strategy_settings)

        intent = policy.intent_for_move("N")

        assert "north" in intent.lower()
        verdict = belief.record("opponent", intent, "N")
        assert verdict == "honest"

    def test_cop_states_actual_direction_south(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """COP moving S states 'south'."""
        policy = AgentPolicy("cop", game_config, strategy_settings, qvalues, pheromones, belief)
        belief = BeliefTracker(game_config, strategy_settings)

        intent = policy.intent_for_move("S")

        assert "south" in intent.lower()
        verdict = belief.record("opponent", intent, "S")
        assert verdict == "honest"

    def test_cop_states_actual_direction_east(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """COP moving E states 'east'."""
        policy = AgentPolicy("cop", game_config, strategy_settings, qvalues, pheromones, belief)
        belief = BeliefTracker(game_config, strategy_settings)

        intent = policy.intent_for_move("E")

        assert "east" in intent.lower()
        verdict = belief.record("opponent", intent, "E")
        assert verdict == "honest"

    def test_cop_states_actual_direction_west(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """COP moving W states 'west'."""
        policy = AgentPolicy("cop", game_config, strategy_settings, qvalues, pheromones, belief)
        belief = BeliefTracker(game_config, strategy_settings)

        intent = policy.intent_for_move("W")

        assert "west" in intent.lower()
        verdict = belief.record("opponent", intent, "W")
        assert verdict == "honest"


class TestThiefDeception:
    """Test THIEF's inverted intent (opposite of actual move)."""

    def test_thief_n_states_south(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """THIEF moving N states 'south' (opposite)."""
        policy = AgentPolicy("thief", game_config, strategy_settings, qvalues, pheromones, belief)
        belief = BeliefTracker(game_config, strategy_settings)

        intent = policy.intent_for_move("N")

        assert "south" in intent.lower()
        verdict = belief.record("opponent", intent, "N")
        assert verdict == "dishonest"
