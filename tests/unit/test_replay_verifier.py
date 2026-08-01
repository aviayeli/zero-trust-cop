"""Audit remediation Pass 1: V1–V4 hardening of the replay verifier.

The audit found the verifier compared only the FINAL replayed state, so a
wholly fabricated per-turn trajectory certified clean; that turn indices and
turn counts were unchecked; and that three malformed inputs crashed with a
traceback instead of returning a verdict. A verifier that cannot answer is as
useless as one that answers wrongly.
"""

import copy
import json
from pathlib import Path

import pytest

from engine.config import load_config
from mcp_server.peer_keys import load_public_keys
from scripts.replay_match import TAMPERED, VERIFIED, main, verify_log

REAL_LOG = Path("logs/groupa/log_ztc001_g01.json")


@pytest.fixture
def genuine():
    return json.loads(REAL_LOG.read_text())


@pytest.fixture
def check(genuine):
    """Verify any log against the real config and keys."""
    config = load_config("config/game.json")
    keys = load_public_keys("police")
    return lambda log: verify_log(log, config, keys)


def _forged(genuine, mutate):
    log = copy.deepcopy(genuine)
    mutate(log)
    return log


def test_a_genuine_log_still_verifies(genuine, check):
    """Regression: hardening must not reject honest artifacts."""
    assert str(check(genuine)) == VERIFIED


# --- V1: intermediate results ------------------------------------------------

def test_a_single_falsified_intermediate_position_is_rejected(genuine, check):
    log = _forged(genuine, lambda l: l["turns"][1]["result"].__setitem__(
        "thief_position", [6, 6]))

    report = check(log)

    assert str(report) == TAMPERED
    assert any("turn 1" in failure for failure in report.failures)


def test_a_wholly_fabricated_trajectory_is_rejected(genuine, check):
    """The audit's headline attack: false middle, correct start and finish."""

    def fabricate(log):
        for index, turn in enumerate(log["turns"][:-1]):
            turn["result"]["cop_position"] = [6, 6 - index]
            turn["result"]["thief_position"] = [6, index]

    assert str(check(_forged(genuine, fabricate))) == TAMPERED


def test_a_falsified_intermediate_capture_flag_is_rejected(genuine, check):
    log = _forged(genuine, lambda l: l["turns"][0]["result"].__setitem__(
        "captured", True))

    assert str(check(log)) == TAMPERED


# --- V2: turn ordering -------------------------------------------------------

def test_swapped_turn_entries_are_rejected(genuine, check):
    def swap(log):
        log["turns"][0], log["turns"][1] = log["turns"][1], log["turns"][0]

    report = check(_forged(genuine, swap))

    assert str(report) == TAMPERED
    assert any("index" in failure for failure in report.failures)


def test_a_renumbered_turn_index_is_rejected(genuine, check):
    log = _forged(genuine, lambda l: l["turns"][2].__setitem__("turn", 99))

    assert str(check(log)) == TAMPERED


# --- V3: turn count ----------------------------------------------------------

def test_a_turn_appended_after_termination_is_rejected(genuine, check):
    def pad(log):
        log["turns"].append(copy.deepcopy(log["turns"][-1]))

    report = check(_forged(genuine, pad))

    assert str(report) == TAMPERED
    assert any("count" in failure for failure in report.failures)


# --- V4: malformed input yields a VERDICT, never a traceback -----------------

@pytest.mark.parametrize(
    "name, mutate",
    [
        ("empty turns", lambda l: l.__setitem__("turns", [])),
        ("no turns key", lambda l: l.pop("turns")),
        ("turns not a list", lambda l: l.__setitem__("turns", "nope")),
        ("missing role", lambda l: l["turns"][0]["submissions"].pop("thief")),
        ("non-ascii digest", lambda l: l["turns"][0]["submissions"]["police"]
            .__setitem__("h_commit", "ü" * 64)),
        ("result missing", lambda l: l["turns"][1].pop("result")),
    ],
)
def test_malformed_logs_report_tampered_without_crashing(
    genuine, check, name, mutate
):
    report = check(_forged(genuine, mutate))

    assert str(report) == TAMPERED, name
    assert report.failures, f"{name}: a rejection must say why"


def test_the_cli_exits_non_zero_on_a_fabricated_trajectory(genuine, tmp_path, capsys):
    def fabricate(log):
        for turn in log["turns"][:-1]:
            turn["result"]["cop_position"] = [5, 5]

    path = tmp_path / "forged.json"
    path.write_text(json.dumps(_forged(genuine, fabricate)))

    with pytest.raises(SystemExit) as exited:
        main([str(path)])

    assert exited.value.code == 1
    assert TAMPERED in capsys.readouterr().out
