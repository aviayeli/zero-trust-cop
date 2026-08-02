"""The Tk windows themselves, skipped where no display exists.

The colour RULES are covered headlessly in test_gui_palette.py; these check
the wiring — that the badge reflects the real verdict, and that the heatmap
actually repaints as belief changes.
"""

import json
from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter")

from gui.palette import TAMPERED_COLOUR, TAMPERED_TEXT, VERIFIED_COLOUR, VERIFIED_TEXT
from gui.live_heatmap import build as build_heatmap
from gui.replay import build as build_replay

LOG = "logs/groupa/log_ztc001_g01.json"


@pytest.fixture
def root():
    try:
        window = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"no display available: {error}")
    window.withdraw()
    yield window
    window.destroy()


@pytest.fixture
def forged(tmp_path):
    """A log whose recorded middle is falsified but whose moves are genuine."""
    log = json.loads(Path(LOG).read_text())
    for turn in log["turns"][:-1]:
        turn["result"]["cop_position"] = [6, 6]
    path = tmp_path / "forged.json"
    path.write_text(json.dumps(log))
    return str(path)


def test_a_clean_log_is_stamped_green(root):
    viewer = build_replay(root, LOG)

    assert viewer.badge.cget("text") == VERIFIED_TEXT
    assert viewer.badge.cget("bg") == VERIFIED_COLOUR


def test_a_forged_log_is_bannered_red(root, forged):
    """The badge must follow the verifier, not the file's own claims."""
    viewer = build_replay(root, forged)

    assert viewer.badge.cget("text") == TAMPERED_TEXT
    assert viewer.badge.cget("bg") == TAMPERED_COLOUR


def test_the_viewer_steps_through_every_turn(root):
    viewer = build_replay(root, LOG)
    first = viewer.caption.cget("text")

    viewer.next()

    assert viewer.caption.cget("text") != first
    assert viewer.index == 1


def test_stepping_never_runs_off_either_end(root):
    viewer = build_replay(root, LOG)

    for _ in range(len(viewer.frames) + 5):
        viewer.next()
    assert viewer.index == len(viewer.frames) - 1

    for _ in range(len(viewer.frames) + 5):
        viewer.previous()
    assert viewer.index == 0


def test_the_heatmap_paints_a_cell_for_every_square(root):
    view = build_heatmap(root, LOG)
    config_cells = view.canvas._grid_size ** 2

    rectangles = [i for i in view.canvas.find_all()
                  if view.canvas.type(i) == "rectangle"]

    assert len(rectangles) == config_cells


def test_the_heatmap_advances_and_then_stops(root):
    view = build_heatmap(root, LOG)

    assert view.advance() is True
    while view.advance():
        pass

    assert view.index == len(view.frames) - 1
    assert view.advance() is False
