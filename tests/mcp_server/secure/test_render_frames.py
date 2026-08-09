"""Per-turn crypto status and the frames a replay produces.

Frames come from stepping a real episode, so they must land where the
committed log says — a renderer that drew the log's claimed positions
would show a forged match as a tidy one.
"""

import json
from pathlib import Path

import pytest

from engine.config import load_config
from mcp_server.peer_keys import load_public_keys
from scripts.render_replay import render_replay, replay_frames, turn_checks

REAL_LOG = Path("logs/aviayeli/log_aviayeli_g01.json")


@pytest.fixture
def config():
    return load_config("config/game.json")


@pytest.fixture
def real_log():
    return json.loads(REAL_LOG.read_text())


@pytest.fixture
def public_keys():
    return load_public_keys("police")


def test_turn_checks_pass_on_the_committed_artifact(real_log, public_keys):
    checks = turn_checks(real_log["turns"][0], public_keys)

    for role in ("police", "thief"):
        assert checks[role]["commitment"] is True
        assert checks[role]["signature"] is True


def test_turn_checks_catch_an_edited_intent(real_log, public_keys):
    turn = json.loads(json.dumps(real_log["turns"][0]))
    turn["submissions"]["police"]["intent"] = "elsewhere"

    checks = turn_checks(turn, public_keys)

    assert checks["police"]["commitment"] is False
    assert checks["police"]["signature"] is True


def test_turn_checks_catch_a_forged_signature(real_log, public_keys):
    turn = json.loads(json.dumps(real_log["turns"][0]))
    turn["submissions"]["thief"]["signature"] = "00" * 64

    checks = turn_checks(turn, public_keys)

    assert checks["thief"]["signature"] is False


def test_one_frame_is_produced_per_logged_turn(real_log, config, public_keys):
    frames = list(replay_frames(real_log, config, public_keys))

    assert len(frames) == len(real_log["turns"])


def test_the_frames_reconstruct_the_logged_final_state(real_log, config, public_keys):
    """Frames come from a real replay, so they must land where the log says."""
    final = list(replay_frames(real_log, config, public_keys))[-1]
    recorded = real_log["turns"][-1]["result"]

    assert list(final.cop) == recorded["cop_position"]
    assert list(final.thief) == recorded["thief_position"]
    assert final.captured is recorded["captured"]


def test_scent_accumulates_as_the_thief_moves(real_log, config, public_keys):
    frames = list(replay_frames(real_log, config, public_keys))

    assert frames[0].scent, "the thief's first position must leave a trace"
    assert any(value > 0 for value in frames[-1].scent.values())


def test_render_writes_a_board_and_pauses_once_per_turn(real_log, config, public_keys):
    written, pauses = [], []

    render_replay(
        real_log, config, public_keys,
        write=written.append, pause=pauses.append, delay=0.25,
    )

    assert len(pauses) == len(real_log["turns"])
    assert pauses == [0.25] * len(real_log["turns"])
    assert any("Turn 1" in line for line in written)


def test_render_shows_moves_and_verification_status(real_log, config, public_keys):
    written = []

    render_replay(real_log, config, public_keys, write=written.append, pause=lambda _: None)

    text = "\n".join(written)
    assert "commit=OK" in text
    assert "signature=OK" in text
    assert "move=" in text


def test_render_flags_a_tampered_turn_instead_of_drawing_it_clean(
    real_log, config, public_keys
):
    """The view must not launder a forgery into a tidy picture."""
    tampered = json.loads(json.dumps(real_log))
    tampered["turns"][0]["submissions"]["police"]["intent"] = "elsewhere"
    written = []

    render_replay(tampered, config, public_keys, write=written.append, pause=lambda _: None)

    assert "commit=!!" in "\n".join(written)


def test_frames_show_the_REPLAYED_position_not_the_logged_claim(
    real_log, config, public_keys
):
    """The view must not echo the log it is supposed to be checking.

    A renderer that read result positions straight from the file would draw a
    forged match exactly as its author intended. Here the recorded final
    position is falsified while the moves stay genuine, so the two sources
    disagree and only a real replay gets it right.
    """
    forged = json.loads(json.dumps(real_log))
    truthful = forged["turns"][-1]["result"]["thief_position"]
    forged["turns"][-1]["result"]["thief_position"] = [6, 6]

    final = list(replay_frames(forged, config, public_keys))[-1]

    assert list(final.thief) == truthful
    assert list(final.thief) != [6, 6]


def test_the_rendered_board_shows_the_replayed_position(real_log, config, public_keys):
    forged = json.loads(json.dumps(real_log))
    forged["turns"][-1]["result"]["cop_position"] = [6, 6]
    written = []

    render_replay(forged, config, public_keys, write=written.append, pause=lambda _: None)

    assert "cop=(6, 6)" not in "\n".join(written)
