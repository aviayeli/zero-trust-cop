"""A spawned peer must be able to import the package, and say so when it cannot.

`uv run pytest` failed four live-transport tests with
`TimeoutError: no peer listening on 127.0.0.1:8802`. The peers were not slow —
they were dead on arrival with `ModuleNotFoundError: No module named
'mcp_server'`, and three defects hid that:

* `pyproject.toml` declares no `[build-system]`, so this project is never
  installed into the venv. `mcp_server` is importable only because pytest's
  `pythonpath = ["src"]` patches the PARENT's `sys.path`.
* `_spawn` passed no environment, so the child inherited none of it.
* `_spawn` piped the child's stderr and never read it, so the real error was
  discarded and the symptom appeared 30 seconds later as a timeout.

The fix makes the child's import path explicit rather than inherited from an
install state nothing declares.
"""

import subprocess
import sys

import pytest

from scripts.peer_processes import SRC_ROOT, child_environment, wait_for_port


def test_the_child_environment_puts_src_on_the_python_path():
    """The child cannot rely on pytest's sys.path patching; it is a new process."""
    env = child_environment()

    assert str(SRC_ROOT) in env["PYTHONPATH"].split(":")


def test_the_child_environment_preserves_the_parent_environment():
    """Replacing os.environ wholesale would drop PATH, HOME and the venv."""
    env = child_environment()

    assert env.get("PATH"), "the child lost PATH"


def test_an_existing_python_path_is_extended_not_replaced(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/somewhere/else")

    entries = child_environment()["PYTHONPATH"].split(":")

    assert str(SRC_ROOT) in entries
    assert "/somewhere/else" in entries


def test_a_spawned_peer_can_actually_import_the_package():
    """The regression itself, reproduced without starting a server."""
    done = subprocess.run(
        [sys.executable, "-c", "import mcp_server, engine, strategy; print('ok')"],
        capture_output=True, text=True, env=child_environment(), timeout=60,
    )

    assert done.returncode == 0, done.stderr
    assert "ok" in done.stdout


def test_a_peer_that_dies_reports_its_error_instead_of_timing_out():
    """A dead child must not be reported as a slow one, 30 seconds later."""
    dead = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stderr.write('boom\\n'); sys.exit(3)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )

    with pytest.raises(RuntimeError, match="boom"):
        wait_for_port("127.0.0.1", 65533, deadline_seconds=30.0, process=dead)


def test_the_dead_peer_check_fails_fast(monkeypatch):
    """Waiting the full deadline for a process that already exited is wasted."""
    import time

    dead = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.exit(1)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    dead.wait(timeout=30)

    started = time.monotonic()
    with pytest.raises(RuntimeError):
        wait_for_port("127.0.0.1", 65533, deadline_seconds=30.0, process=dead)

    assert time.monotonic() - started < 5.0


def test_a_genuinely_absent_listener_still_times_out():
    """The original behaviour must survive when there is no process to blame."""
    with pytest.raises(TimeoutError, match="no peer listening"):
        wait_for_port("127.0.0.1", 65533, deadline_seconds=0.3)
