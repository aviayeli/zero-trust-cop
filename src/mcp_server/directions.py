"""Wire encoding for moves and honesty (payload semantics v3.0.0).

The wire states a DIRECTION and an HONESTY flag separately:

    move   = 'north' | 'south' | 'east' | 'west' | 'stay'
    intent = 'truth' | 'lie'

The engine speaks ``N/S/E/W/STAY`` and must never learn that a wire encoding
exists, so the translation lives here, above it. ``src/engine/`` is guarded by
an AST import test precisely to keep that boundary.

The verbal hint an opponent would have heard is derivable rather than
transmitted: it is the move itself when truthful, and its opposite when not.
That keeps the belief tracker scoring the same evidence it always did, while
the payload itself now says plainly whether the peer lied.
"""

TRUTH = "truth"
LIE = "lie"
_INTENTS = (TRUTH, LIE)

_WORDS = {"N": "north", "S": "south", "E": "east", "W": "west", "STAY": "stay"}
_TOKENS = {word: token for token, word in _WORDS.items()}
_OPPOSITE = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "stay": "stay",
}


def to_word(token: str) -> str:
    """Engine token -> wire direction word."""
    try:
        return _WORDS[token]
    except KeyError:
        raise ValueError(f"unknown move token: {token!r}") from None


def to_token(word: str) -> str:
    """Wire direction word -> engine token."""
    try:
        return _TOKENS[word]
    except KeyError:
        raise ValueError(f"unknown direction word: {word!r}") from None


def is_intent(value) -> bool:
    """Whether a value is one of the two permitted honesty flags."""
    return value in _INTENTS


def opposite(word: str) -> str:
    """The inverse direction. ``stay`` is its own opposite (D4)."""
    try:
        return _OPPOSITE[word]
    except KeyError:
        raise ValueError(f"unknown direction word: {word!r}") from None


def stated_hint(move_word: str, intent: str) -> str:
    """The hint the peer claimed: the move when truthful, else its opposite."""
    if not is_intent(intent):
        raise ValueError(f"intent must be one of {_INTENTS}: {intent!r}")
    return move_word if intent == TRUTH else opposite(move_word)
