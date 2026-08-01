"""The engine must never learn that ``strategy`` or ``agent`` exist.

PLAN_05 puts ``src/agent/`` ABOVE both ``src/strategy/`` and ``src/engine/``,
so nothing beneath it gains an import. That intention is worth nothing if it
depends on a reviewer remembering it, so this walks the engine package and
fails on any import of a forbidden root.

The check parses each module with ``ast`` rather than scanning its text: a
substring or regex scan reports imports that appear in comments and
docstrings, and misses ones written unusually. Several tests below pin both
halves of that distinction.
"""

import ast
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parents[2] / "src" / "engine"
FORBIDDEN_ROOTS = frozenset({"strategy", "agent"})


def _imported_roots(source):
    """Return the set of ROOT package names imported by a module's source.

    Only the first dotted segment matters, so ``strategy.qvalues`` is a hit
    for ``strategy`` while ``strategyfoo`` is not. ``from . import x`` has no
    module name and is skipped: it cannot reach outside its own package.
    """
    roots = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _engine_modules():
    """Every module under src/engine/, discovered at collection time.

    Globbed rather than listed, so a module added later is covered without
    anyone remembering to extend this file.
    """
    return sorted(ENGINE_DIR.rglob("*.py"))


def test_the_engine_package_was_actually_found():
    """Fail loudly on an empty glob instead of passing with nothing to check."""
    modules = _engine_modules()

    assert len(modules) >= 5, f"engine package not found at {ENGINE_DIR}"
    names = {path.name for path in modules}
    assert {"board.py", "game_loop.py", "resolver.py"} <= names


@pytest.mark.parametrize("module_path", _engine_modules(), ids=lambda p: p.name)
def test_engine_module_imports_neither_strategy_nor_agent(module_path):
    violations = FORBIDDEN_ROOTS & _imported_roots(module_path.read_text())

    assert not violations, f"{module_path.name} imports {sorted(violations)}"


@pytest.mark.parametrize(
    "source",
    [
        "import strategy",
        "import strategy.qvalues",
        "import strategy as s",
        "from strategy import qvalues",
        "from strategy.qvalues import QValues",
        "import agent",
        "from agent.agent_core import AgentPolicy",
        "from ..strategy import qvalues",
        "def f():\n    import strategy",
    ],
)
def test_the_checker_detects_a_forbidden_import(source):
    """Guard the guard: a checker that never fires would enforce nothing."""
    assert FORBIDDEN_ROOTS & _imported_roots(source)


@pytest.mark.parametrize(
    "source",
    [
        "import json",
        "from dataclasses import dataclass",
        "from engine.config import GameConfig",
        "from . import config",
        "import strategyfoo",
        "from agentfoo import thing",
        '"""A docstring mentioning strategy and agent."""',
        "# import strategy\nimport json",
        "MESSAGE = 'from agent import AgentPolicy'",
    ],
)
def test_the_checker_permits_everything_else(source):
    """The last three would all false-positive under a text scan."""
    assert not FORBIDDEN_ROOTS & _imported_roots(source)


def test_a_violating_module_on_disk_is_flagged(tmp_path):
    offender = tmp_path / "offender.py"
    offender.write_text("from strategy.qvalues import QValues\n")

    assert FORBIDDEN_ROOTS & _imported_roots(offender.read_text())


def test_a_clean_module_on_disk_is_not_flagged(tmp_path):
    innocent = tmp_path / "innocent.py"
    innocent.write_text("from engine.board import Board\nimport json\n")

    assert not FORBIDDEN_ROOTS & _imported_roots(innocent.read_text())
