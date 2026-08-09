"""The --render flag is additive: verification behaviour must not change.

Without the flag the tool stays a fast cryptographic check that prints
"Verified OK" and exits 0 — no board, no pause.
"""

import pytest

from scripts.replay_match import main, parse_args

LOG = "logs/aviayeli/log_aviayeli_g01.json"


def test_render_is_off_by_default():
    assert parse_args([LOG]).render is False


def test_the_flag_turns_rendering_on():
    assert parse_args([LOG, "--render"]).render is True


def test_the_delay_is_configurable():
    assert parse_args([LOG, "--render-delay", "0.1"]).render_delay == 0.1


def test_step_mode_is_available_and_off_by_default():
    assert parse_args([LOG]).step is False
    assert parse_args([LOG, "--render", "--step"]).step is True


def test_without_render_the_output_is_only_the_verdict(capsys):
    with pytest.raises(SystemExit) as exited:
        main([LOG])

    assert exited.value.code == 0
    assert capsys.readouterr().out.strip() == "Verified OK"


def test_with_render_the_board_is_drawn_before_the_verdict(capsys):
    with pytest.raises(SystemExit) as exited:
        main([LOG, "--render", "--render-delay", "0"])

    output = capsys.readouterr().out
    assert exited.value.code == 0
    assert "Turn 1" in output
    assert "legend:" in output
    assert output.strip().endswith("Verified OK")


def test_rendering_a_tampered_log_still_exits_non_zero(capsys, tmp_path):
    import json
    log = json.loads(open(LOG).read())
    log["turns"][0]["submissions"]["police"]["intent"] = "elsewhere"
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(log))

    with pytest.raises(SystemExit) as exited:
        main([str(path), "--render", "--render-delay", "0"])

    output = capsys.readouterr().out
    assert exited.value.code == 1
    assert "commit=!!" in output
    assert "TAMPERED!" in output
