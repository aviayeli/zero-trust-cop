"""Wire vocabulary for moves and honesty (payload v3.0.0).

The wire states a MOVE and an HONESTY flag separately:

    move   = 'MOVE:N' | 'MOVE:S' | 'MOVE:E' | 'MOVE:W' | 'MOVE:STAY'
    intent = 'truth' | 'lie'

Internally the engine's single-token vocabulary is preserved: ``encode`` adds
the prefix on the way out and ``decode`` strips it on the way in, so exactly
one place knows the wire spelling. ``decode`` also accepts a bare token, so
logs written before the prefix existed still verify.

The verbal hint an opponent would have heard is derivable rather than
transmitted: the move itself when truthful, its opposite when not. The policy
states its claim as a word ("north"), so the word map below exists only to
compare that claim against the move actually played — it is not a wire form.
"""

TRUTH = "truth"
LIE = "lie"
_INTENTS = (TRUTH, LIE)

MOVES = ("N", "S", "E", "W", "STAY")
PREFIX = "MOVE:"
_OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E", "STAY": "STAY"}
_WORD_TO_TOKEN = {
    "north": "N", "south": "S", "east": "E", "west": "W", "stay": "STAY",
}


def is_move(token) -> bool:
    """Whether a value is one of the five permitted move tokens."""
    return token in MOVES


def encode(token: str) -> str:
    """Engine token -> canonical wire spelling."""
    if not is_move(token):
        raise ValueError(f"unknown move token: {token!r}")
    return f"{PREFIX}{token}"


def decode(wire) -> str:
    """Wire spelling -> engine token, tolerating a bare legacy token."""
    if isinstance(wire, str):
        token = wire[len(PREFIX):] if wire.startswith(PREFIX) else wire
        if is_move(token):
            return token
    raise ValueError(f"unknown wire move: {wire!r}")


def is_wire_move(wire) -> bool:
    """Whether a value decodes to a permitted move."""
    try:
        decode(wire)
    except ValueError:
        return False
    return True


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
