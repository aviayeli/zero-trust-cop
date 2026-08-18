"""The thing we SHIP must run, not just the thing we have checked out.

Five sittings of guards all tested the working tree. None tested the artifact,
and the gap produced exactly the defect it should have caught: the
`v1.0-submission` tag sat one commit behind master, and that commit was the fix
for four live-transport tests. A clean clone of the tag failed 4/903 while the
working tree passed 910/910. The tests were green and the submission was not.

Two checks, deliberately separated:

* A clean clone of HEAD must PASS THE LIVE-TRANSPORT TESTS. Collection alone
  would not have caught the original bug — it was a child process failing to
  import at runtime, which collects perfectly well. This runs always.
* The tag must point at HEAD. This runs only under ZTC_RELEASE_CHECK, because
  between a commit and a release the tag legitimately lags, and asserting
  otherwise would fail inside `sync_repos.sh`'s own gate and deadlock every
  push. `sync_repos.sh` sets it after moving the tags.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUBMISSION_TAG = "v1.0-submission"
# The suite whose failure the tag shipped: peers spawned as real processes.
ARTIFACT_SUITE = "tests/mcp_server/secure/test_http_match.py"
RELEASE_CHECK = "ZTC_RELEASE_CHECK"


def _git(*args, cwd=PROJECT_ROOT) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def _require_git():
    if not (PROJECT_ROOT / ".git").exists():
        pytest.skip("not a git checkout; there is no artifact to verify")


@pytest.fixture(scope="module")
def clean_clone():
    """A throwaway clone of HEAD — the artifact, not the working tree."""
    _require_git()
    target = tempfile.mkdtemp(prefix="ztc-release-")
    try:
        subprocess.run(
            ["git", "clone", "--quiet", "--no-hardlinks", str(PROJECT_ROOT), target],
            capture_output=True, text=True, check=True,
        )
        yield Path(target)
    finally:
        shutil.rmtree(target, ignore_errors=True)


def test_the_submission_tag_exists(   ):
    """A submission with no tag is not a submission."""
    _require_git()

    assert SUBMISSION_TAG in _git("tag").splitlines()


def test_a_clean_clone_carries_the_committed_tree(clean_clone):
    """Guards the fixture: a clone that silently failed would pass everything."""
    assert (clean_clone / "pyproject.toml").exists()
    assert (clean_clone / ARTIFACT_SUITE).exists()


def test_a_clean_clone_of_head_passes_the_live_transport_tests(clean_clone):
    """The regression itself.

    These spawn real peer processes, so they are the tests that depend on the
    artifact being self-contained. A clone that cannot start its own peers is
    a submission a grader cannot run — which is precisely what was shipped.
    """
    done = subprocess.run(
        [sys.executable, "-m", "pytest", ARTIFACT_SUITE, "-q"],
        cwd=clean_clone, capture_output=True, text=True, timeout=900,
    )

    assert done.returncode == 0, (
        "a clean clone of HEAD cannot run its own live-transport tests:\n"
        + done.stdout[-2000:]
    )


@pytest.mark.skipif(
    not os.environ.get(RELEASE_CHECK),
    reason=f"release check; set {RELEASE_CHECK}=1 (sync_repos.sh does)",
)
def test_the_submission_tag_points_at_head():
    """Run at RELEASE time only.

    Between a commit and a push the tag is legitimately behind, so asserting
    this unconditionally would fail inside sync_repos.sh's own test gate and
    make every future release impossible.
    """
    _require_git()

    assert _git("rev-list", "-n1", SUBMISSION_TAG) == _git("rev-parse", "HEAD"), (
        f"{SUBMISSION_TAG} does not point at HEAD; the tag a grader clones is "
        "not the code that was verified"
    )
