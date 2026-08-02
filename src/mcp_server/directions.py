"""Wire vocabulary for moves and honesty (payload v3.0.0).

The wire states a MOVE and an HONESTY flag separately:

    move   = 'N' | 'S' | 'E' | 'W' | 'STAY'      (engine tokens, uppercase)
    intent = 'truth' | 'lie'

Move tokens are the engine's own vocabulary, so nothing is translated at the
boundary and a malformed token fails in exactly one place.

The verbal hint an opponent would have heard is derivable rather than
transmitted: the move itself when truthful, its opposite when not. The policy
states its claim as a word ("north"), so the word map below exists only to
compare that claim against the move actually played — it is not a wire form.
"""

TRUTH = "truth"
LIE = "lie"
_INTENTS = (TRUTH, LIE)

MOVES = ("N", "S", "E", "W", "STAY")
_OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E", "STAY": "STAY"}
_WORD_TO_TOKEN = {
    "north": "N", "south": "S", "east": "E", "west": "W", "stay": "STAY",
}


def is_move(token) -> bool:
    """Whether a value is one of the five permitted move tokens."""
    return token in MOVES


def is_intent(value) -> bool:
    """Whether a value is one of the two permitted honesty flags."""
    return value in _INTENTS


def token_for_claim(word: str) -> str:
    """The move token a policy's spoken claim refers to."""
    try:
        return _WORD_TO_TOKEN[word.strip().lower()]
    except KeyError:
        raise ValueError(f"unknown direction claim: {word!r}") from None


def opposite(token: str) -> str:
    """The inverse move. ``STAY`` is its own opposite (D4)."""
    try:
        return _OPPOSITE[token]
    except KeyError:
        raise ValueError(f"unknown move token: {token!r}") from None


def stated_hint(move: str, intent: str) -> str:
    """The move the peer claimed: its own when truthful, else the opposite."""
    if not is_intent(intent):
        raise ValueError(f"intent must be one of {_INTENTS}: {intent!r}")
    return move if intent == TRUTH else opposite(move)
