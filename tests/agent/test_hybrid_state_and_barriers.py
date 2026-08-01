"""Tests for hybrid state source and barrier scanning."""

import pytest

from engine.board import Board
from agent.agent_core import AgentPolicy


class TestHybridStateSource:
    """Test the three branches of the hybrid opponent position source."""

    def test_resolved_position_takes_precedence(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """When resolved position exists, it wins."""
        policy = AgentPolicy("cop", game_config, strategy_settings, qvalues, pheromones, belief)
        resolved_pos = (3, 3)
        pheromones.deposit((5, 5))

        opponent_cell = policy.hybrid_opponent_cell(resolved_pos)

        assert opponent_cell == resolved_pos

    def test_fallback_to_pheromones_when_resolved_is_none(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """When resolved is None, use pheromones.strongest()."""
        policy = AgentPolicy("cop", game_config, strategy_settings, qvalues, pheromones, belief)
        pheromones.deposit((2, 2))
        pheromones.advance()

        opponent_cell = policy.hybrid_opponent_cell(None)

        assert opponent_cell == (2, 2)

    def test_none_when_both_resolved_and_pheromones_absent(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """When both are absent, return None."""
        policy = AgentPolicy("cop", game_config, strategy_settings, qvalues, pheromones, belief)

        opponent_cell = policy.hybrid_opponent_cell(None)

        assert opponent_cell is None

    def test_state_key_itself_applies_the_hybrid_fallback(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """state_key must resolve the hybrid itself, not trust the caller to."""
        policy = AgentPolicy("cop", game_config, strategy_settings, qvalues, pheromones, belief)
        board = Board(game_config)
        pheromones.deposit((0, 3))

        # No resolved position: the state must still encode the pheromone trace.
        fallback_state = policy.state_key((0, 0), None, board)
        expected = qvalues.state_key((0, 0), pheromones.strongest(), frozenset())

        assert fallback_state == expected
        assert fallback_state[0] is not None


class TestBarriers:
    """Test barrier scanning via Board.is_barrier."""

    def test_barriers_collected_by_scanning_board(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """Barriers are found by scanning Board.is_barrier, not private _barriers."""
        policy = AgentPolicy("cop", game_config, strategy_settings, qvalues, pheromones, belief)
        board = Board(game_config)
        board.place_barrier((1, 1))
        board.place_barrier((2, 2))

        barriers = policy.barriers(board)

        # Exact set: a scan that returned every cell, or ignored is_barrier,
        # would satisfy mere membership assertions but fails this.
        assert barriers == frozenset({(1, 1), (2, 2)})
        assert (0, 0) not in barriers
        assert isinstance(barriers, frozenset)

    def test_empty_board_yields_no_barriers(
        self, game_config, strategy_settings, qvalues, pheromones, belief
    ):
        """A board with no barriers must scan to an empty set, not every cell."""
        policy = AgentPolicy("cop", game_config, strategy_settings, qvalues, pheromones, belief)

        assert policy.barriers(Board(game_config)) == frozenset()
