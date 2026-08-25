"""The graded series must REPORT itself (PRD_11 FR1-FR3).

`report_by_email` has existed since Phase 6 and had exactly two callers,
neither of them the league entry point: `run_local_mcp_match` and
`run_remote_mcp_match`. So the one run that is actually graded was the one run
that emailed nothing, and "it did not send" looked identical at the console to
"it sent".

Three properties are pinned here, and only the first is about delivery:
reporting HAPPENS, reporting cannot FAIL the series it reports on, and the
mode is overridable without editing the shipped config.
"""

import pytest

from scripts import reference_cli

SUMMARY = {"sub_game": 1, "role": "police", "steps": 4,
           "terminal_reason": "capture", "their_audit_response":
           {"status": "accepted"}, "handshake_counter_signed": True}

ARGV = ["--seed", "1", "--opponent-url", "https://x/mcp"]


@pytest.fixture
def played(monkeypatch):
    """Stand in for a completed series and capture what the tail does."""
    calls = []

    async def fake_run(args):
        return [dict(SUMMARY)]

    monkeypatch.setattr("scripts.reference_run.run", fake_run)
    monkeypatch.setattr(
        reference_cli, "write_series_artifacts",
        lambda *a, **k: {"result": "logs/aviayeli/result_a-vs-b.json"},
    )
    monkeypatch.setattr(
        reference_cli, "report_by_email",
        lambda *a, **k: calls.append((a, k)),
    )
    return calls


# --- the flag --------------------------------------------------------------


def test_the_email_mode_defaults_to_the_shipped_config():
    """Absent an override, `load_email_settings` still decides — so the
    shipped `mode = "auto"` keeps governing CI and local simulation."""
    assert reference_cli.parse_args(ARGV).email_mode is None


def test_the_graded_run_can_demand_a_real_send():
    args = reference_cli.parse_args(ARGV + ["--email-mode", "send"])

    assert args.email_mode == "send"


def test_an_unknown_mode_is_refused_at_the_command_line():
    with pytest.raises(SystemExit):
        reference_cli.parse_args(ARGV + ["--email-mode", "maybe"])


# --- the tail --------------------------------------------------------------


def test_a_completed_series_reports_its_result(played):
    reference_cli.main(ARGV)

    assert len(played) == 1
    assert played[0][0][0] == "logs/aviayeli/result_a-vs-b.json"


def test_the_chosen_mode_reaches_the_reporter(played):
    reference_cli.main(ARGV + ["--email-mode", "send"])

    assert played[0][1]["mode"] == "send"


def test_a_rehearsal_that_wrote_nothing_reports_nothing(played):
    """`--no-artifacts` leaves no result file; reporting a path that does not
    exist would print a failure for a run that did nothing wrong."""
    reference_cli.main(ARGV + ["--no-artifacts"])

    assert played == []


def test_a_reporting_failure_cannot_discard_the_series(played, monkeypatch,
                                                       capsys):
    """Six played sub-games and a dead OAuth token is a mail problem, not a
    match problem. The artifacts are already on disk."""
    def explode(*a, **k):
        raise RuntimeError("invalid_grant")

    monkeypatch.setattr(reference_cli, "report_by_email", explode)

    summaries = reference_cli.main(ARGV)

    assert [s["sub_game"] for s in summaries] == [1]
    assert "email_report=FAILED" in capsys.readouterr().out


# --- the inter-sub-game window (PRD_14) ------------------------------------


def test_the_sub_game_pause_defaults_to_none_at_all():
    """Zero is today's behaviour, so an existing invocation is untouched."""
    assert reference_cli.parse_args(ARGV).sub_game_pause == 0


def test_a_relaunching_opponent_can_be_given_a_window():
    args = reference_cli.parse_args(ARGV + ["--sub-game-pause", "60"])

    assert args.sub_game_pause == 60
