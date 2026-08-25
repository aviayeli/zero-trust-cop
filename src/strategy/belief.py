"""Track whether a peer's stated movement intent matched its action.

Each observation is ``honest``, ``dishonest``, or ``unscorable``.  An
unscorable intent names no direction and is absent evidence, not negative
evidence, so it never changes the honesty rate.  Full direction words match
at a word-boundary prefix (thus ``northern`` names north), while one-letter
forms must stand alone; this prevents incidental text such as ``SNOW`` or
``NEWS`` from naming directions.  Intent length is irrelevant here.  This is
not lie detection: it measures stated intent versus action only, so a peer
with an honest intent and good strategy remains honest.
"""

import re
from collections import defaultdict

from engine.config import GameConfig
from strategy.settings import StrategySettings

_DIRECTION_WORDS = {
    "north": "N",
    "south": "S",
    "east": "E",
    "west": "W",
    "stay": "STAY",
}
_SINGLE_LETTERS = {"N", "S", "E", "W"}
_VERDICTS = ("honest", "dishonest", "unscorable")


class BeliefTracker:
    """Maintain independent stated-intent evidence for each peer."""

    def __init__(self, config: GameConfig, settings: StrategySettings):
        self.config = config
        self.settings = settings
        self._counts = defaultdict(lambda: dict.fromkeys(_VERDICTS, 0))
        self._moves = {str(token).upper(): token for token in config.move_set}

    def record(self, peer: str, intent: str, move: str) -> str:
        """Record one revealed intent and action, returning its verdict."""
        named_moves = self._named_moves(intent)
        if not named_moves:
            verdict = "unscorable"
        elif str(move).upper() in named_moves:
            verdict = "honest"
        else:
            verdict = "dishonest"
        self._counts[peer][verdict] += 1
        return verdict

    def honesty_rate(self, peer: str) -> float:
        """Return a peer's scorable honesty fraction, or its configured prior."""
        counts = self._counts.get(peer)
        if counts is None:
            return self.settings.honesty_prior
        scorable = counts["honest"] + counts["dishonest"]
        if not scorable:
            return self.settings.honesty_prior
        return counts["honest"] / scorable

    def counts(self, peer: str) -> dict:
        """Return every verdict tally for a peer, including zero tallies."""
        counts = self._counts.get(peer)
        if counts is None:
            return dict.fromkeys(_VERDICTS, 0)
        return dict(counts)

    def _named_moves(self, intent: str) -> set[str]:
        upper_intent = intent.upper()
        named = {
            token
            for word, token in _DIRECTION_WORDS.items()
            if re.search(rf"\b{word}\w*", intent, re.IGNORECASE)
        }
        named.update(
            letter
            for letter in _SINGLE_LETTERS
            if re.search(rf"\b{letter}\b", upper_intent)
        )
        return {token for token in named if token.upper() in self._moves}
