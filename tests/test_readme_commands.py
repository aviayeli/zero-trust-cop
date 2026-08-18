"""The README's COMMANDS must work, not just its figures.

Five audit sittings built mechanical guards for every number this project
publishes — README figures, PLAN figures, state counts, contract keys, thief
README claims — and left the execution guide unchecked. It rotted exactly as
the numbers would have:

    ### 2 — Train the agents offline (reproduces `data/q_table_*.json`)
    ... -m scripts.run_tournament --seed 20260801

That named the SUPERSEDED self-play trainer. Both trainers save to the same
configured `qtable_path`, so a grader following the documented step would have
OVERWRITTEN the shipped tables with ones measuring far worse — the evader
drops from 78% survival to 2.2% against a heuristic pursuer. The documented
reproduction was a destruction, and nothing caught it.

So the guide gets the same enforcement the figures have.
"""

import importlib.util
import re
import tomllib
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
README = PROJECT_ROOT / "README.md"
# `python -m <module>` in any of the spellings the guide uses.
_INVOCATION = re.compile(r"python\s+-m\s+([A-Za-z_][\w.]*)")
# The trainer whose output is the shipped tables.
SHIPPED_TRAINER = "scripts.train_diverse"
SUPERSEDED_TRAINER = "scripts.run_tournament"


@pytest.fixture(scope="module")
def readme():
    return README.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def invoked(readme):
    """Every module the README tells a reader to run, in order."""
    return _INVOCATION.findall(readme)


def test_the_guide_actually_invokes_something(invoked):
    """A regex that silently matched nothing would pass every test below."""
    assert len(invoked) >= 5, f"only found {invoked}"


def test_every_documented_module_exists(invoked):
    """`python -m <module>` on a missing module is an immediate failure."""
    missing = sorted(
        {name for name in invoked if importlib.util.find_spec(name) is None}
    )

    assert not missing, f"README invokes modules that do not exist: {missing}"


def test_the_reproduction_step_names_the_trainer_that_MADE_the_tables(readme):
    """The defect this file exists for.

    Whichever section claims to reproduce `data/q_table_*.json` must name the
    trainer whose output those files actually are.
    """
    heading = "### 2 — Train the agents offline"
    assert heading in readme, "the reproduction section was renamed"
    section = readme[readme.index(heading):]
    section = section[: section.index("###", len(heading))]

    invoked = _INVOCATION.findall(section)

    assert SHIPPED_TRAINER in invoked, (
        f"the reproduction step must RUN {SHIPPED_TRAINER}; it invokes {invoked}"
    )
    assert SUPERSEDED_TRAINER not in invoked, (
        f"{SUPERSEDED_TRAINER} is the superseded self-play trainer; running it "
        "OVERWRITES the shipped tables with weaker ones. Naming it in prose to "
        "warn the reader is fine; invoking it here is not."
    )


def test_the_documented_seed_is_the_one_the_tables_were_trained_on(readme):
    """A correct trainer with the wrong seed reproduces nothing."""
    heading = "### 2 — Train the agents offline"
    section = readme[readme.index(heading):]
    section = section[: section.index("###", len(heading))]

    assert "--seed 20260818" in section


def test_the_documented_table_paths_match_the_peers_configuration(readme):
    """The guide claims to reproduce specific files; they must be the real ones."""
    for role in ("police", "thief"):
        with open(PROJECT_ROOT / "config" / role / "game.toml", "rb") as handle:
            path = tomllib.load(handle)["strategy"]["qtable_path"]

        assert Path(path).name in readme, (
            f"README never mentions {path}, which is where {role} actually writes"
        )


def test_documented_artifacts_exist_on_disk(readme):
    """Every logs/ path the guide passes to a command must be present."""
    referenced = set(re.findall(r"logs/[\w./-]+\.json", readme))
    missing = sorted(
        path for path in referenced if not (PROJECT_ROOT / path).exists()
    )

    assert not missing, f"README references artifacts that do not exist: {missing}"
