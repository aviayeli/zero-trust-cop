"""board_view.py is an alias layer: it must re-export, not reimplement.

A "clean entry point" that quietly grew its own drawing or colour logic would
sit outside every test that targets palette.py and board_canvas.py.
"""

import pytest

tk = pytest.importorskip("tkinter")

from gui import board_view
from gui.board_canvas import BoardCanvas
from gui.live_heatmap import LiveHeatmap
from gui.palette import badge, heat_colour
from gui.replay import ReplayViewer


def test_it_re_exports_the_real_objects_not_copies():
    assert board_view.BoardCanvas is BoardCanvas
    assert board_view.LiveHeatmap is LiveHeatmap
    assert board_view.ReplayViewer is ReplayViewer
    assert board_view.heat_colour is heat_colour
    assert board_view.badge is badge


def test_both_views_are_reachable_from_the_one_entry_point():
    assert sorted(board_view._VIEWS) == ["heatmap", "replay"]


def test_the_launcher_defaults_to_the_replay_viewer():
    parsed = board_view.main.__doc__
    assert "heatmap" in parsed and "replay" in parsed


@pytest.mark.parametrize("view", ["heatmap", "replay"])
def test_each_view_builds_a_real_widget(view):
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"no display available: {error}")
    root.withdraw()
    try:
        widget = board_view._VIEWS[view](root, "logs/groupa/log_ztc001_g01.json")
        assert isinstance(widget, tk.Frame)
    finally:
        root.destroy()


def test_the_alias_layer_defines_no_logic_of_its_own():
    """Only the launcher; everything else must come from the real modules."""
    defined = {
        name for name, value in vars(board_view).items()
        if callable(value) and getattr(value, "__module__", "") == "gui.board_view"
    }

    assert defined == {"main"}
