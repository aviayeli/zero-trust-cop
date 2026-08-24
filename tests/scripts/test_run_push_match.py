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
        parse_args(["--role", "police", "--seed", "1"])


def test_the_cli_defaults_to_a_single_sub_game():
    from scripts.run_push_match import parse_args

    args = parse_args(["--role", "police", "--seed", "1",
                       "--opponent-url", "https://x/mcp"])

    assert args.sub_games == 1 and args.opponent_url == "https://x/mcp"
