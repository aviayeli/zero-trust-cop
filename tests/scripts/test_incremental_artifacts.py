"""A finished sub-game must survive the one that follows it (PRD_10 10.24).

Artifacts were written once, after the WHOLE series. So a series that played
sub-game 1 to a clean close and then lost the opponent in sub-game 2 wrote
nothing at all — thirty-five verified steps and a mutual audit, deleted by a
502 that arrived afterwards. That happened live against rstabcde, whose cop
endpoint has now dropped at a sub-game boundary three times.

Under a deadline it is the difference between five attempts producing nothing
and five attempts producing five logs. A sub-game that completed is evidence;
what happens next cannot un-play it.
"""

import json
from pathlib import Path

from scripts.reference_writer import write_series_artifacts


def _summary(n, role="police", steps=2):
    return {"sub_game": n, "role": role, "steps": steps,
            "terminal_reason": "survival", "handshake_counter_signed": False,
            "result_claim": {"outcome": "survival", "steps": steps},
            "their_audit_response": {"accepted": True},
            "our_chain": [{"payload": {"step": s}, "nonce": "n", "commit": "c"}
                          for s in range(1, steps + 1)],
            "their_turns": []}


def test_a_sub_game_log_can_be_written_on_its_own(tmp_path):
    from scripts.reference_writer import write_sub_game_log

    path = write_sub_game_log(tmp_path, _summary(1), group_id="aviayeli",
                              opponent_id="rstabcde")

    assert Path(path).exists()
    assert json.loads(Path(path).read_text())["game_number"] == 1


def test_each_sub_game_gets_its_own_file(tmp_path):
    from scripts.reference_writer import write_sub_game_log

    for n in (1, 2, 3):
        write_sub_game_log(tmp_path, _summary(n), "aviayeli",
                           opponent_id="rstabcde")

    written = sorted(p.name for p in (tmp_path / "aviayeli").glob("log_*.json"))
    assert len(written) == 3


def test_the_series_writer_still_produces_all_four(tmp_path):
    """Writing incrementally must not stop the closing set being written."""
    paths = write_series_artifacts(tmp_path, [_summary(1), _summary(2)],
                                   group_id="aviayeli", opponent_id="rstabcde")

    assert sorted(paths) == ["config", "declaration", "log", "result"]


def test_rewriting_a_sub_game_log_is_idempotent(tmp_path):
    """The series writer rewrites the logs the incremental pass already
    wrote; identical bytes, so a partial run and a full one agree."""
    from scripts.reference_writer import write_sub_game_log

    first = Path(write_sub_game_log(tmp_path, _summary(1), "aviayeli",
                                    opponent_id="rstabcde"))
    before = first.read_text()
    write_series_artifacts(tmp_path, [_summary(1)], group_id="aviayeli",
                           opponent_id="rstabcde")

    assert first.read_text() == before


def test_the_runner_can_actually_call_the_incremental_writer():
    """The bug this file exists to prevent, in the one place it hid.

    `write_sub_game_log` was added, tested directly, and wired into the
    runner — but the import landed in a sibling module. A live sub-game ran
    all 35 steps, exchanged audits, and then died on `NameError` while
    writing, losing exactly what the incremental write was added to save.

    Every test here called the writer directly, so nothing touched the path
    the runner actually uses.

    The wiring moved when `run_reference_match` was split at the 150-line
    limit: that module is now the docstring and the re-exported entry points,
    and `scripts.reference_run` is the loop. So this asserts against the
    module that actually calls the writer, not the shim in front of it.
    """
    import scripts.reference_run as runner
    from scripts.reference_writer import write_sub_game_log

    assert runner.write_sub_game_log is write_sub_game_log
    assert callable(runner.group_id)
