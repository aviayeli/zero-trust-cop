"""Tabular Q-learning with a compact, observable-board state layout.

The update rule is ``Q(s,a) <- Q(s,a) + alpha * (r + gamma * max Q(s',a')
- Q(s,a))``; terminal transitions omit the bootstrap term.  State keys are
``(relative_opponent, barrier_mask)``: off-board neighbours count as blocked,
and ``move_count`` is excluded so turns generalise rather than each becoming its
own state; unlearned states defer to ``strategy/fallback.py``.  Persistence stores
tuple keys as ``[[relative-row, relative-col] | null, mask, action, value]``.
"""

import json
from pathlib import Path

from engine.config import GameConfig
from strategy.fallback import BARRIER_BIT_DIRECTIONS, policy_action
from strategy.settings import StrategySettings


STATE_LAYOUT_VERSION = 1


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

    def best_action(self, state: tuple) -> str:
        """Choose the highest-valued configured move, retaining move-set tie order."""
        if not self.config.move_set:
            raise ValueError("move_set must contain at least one action")
        best = self.config.move_set[0]
        best_value = self.q_value(state, best)
        for action in self.config.move_set[1:]:
            value = self.q_value(state, action)
            if value > best_value:
                best, best_value = action, value
        return policy_action(self, state) or best

    def decay_epsilon(self) -> None:
        """Apply one decay step, clamped at epsilon_floor."""
        self._epsilon *= self.settings.epsilon_decay_factor
        self._epsilon = max(self._epsilon, self.settings.epsilon_floor)

    @property
    def epsilon(self) -> float:
        """Read the current mutable epsilon value."""
        return self._epsilon

    def select_action(self, state: tuple, rng) -> str:
        """Choose epsilon-greedily using the caller-provided random generator."""
        if rng.random() < self._epsilon:
            return rng.choice(self.config.move_set)
        return self.best_action(state)

    def save(self, path: str | Path | None = None) -> None:
        """Write the table and state-layout version as reversible JSON records."""
        destination = Path(self.settings.qtable_path if path is None else path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        entries = []
        for (state, action), value in self.q_table.items():
            relative, mask = state
            encoded_relative = None if relative is None else list(relative)
            entries.append([encoded_relative, mask, action, value])
        destination.write_text(
            json.dumps({"state_layout_version": STATE_LAYOUT_VERSION, "q_values": entries})
        )

    def load(self, path: str | Path | None = None) -> None:
        """Replace this table from JSON after verifying its state-layout version."""
        source = Path(self.settings.qtable_path if path is None else path)
        payload = json.loads(source.read_text())
        if payload["state_layout_version"] != STATE_LAYOUT_VERSION:
            raise ValueError("Q-table state layout version does not match")
        loaded: dict[tuple[tuple[tuple[int, int] | None, int], str], float] = {}
        for relative, mask, action, value in payload["q_values"]:
            state = (None if relative is None else tuple(relative), mask)
            loaded[(state, action)] = value
        self.q_table = loaded
