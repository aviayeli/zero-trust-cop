"""The live push-match CLI's argument contract.

Split from `test_push_runner.py` at the 150-line limit. The runner glue is
there; this is the entry point that connects it to a real opponent — the
piece whose absence meant a successful handshake was followed by silence.
"""

import pytest


# --- the CLI ---------------------------------------------------------------


def test_the_cli_requires_an_opponent_url():
    """Without it there is nobody to push to, and the old failure mode was a
    successful handshake followed by silence."""
    from scripts.run_push_match import parse_args

    with pytest.raises(SystemExit):
        parse_args(["--seed", "1"])


def test_the_cli_plays_the_whole_series_by_default():
    """A league series is six sub-games. Defaulting to one would leave the
    operator alternating roles by hand in the middle of a live match."""
    from scripts.run_push_match import parse_args

    args = parse_args(["--seed", "1", "--opponent-url", "https://x/mcp"])

    assert args.sub_games == 6
    assert args.first_role == "police"
    assert args.opponent_url == "https://x/mcp"


def test_the_starting_side_is_selectable():
    from scripts.run_push_match import parse_args

    assert parse_args(["--seed", "1", "--opponent-url", "https://x/mcp",
                       "--first-role", "thief"]).first_role == "thief"


def test_there_is_no_single_role_flag_any_more():
    """--role would describe only the first sub-game and silently mislead
    about the other five."""
    from scripts.run_push_match import parse_args

    with pytest.raises(SystemExit):
        parse_args(["--seed", "1", "--opponent-url", "https://x/mcp",
                    "--role", "police"])
