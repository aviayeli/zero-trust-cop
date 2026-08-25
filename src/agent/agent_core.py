"""Policy layer that consumes strategy modules."""

from engine.config import GameConfig
from strategy.settings import StrategySettings


class AgentPolicy:
    """An injected policy that chooses moves, learns, and observes opponents."""

    _INVERSION = {"N": "S", "S": "N", "E": "W", "W": "E", "STAY": "STAY"}
    _DIRECTION_TEXT = {"N": "north", "S": "south", "E": "east", "W": "west",
                       "STAY": "stay"}

    def __init__(self, role, config, settings, qvalues, pheromones, belief):
        """Construct with injected dependencies."""
        self.role = role
        self.config = config
        self.settings = settings
        self.qvalues = qvalues
        self.pheromones = pheromones
        self.belief = belief

    def barriers(self, board):
        """Return frozenset of barrier cells by scanning Board.is_barrier."""
        barriers = set()
        for row in range(self.config.grid_size):
            for col in range(self.config.grid_size):
                if board.is_barrier((row, col)):
                    barriers.add((row, col))
        return frozenset(barriers)

    def hybrid_opponent_cell(self, resolved_pos):
        """Return opponent cell: resolved → pheromones.strongest → None (D2)."""
        if resolved_pos is not None:
            return resolved_pos
        return self.pheromones.strongest()

    def state_key(self, own_pos, resolved_opponent, board):
        """Build the state key, applying the D2 hybrid source itself.

        The hybrid is resolved HERE rather than by the caller, so a caller that
        passes only the resolved position cannot silently skip the fallback.
        """
        opponent = self.hybrid_opponent_cell(resolved_opponent)
        return self.qvalues.state_key(own_pos, opponent, self.barriers(board))

    def intent_for_move(self, move):
        """Map move to intent text: COP honest, THIEF inverted."""
        if move not in self._DIRECTION_TEXT:
            raise ValueError(f"unknown move token: {move!r}")
        if self.role == "thief":
            move = self._INVERSION[move]
        return self._DIRECTION_TEXT[move]

    def truncate_intent(self, text, max_words):
        """Truncate intent to max_words whitespace-separated words."""
        words = text.split()
        return " ".join(words[:max_words])

    def decide(self, state, rng, forbid=()):
        """Return (move, truncated_intent) for the state.

        ``forbid`` is the thaw's verdict for this step (PRD_18): moves the
        caller has refuted, excluded before the table ranks anything.
        """
        move = self.qvalues.select_action(state, rng, forbid)
        intent = self.intent_for_move(move)
        truncated = self.truncate_intent(intent, self.settings.hint_max_words)
        return move, truncated

    def observe_opponent(self, opponent_role, intent, move, cell):
        """Record belief and deposit cell into pheromone field exactly once."""
        self.belief.record(opponent_role, intent, move)
        deposits = [cell] if cell is not None else []
        self.pheromones.advance(deposits=deposits)

    def learn(self, state, action, reward, next_state, terminal):
        """Perform exactly one qvalues.update per transition."""
        self.qvalues.update(state, action, reward, next_state, terminal=terminal)
