"""The README's headline numbers must match the tree (self-enforcing docs).

Those figures went stale twice in a single session — 432 → 459 → 493 tests
and 102 → 106 → 111 files — because every change that adds a file or a test
silently invalidates them. A document quoting exact counts either gets a
mechanical check or quietly becomes wrong, and this project's whole posture
is that invariants are enforced rather than remembered.

Counts come from a SUBPROCESS collection, not from the running session:
``request.session.testscollected`` reports only what the current invocation
gathered, so ``pytest tests/unit`` would see ~30 and fail spuriously.
``--collect-only`` executes nothing, so there is no recursion.

The file count is measured with ``git ls-files``, i.e. the TRACKED tree,
which is exactly what the README claims. A new file therefore has to be
staged before this test agrees — which is the intended moment to notice.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

README = Path("README.md")
_COLLECTED = re.compile(r"(\d+) tests? collected")

# Each claim: a label, and the pattern that must still find it in the README.
TEST_COUNT = (r"\*\*(\d+) tests\*\*", "test-suite total")
FILE_COUNT = (r"\*\*(\d+)\*\* tracked Python files", "tracked .py count")
MAX_LINES = (r"max: (\d+)\)", "longest-file line count")
GUIDE_TOTAL = (r"# expected: (\d+) passed", "execution-guide expected total")


@pytest.fixture(scope="module")
def readme():
    return README.read_text(encoding="utf-8")


def documented(readme, claim):
    """Read one figure the README states, failing if the claim vanished."""
    pattern, label = claim
    match = re.search(pattern, readme)
    assert match, f"README no longer states the {label} (pattern: {pattern})"
    return int(match.group(1))


@pytest.fixture(scope="module")
def collected_tests():
    """The FULL suite's count, whatever subset this invocation is running."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True,
    )
    match = _COLLECTED.search(result.stdout)
    assert match, f"could not read a collection count:\n{result.stdout[-400:]}"
    return int(match.group(1))


@pytest.fixture(scope="module")
def tracked_python_files():
    if not Path(".git").exists():
        pytest.skip("not a git checkout; the tracked-file count is unmeasurable")
    listing = subprocess.run(
        ["git", "ls-files", "*.py"], capture_output=True, text=True, check=True
    ).stdout
    return [line for line in listing.splitlines() if line]


def test_the_documented_test_count_matches_the_suite(readme, collected_tests):
    assert documented(readme, TEST_COUNT) == collected_tests


def test_the_execution_guide_quotes_the_same_total(readme, collected_tests):
    """Two places state the total; both must move together."""
    assert documented(readme, GUIDE_TOTAL) == collected_tests


def test_the_documented_file_count_matches_the_tracked_tree(
    readme, tracked_python_files
):
    assert documented(readme, FILE_COUNT) == len(tracked_python_files)


def test_the_documented_longest_file_is_correct(readme, tracked_python_files):
    longest = max(
        len(Path(path).read_text(encoding="utf-8").splitlines())
        for path in tracked_python_files
    )

    assert documented(readme, MAX_LINES) == longest


def test_the_documented_longest_file_respects_the_line_limit(
    readme, tracked_python_files
):
    """The README must never be able to advertise a violation as compliant."""
    assert documented(readme, MAX_LINES) <= 150


@pytest.mark.parametrize(
    "claim", [TEST_COUNT, FILE_COUNT, MAX_LINES, GUIDE_TOTAL], ids=lambda c: c[1]
)
def test_every_checked_claim_is_still_present(readme, claim):
    """Deleting a figure must fail loudly, not silently disable its check."""
    assert documented(readme, claim) > 0
