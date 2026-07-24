"""Episode orchestrator for the game engine (FR6 termination, FR7 determinism).

Composes engine.config, engine.board, engine.player, engine.actions, and
engine.resolver to drive a full cop/thief episode. All resolution and
capture logic is delegated to engine.resolver.resolve_turn; this module
only manages episode-level state, history, and termination.
"""

from dataclasses import dataclass

from engine.actions import Action, parse_action
from engine.board import Board
from engine.config import GameConfig
from engine.player import PlayerState
from engine.resolver import TurnResult, resolve_turn


@dataclass
class TurnRecord:
    """A single logged turn: the submitted actions and their resolution.

    Attributes:
        cop_action: The Action the cop submitted this turn.
        thief_action: The Action the thief submitted this turn.
        result: The TurnResult produced by resolve_turn for this turn.
    """

    cop_action: Action
    thief_action: Action
    result: TurnResult


class GameEpisode:
    """Orchestrates a single cop/thief episode: state, history, termination."""

    def __init__(self, config: GameConfig):
        """Initialize the episode from a GameConfig and reset to start state.

        Args:
            config: GameConfig instance describing the episode parameters.
        """
        self.config = config
        self.reset()

    def reset(self):
        """Reset the episode to its initial state (may be called to restart)."""
        self.board = Board(self.config)
        self.cop_state = PlayerState(tuple(self.config.cop_start), "cop")
        self.thief_state = PlayerState(tuple(self.config.thief_start), "thief")
        self.turn_count = 0
        self.is_terminated = False
        self.history = []

    def step(self, cop_token: str, thief_token: str):
        """Advance the episode by one turn.

        Args:
            cop_token: The cop's action token (e.g. "N", "STAY").
            thief_token: The thief's action token (e.g. "N", "STAY").

        Returns:
            The TurnResult for this turn, or (if already terminated) the
            last recorded TurnResult (or None if history is empty). No
            state is mutated once the episode has terminated.

        Raises:
            InvalidActionError: If either token fails to parse. Parsing
                happens before any state mutation, so state is left
                untouched when this is raised.
        """
        if self.is_terminated:
            return self.history[-1].result if self.history else None

        cop_action = parse_action(cop_token)
        thief_action = parse_action(thief_token)

        result = resolve_turn(
            self.board, self.cop_state, self.thief_state, cop_action, thief_action
        )

        self.cop_state.position = result.cop_position
        self.thief_state.position = result.thief_position
        self.turn_count += 1
        self.history.append(TurnRecord(cop_action, thief_action, result))

        if result.captured:
            self.is_terminated = True
        elif self.turn_count >= self.config.max_moves:
            self.is_terminated = True

        return result

    def replay(self, actions):
        """Reset and replay a sequence of (cop_token, thief_token) pairs.

        Args:
            actions: List of (cop_token, thief_token) tuples to step through
                in order.

        Returns:
            self, after having been reset and stepped through actions.
        """
        self.reset()
        for cop_token, thief_token in actions:
            self.step(cop_token, thief_token)
        return self
