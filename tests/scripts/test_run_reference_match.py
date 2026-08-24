"""The live reference-v3 CLI's argument contract (PRD_10 10.6).

This is the entry point that replaces `run_push_match` against ali-ahm1: the
push dialect's `receive_commit` is served by their peer and read by nothing
in their game loop, so a series driven through it pushes into a void that
answers 200.

Both of our peers are served for the whole series because the sides swap
every sub-game, which is why there is no `--role`: it would describe the
first sub-game and silently mislead about the other five.
"""

import pytest

from scripts.run_reference_match import parse_args


def test_the_cli_requires_an_opponent_url():
    with pytest.raises(SystemExit):
        parse_args(["--seed", "1"])


def test_the_cli_plays_the_whole_series_by_default():
    args = parse_args(["--seed", "1", "--opponent-url", "https://x/mcp"])

    assert args.sub_games == 6
    assert args.first_role == "police"
    assert args.opponent_url == "https://x/mcp"


def test_the_starting_side_is_selectable():
    args = parse_args(["--seed", "1", "--opponent-url", "https://x/mcp",
                       "--first-role", "thief"])

    assert args.first_role == "thief"


def test_there_is_no_single_role_flag():
    with pytest.raises(SystemExit):
        parse_args(["--seed", "1", "--opponent-url", "https://x/mcp",
                    "--role", "police"])


def test_the_seed_is_required():
    """A series with no seed is unreplayable, and the log is the deliverable."""
    with pytest.raises(SystemExit):
        parse_args(["--opponent-url", "https://x/mcp"])


def test_this_entry_point_drives_the_claims_runner_not_the_push_one():
    """The whole point of the module. Asserted on the import, because a
    correct CLI in front of the wrong loop is exactly the bug being fixed."""
    import scripts.reference_run as module

    from scripts.claims_runner import play_series

    assert module.play_series is play_series


# --- the wait window -------------------------------------------------------


def test_the_wait_window_defaults_to_todays_behaviour():
    """5 minutes at the configured 0.5s poll interval is 600 polls — exactly
    the old hardcoded budget. The default must not change what a run does."""
    from scripts.claims_guards import DEFAULT_MAX_POLLS
    from scripts.reference_launch import polls_for

    args = parse_args(["--seed", "1", "--opponent-url", "https://x/mcp"])

    assert args.wait_minutes == 5
    assert polls_for(args.wait_minutes, 0.5) == DEFAULT_MAX_POLLS


def test_a_longer_window_is_selectable():
    """The reason this flag exists: our peers only live while a run does, so
    a 5-minute budget forces both sides onto the same minute. Three attempts
    on 2026-08-24 were lost to that and none to the protocol."""
    from scripts.reference_launch import polls_for

    args = parse_args(["--seed", "1", "--opponent-url", "https://x/mcp",
                       "--wait-minutes", "30"])

    assert args.wait_minutes == 30
    assert polls_for(30, 0.5) == 3600


def test_the_window_is_derived_from_the_configured_interval_not_a_literal():
    """A peer polling every 2s must not get a quarter of the window it asked
    for. The interval is a tunable and lives in the peer's [network] block."""
    from scripts.reference_launch import polls_for

    assert polls_for(10, 2.0) == 300
    assert polls_for(10, 0.25) == 2400


def test_a_window_is_never_rounded_down_to_zero_polls():
    """A sub-minute interval must still poll at least once, or the loop
    reports a stall it never waited for."""
    from scripts.reference_launch import polls_for

    assert polls_for(0, 0.5) >= 1


def test_a_two_process_opponent_is_addressable():
    """rstabcde run cop and thief as separate tunnels, and the sides swap
    every sub-game, so one URL cannot express where a turn goes."""
    args = parse_args(["--seed", "1", "--opponent-cop-url", "https://c/mcp",
                       "--opponent-thief-url", "https://t/mcp"])

    assert args.opponent_cop_url == "https://c/mcp"
    assert args.opponent_thief_url == "https://t/mcp"
    assert args.opponent_url is None


def test_the_single_endpoint_form_still_works():
    """ali-ahm1 served both roles on one endpoint; that must keep working."""
    args = parse_args(["--seed", "1", "--opponent-url", "https://x/mcp"])

    assert args.opponent_url == "https://x/mcp"


def test_naming_no_endpoint_at_all_is_refused():
    with pytest.raises(SystemExit):
        parse_args(["--seed", "1"])
