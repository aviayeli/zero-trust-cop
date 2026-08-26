"""Tabular Q-learning with a compact, observable-board state layout.

The update rule is ``Q(s,a) <- Q(s,a) + alpha * (r + gamma * max Q(s',a')
- Q(s,a))``; terminal transitions omit the bootstrap term.  State keys are
``(relative_opponent, barrier_mask)``: off-board neighbours count as blocked,
and ``move_count`` is excluded so turns generalise rather than each becoming its
own state; unlearned states defer to ``strategy/fallback.py``.  Persistence stores
tuple keys as ``[[relative-row, relative-col] | null, mask, action, value]``.
"""

from pathlib import Path

from engine.config import GameConfig
from strategy.fallback import BARRIER_BIT_DIRECTIONS, policy_action
from strategy.qtable_io import load_table, save_table
from strategy.settings import StrategySettings


class QValues:
    """Learn and persist action values using injected game and strategy settings."""

    def __init__(self, config: GameConfig, settings: StrategySettings,
                 role: str | None = None) -> None:
        self.config = config
        self.settings = settings
        self.role = role
        self._epsilon = settings.exploration_rate
        self.q_table: dict[tuple[tuple[tuple[int, int] | None, int], str], float] = {}

    def state_key(
        self,
        own_position: tuple[int, int],
        opponent_position: tuple[int, int] | None,
        barriers: set[tuple[int, int]] | frozenset[tuple[int, int]],
    ) -> tuple[tuple[int, int] | None, int]:
        """Return the relative opponent location and adjacent-blocker bit mask."""
        row, col = own_position
        mask = 0
        for bit, (row_delta, col_delta) in enumerate(BARRIER_BIT_DIRECTIONS):
            neighbour = (row + row_delta, col + col_delta)
            off_board = not (
                0 <= neighbour[0] < self.config.grid_size
                and 0 <= neighbour[1] < self.config.grid_size
            )
            if off_board or neighbour in barriers:
                mask |= 1 << bit
        relative_opponent = (
            None
            if opponent_position is None
            else (opponent_position[0] - row, opponent_position[1] - col)
        )
        return relative_opponent, mask

    def q_value(self, state: tuple, action: str) -> float:
        """Read an action value, using the configured value for unseen entries."""
        return self.q_table.get((state, action), self.settings.initial_q_value)

    def update(
        self,
        state: tuple,
        action: str,
        reward: float,
        next_state: tuple,
        terminal: bool,
    ) -> float:
        """Apply one exact temporal-difference update and return the new value."""
        current = self.q_value(state, action)
        bootstrap = (
            0.0
            if terminal
            else self.settings.discount_factor
            * max(self.q_value(next_state, next_action) for next_action in self.config.move_set)
        )
        target = reward + bootstrap
        updated = current + self.settings.learning_rate * (target - current)
        self.q_table[(state, action)] = updated
        return updated

    def reward(self, role: str, outcome: str) -> int:
        """Return the shared game reward, rejecting unknown engine vocabulary."""
        role_rewards = {
            "capture": {"cop": self.config.capture_cop, "thief": self.config.capture_thief},
            "survival": {"cop": self.config.survival_cop, "thief": self.config.survival_thief},
            "tie": {"cop": self.config.tie_score, "thief": self.config.tie_score},
            "technical_loss": {
                "cop": self.config.technical_loss,
                "thief": self.config.technical_loss,
            },
        }
        try:
            return role_rewards[outcome][role]
        except KeyError as error:
            raise ValueError(f"unknown role or outcome: {role!r}, {outcome!r}") from error

    def best_action(self, state: tuple, forbid=(), prefer=None) -> str:
        """Return the policy's move; the plain greedy read is only its fallback.

        ``forbid`` drops refuted moves (PRD_18) BEFORE either mode ranks
        anything: filtering afterwards substitutes an unsanctioned move.
        """
        if not self.config.move_set:
            raise ValueError("move_set must contain at least one action")
        chosen = policy_action(self, state, forbid, prefer)
        if chosen is not None:
            return chosen
        return max(self._allowed(forbid), key=lambda a: self.q_value(state, a))

    def decay_epsilon(self) -> None:
        """Apply one decay step, clamped at epsilon_floor."""
        self._epsilon *= self.settings.epsilon_decay_factor
        self._epsilon = max(self._epsilon, self.settings.epsilon_floor)

    @property
    def epsilon(self) -> float:
        """Read the current mutable epsilon value."""
        return self._epsilon

    def select_action(self, state: tuple, rng, forbid=(), prefer=None) -> str:
        """Choose epsilon-greedily using the caller-provided generator."""
        if rng.random() < self._epsilon:
            return rng.choice(self._allowed(forbid))
        return self.best_action(state, forbid, prefer)

    def _allowed(self, forbid) -> list:
        """The move set minus refused moves, never empty."""
        return [a for a in self.config.move_set if a not in forbid] \
            or list(self.config.move_set)

    def save(self, path: str | Path | None = None) -> None:
        """Persist the table; see ``strategy.qtable_io``."""
        save_table(self.q_table, self.settings, path)

    def load(self, path: str | Path | None = None) -> None:
        """Replace the table from disk; see ``strategy.qtable_io``."""
        self.q_table = load_table(self.settings, path)
