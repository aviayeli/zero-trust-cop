"""The entry point's ARTIFACT wiring (PRD_10 10.19).

Split from `test_run_reference_match.py`, which covers the argument contract.
A graded series that leaves only stdout leaves nothing to grade, so writing is
the default and the flag turns it OFF.
"""

from scripts.reference_cli import parse_args


# --- artifacts -------------------------------------------------------------


def test_artifacts_are_written_by_default():
    """A graded series that leaves only stdout leaves nothing to grade."""
    args = parse_args(["--seed", "1", "--opponent-url", "https://x/mcp"])

    assert args.logs_dir == "logs"
    assert args.write_artifacts is True


def test_writing_can_be_turned_off_for_a_throwaway_run():
    args = parse_args(["--seed", "1", "--opponent-url", "https://x/mcp",
                       "--no-artifacts"])

    assert args.write_artifacts is False


def test_the_logs_directory_is_selectable():
    args = parse_args(["--seed", "1", "--opponent-url", "https://x/mcp",
                       "--logs-dir", "/tmp/elsewhere"])

    assert args.logs_dir == "/tmp/elsewhere"


def test_the_entry_point_uses_the_reference_writer_not_the_native_one():
    """The native writer records a per-turn signature and the opponent's
    revealed move. This wire carries neither, and a graded artifact must not
    claim fields no message ever held."""
    import scripts.reference_cli as module

    from scripts.reference_writer import write_series_artifacts

    assert module.write_series_artifacts is write_series_artifacts


def test_the_opposing_group_can_be_named():
    """`agreed_between` still names a placeholder from an earlier phase, so a
    run against a real opponent would derive `game_uid` from the wrong pair —
    artifacts that join OUR four files perfectly and fail the cross-team join
    silently, which is the exact failure PRD_08 exists to prevent."""
    args = parse_args(["--seed", "1", "--opponent-url", "https://x/mcp",
                       "--opponent-id", "ali-ahm1"])

    assert args.opponent_id == "ali-ahm1"


def test_the_opposing_group_defaults_to_the_contracted_pair():
    """Both peers ship the same contract, so a normal league match needs no
    extra argument and cannot disagree about who is playing."""
    args = parse_args(["--seed", "1", "--opponent-url", "https://x/mcp"])

    assert args.opponent_id is None
