"""The trainer must never pull in the MCP transport, even transitively.

Two independent mechanisms, because either alone is weak:

1. a meta-path finder that RAISES on any ``mcp``/``mcp_server`` import. It
   implements ``find_spec`` — the older ``find_module`` protocol was removed
   in Python 3.12, so a finder defining only that method is silently never
   consulted and blocks nothing.
2. a scan of ``sys.modules`` after a full training series has actually RUN,
   so an import deferred inside the training loop cannot slip past.

Both run in a subprocess with a clean interpreter, so modules imported by
the surrounding pytest session cannot mask a real dependency.
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_DRIVER = '''
import json, os, sys
sys.path.insert(0, "src")


def _is_mcp(name):
    return (name == "mcp" or name.startswith("mcp.")
            or name == "mcp_server" or name.startswith("mcp_server."))


class _BlockMCP:
    """Raise rather than resolve, so any MCP import fails the run outright."""

    def find_spec(self, name, path=None, target=None):
        if _is_mcp(name):
            raise ImportError("MCP import blocked in trainer: " + name)
        return None


sys.meta_path.insert(0, _BlockMCP())

from dataclasses import replace
from engine.config import load_config
from strategy.settings import load_strategy_settings
from scripts.run_tournament import train_tournament

out = sys.argv[1]
config = load_config("config/game.json")
cop = replace(load_strategy_settings("police"),
              qtable_path=os.path.join(out, "cop.json"), num_games=2)
thief = replace(load_strategy_settings("thief"),
                qtable_path=os.path.join(out, "thief.json"), num_games=2)

train_tournament(config, cop, thief, 5)

print(json.dumps(sorted(name for name in sys.modules if _is_mcp(name))))
'''


def _run_trainer_with_mcp_blocked(out_dir):
    """Run a real training series in a clean interpreter with MCP blocked."""
    return subprocess.run(
        [sys.executable, "-c", _DRIVER, str(out_dir)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )


def test_a_full_training_run_survives_every_mcp_import_being_blocked(tmp_path):
    result = _run_trainer_with_mcp_blocked(tmp_path)

    assert result.returncode == 0, result.stderr


def test_no_mcp_module_is_loaded_by_a_full_training_run(tmp_path):
    result = _run_trainer_with_mcp_blocked(tmp_path)

    assert result.returncode == 0, result.stderr
    loaded = json.loads(result.stdout.strip().splitlines()[-1])
    assert loaded == [], f"trainer loaded MCP modules: {loaded}"


def test_the_guard_itself_can_fail(tmp_path):
    """Guard-the-guard: the driver must reject a trainer that imports MCP.

    Without this, a finder that silently never fires would leave the two
    tests above passing while enforcing nothing.
    """
    driver = _DRIVER.replace(
        "from scripts.run_tournament import train_tournament",
        "import mcp_server.server\nfrom scripts.run_tournament"
        " import train_tournament",
    )
    result = subprocess.run(
        [sys.executable, "-c", driver, str(tmp_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "MCP import blocked" in result.stderr
