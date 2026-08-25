"""The cop -> thief README conversion, which nothing checked until now.

`scripts/thief_readme.py` raises when an anchor stops matching, which is the
right behaviour — but it only ever ran at PUSH time, inside
`scripts/sync_repos.sh`. So when the 2026-08-11 retrain rewrote the capture
matrix, rule 6 went stale, the sync stopped completing, and both remotes sat
on the same commit for six days with the two repositories byte-identical.

Moving the check into the suite turns a push-time failure into a test-time
one: `sync_repos.sh` gates on pytest BEFORE it attempts the conversion, so a
stale rule now fails before anything is pushed.

Skipped on the derived thief branch, whose README is the OUTPUT of the
conversion and therefore no longer carries the cop's anchors. The figures the
conversion INSERTS are checked against the shipped Q-table by
``test_thief_figures.py``, which is valid on either branch.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COP_README = (ROOT / "README.md").read_text(encoding="utf-8")
_PERCENT = re.compile(r"(\d+\.\d)%")
# The 200-game block matrix, whose drift is what broke rule 6.
_MATRIX = re.compile(r"^games    0.+?games 1800.2000\s+\d+\.\d%$", re.S | re.M)

pytestmark = pytest.mark.skipif(
    COP_README.startswith("# zero-trust-thief"),
    reason="this checkout is the derived thief edition, not the cop source",
)


def _block_rates(text):
    """The ten per-block percentages from the 200-game matrix."""
    matrix = _MATRIX.search(text)
    assert matrix, "the 200-game block matrix is no longer in the README"
    return [float(value) for value in _PERCENT.findall(matrix.group(0))]


@pytest.fixture(scope="module")
def converted(regenerator):
    return regenerator.convert(COP_README)


def test_every_rule_still_matches_the_cop_readme(converted):
    """The whole point: a stale anchor fails here rather than at push time."""
    assert converted != COP_README


def test_the_survival_matrix_is_the_complement_of_the_capture_matrix(converted):
    """Survival is 100 − capture; a retrain must move both or neither."""
    capture = _block_rates(COP_README)
    survival = _block_rates(converted)

    assert len(capture) == 10, "expected ten 200-game blocks"
    assert len(survival) == len(capture)
    for block, (caught, survived) in enumerate(zip(capture, survival)):
        assert caught + survived == pytest.approx(100.0), f"block {block} disagrees"


def test_the_matrix_columns_keep_their_alignment(converted):
    """A mis-padded percentage silently breaks the ASCII table."""
    cop = _MATRIX.search(COP_README).group(0).splitlines()
    thief = _MATRIX.search(converted).group(0).splitlines()

    assert [len(line) for line in cop] == [len(line) for line in thief]


def test_the_conversion_retitles_and_flips_the_cross_link(converted):
    assert converted.startswith("# zero-trust-thief")
    assert "the pursuing half of this pair lives at" in converted
    assert "**https://github.com/aviayeli/zero-trust-cop**" in converted


def test_no_cop_identity_survives_the_conversion(converted):
    """A half-converted README has shipped once before; it must not again."""
    assert "# zero-trust-cop\n" not in converted
    assert "## 3. Reinforcement learning and convergence" not in converted


def test_the_conversion_is_deterministic(regenerator, converted):
    assert regenerator.convert(COP_README) == converted


def test_a_drifted_matrix_still_fails_loudly(regenerator):
    """Guard-the-guard: reproduce the exact drift that stranded the sync."""
    drifted = COP_README.replace("games    0– 200", "games    0– 999", 1)

    with pytest.raises(SystemExit, match="rule 6"):
        regenerator.convert(drifted)
