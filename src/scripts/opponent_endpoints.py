"""Which of the opponent's endpoints receives this sub-game (PRD_10 10.21).

Two shapes exist in this league and both are conformant. ali-ahm1 serve both
roles on ONE endpoint and read the role out of the message; rstabcde run cop
and thief as two separate processes on two tunnels. A single
``--opponent-url`` covered the first and silently could not express the
second.

The mapping is the part to state plainly, because inverting it is not a
crash. We push to the endpoint serving the role THEY are playing, which is
the opposite of ours: in a sub-game where we are police, their THIEF endpoint
receives our turns. Push to the wrong one and a whole sub-game goes to a peer
playing the same side we are -- a pairing collision on their end, silence on
ours, and thirty-five steps before either side finds out.
"""

from __future__ import annotations

# Our wire role -> the role the OPPONENT is playing that sub-game.
_THEIR_ROLE = {"police": "thief", "thief": "police"}
# Their role -> the key its endpoint is stored under. The contract and the
# book say `cop`; our peers say `police`.
_ENDPOINT_KEY = {"police": "cop", "thief": "thief"}


def resolve_endpoints(single: str | None, cop: str | None,
                      thief: str | None) -> dict:
    """Normalise the two CLI shapes into one role -> URL map.

    Raises:
        ValueError: no endpoint, only half a split pair, or both forms at
            once. Half a mapping plays half a series into a void that answers
            200, and naming both forms gives two answers to one question with
            no way to tell which was meant.
    """
    split = (cop, thief)
    if single and any(split):
        raise ValueError(
            "name either one endpoint serving both their roles, or one per "
            "role -- not both"
        )
    if single:
        return {"cop": single, "thief": single}
    if all(split):
        return {"cop": cop, "thief": thief}
    if any(split):
        missing = "thief" if cop else "cop"
        raise ValueError(
            f"an opponent running two processes needs both endpoints; "
            f"{missing} is missing. The sides swap every sub-game, so half a "
            "mapping plays half the series into an inbox nobody polls."
        )
    raise ValueError("no opponent endpoint given")


def endpoint_for(endpoints: dict, our_role: str) -> str:
    """The URL that receives OUR turns while we play ``our_role``.

    Raises:
        ValueError: a role this wire does not have. Defaulting would push a
            whole sub-game at the wrong peer.
    """
    try:
        theirs = _THEIR_ROLE[our_role]
    except KeyError:
        raise ValueError(
            f"role must be one of {sorted(_THEIR_ROLE)}, got {our_role!r}"
        ) from None
    return endpoints[_ENDPOINT_KEY[theirs]]


def endpoints_needed(endpoints: dict, sub_games: int, first_role: str) -> list:
    """The distinct URLs this schedule will actually address.

    Opening every endpoint the opponent serves killed runs that needed only
    one: a single sub-game as police never addresses their cop, and their cop
    being down took the whole run with it. The schedule is a pure function of
    the series length and the side we start, so what we must reach is known
    before we dial anything.
    """
    from scripts.push_runner import role_schedule

    seen = []
    for role in role_schedule(sub_games, first_role):
        url = endpoint_for(endpoints, role)
        if url not in seen:
            seen.append(url)
    return seen
