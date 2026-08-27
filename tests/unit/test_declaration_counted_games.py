"""The greeting must carry `counted_games_played` (SMNGRP05 precondition).

Their reader is `opponent.get("counted_games_played", 0) or 0`, so a greeting
WITHOUT the field is recorded as 0 -- not as absent. Our declaration carried
four keys and none of them was this one, so today they would file 0 for us
while we filed 3.

That is not hypothetical: it is exactly how their counted series against
bb-ai-12 went wrong. bb-ai-12 sent nothing, the absence defaulted to 0, their
`+1` made it 1, and the two sides filed 1 and 2 for one match.

CONVENTION, settled in writing after they corrected their own two sentences
against report/artifacts.py:126 -- the +1 is applied to BOTH groups, so the
greeting field means the count BEFORE this series:

    our greeting      counted_games_played        = 2
    they file for us  games_played_including_this = 3

Two counted series played: aviayeli-vs-bb-ai-12 and ZeroOne0-vs-aviayeli.
The SMNGRP05 friendly is not counted and is not in it.
"""

import json
from pathlib import Path

from mcp_server.declaration import build_declaration

COUNTED = 2


def test_the_declaration_carries_counted_games_played():
    assert build_declaration()["counted_games_played"] == COUNTED


def test_the_value_lives_in_config_not_in_source():
    """The constitution forbids inlined tunables. A count that will change
    after the next graded series must not be a literal in a .py file."""
    declared = json.loads(Path("config/declaration.json").read_text())

    assert declared["counted_games_played"] == COUNTED


def test_the_field_is_an_integer_not_a_string():
    """Their reader does int() on it; a string would arrive as something
    else on their side."""
    assert isinstance(build_declaration()["counted_games_played"], int)


def test_it_counts_series_played_not_including_the_next_one():
    """The greeting is the BEFORE count. Sending 3 here would make them file
    4 for us -- the same off-by-one, one step later."""
    played = ["aviayeli-vs-bb-ai-12", "ZeroOne0-vs-aviayeli"]

    assert build_declaration()["counted_games_played"] == len(played)


# --- the WIRE, which is what the opponent actually records -------------------

def test_the_greeting_carries_counted_games_played():
    """SMNGRP05 verify this from the wire, not from the attachment: "what
    your greeting actually carries is what our reporter records".

    build_declaration carrying the field is NOT enough. `identity_block`
    cherry-picks a subset for `negotiate`, and the field was not in it -- so
    the artifact would have said 2 while the handshake said nothing, their
    reader would have defaulted it to 0, and the two sides would have filed
    0 and 3 for one counted match. That is the bb-ai-12 failure exactly.
    """
    from mcp_server.reference_surface import identity_block

    assert identity_block("police")["counted_games_played"] == COUNTED
    assert identity_block("thief")["counted_games_played"] == COUNTED


def test_the_wire_and_the_artifact_agree():
    """A config left at one value while the greeting carries another is the
    split SMNGRP05 warned produces two reports that disagree."""
    from mcp_server.reference_surface import identity_block

    assert (identity_block("police")["counted_games_played"]
            == build_declaration()["counted_games_played"])
