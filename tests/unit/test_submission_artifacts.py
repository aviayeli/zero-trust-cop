"""Course-alignment gaps: provenance in the summary, and a coloured verdict.

The Step-0 commit hash was already in declaration_<game_id>.json but absent
from result_<game_id>.json, so the final summary could not be tied to the
code that produced it. And the verifier printed an uncoloured verdict.

Colour must be conditional: piped or captured output has to stay byte-clean,
or every existing assertion on stdout breaks and logs fill with escapes.
"""

import json
import re
from pathlib import Path

import pytest

from mcp_server.declaration import github_commit
from scripts.match_log import build_result, write_artifacts
from scripts.replay_match import TAMPERED, VERIFIED, colourise


@pytest.fixture
def history():
    return [{
        "turn": 0,
        "submissions": [],
        "result": {"cop_position": (0, 1), "thief_position": (3, 3),
                   "captured": False, "turn_count": 1, "is_terminated": True,
                   "terminal_reason": "capture"},
    }]


def test_the_probe_returns_a_git_sha():
    assert re.fullmatch(r"[0-9a-f]{40}|unknown", github_commit())


def test_the_result_summary_carries_the_commit_hash(history):
    result = build_result("g1", 1, history, group_id="aviayeli")

    assert result["github_commit"] == github_commit()


def test_the_written_result_artifact_carries_it_too(tmp_path, history):
    paths = write_artifacts(tmp_path, "g1", 1, history,
                            group_id="aviayeli", config_root="config")

    written = json.loads(Path(paths["result"]).read_text())
    assert written["github_commit"] == github_commit()


def test_the_declaration_and_the_result_agree_on_provenance(tmp_path, history):
    """Both artifacts must name the SAME commit, or the pair is incoherent."""
    paths = write_artifacts(tmp_path, "g1", 1, history,
                            group_id="aviayeli", config_root="config")

    declaration = json.loads(Path(paths["declaration"]).read_text())
    result = json.loads(Path(paths["result"]).read_text())

    assert result["github_commit"] == declaration["github_commit_hash"]


# --- coloured verdict --------------------------------------------------------

def test_a_pass_is_green_when_colour_is_enabled():
    painted = colourise(VERIFIED, ok=True, enabled=True)

    assert painted.startswith("\033[32m") and painted.endswith("\033[0m")
    assert VERIFIED in painted


def test_a_failure_is_red_when_colour_is_enabled():
    painted = colourise(TAMPERED, ok=False, enabled=True)

    assert painted.startswith("\033[31m") and painted.endswith("\033[0m")


@pytest.mark.parametrize("verdict, ok", [(VERIFIED, True), (TAMPERED, False)])
def test_output_stays_byte_clean_when_colour_is_disabled(verdict, ok):
    """Piped and captured output must carry no escape sequences at all."""
    assert colourise(verdict, ok=ok, enabled=False) == verdict


def test_capsys_captured_output_is_never_coloured(capsys):
    """Regression: existing tests assert stdout == 'Verified OK' exactly."""
    from scripts.replay_match import main

    with pytest.raises(SystemExit) as exited:
        main(["logs/aviayeli/log_aviayeli_g01.json"])

    assert exited.value.code == 0
    assert capsys.readouterr().out.strip() == VERIFIED
