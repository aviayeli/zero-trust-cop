"""The official Appendix-F consensus scope, derived from our own artifacts.

The load-bearing case is a known answer: ZeroOne0 independently derived
3997 bytes and 5077306a...0373 from THEIR artifacts with a separate
implementation. If our derivation agrees byte-for-byte, two independent
implementations agree, which is the only thing a settlement digest is for.

Deliberately NOT reading anything ZeroOne0 sent: the whole point is that the
scope is rebuilt from evidence we hold.
"""

import json
from pathlib import Path

import pytest

from reporting import official_scope

EVIDENCE = Path("logs/evidence/ZeroOne0-vs-aviayeli")
SETTLED_SHA = "5077306a3703467941ce7593bcf805a022c9f162588acc4f3feca97a045b0373"
SETTLED_LEN = 3997
THEIR_COMMIT = "62404917a4c43acdc600c4b72adecbbe8d6df341"


def _load():
    if not EVIDENCE.exists():
        pytest.skip("the ZeroOne0 evidence bundle is not in this checkout")
    result = json.loads((EVIDENCE / "result_ZeroOne0-vs-aviayeli.json").read_text())
    config = json.loads(
        (EVIDENCE / "config_ZeroOne0-vs-aviayeli_series.json").read_text())
    logs = {
        n: json.loads((EVIDENCE / f"log_ZeroOne0-vs-aviayeli_g0{n}.json").read_text())
        for n in range(1, 7)
    }
    return result, config, logs


def test_the_derived_scope_matches_the_settled_digest():
    result, config, logs = _load()
    scope = official_scope.build(result, config, logs, THEIR_COMMIT)

    assert official_scope.digest(scope) == (SETTLED_SHA, SETTLED_LEN)


def test_the_score_comes_from_the_agreed_config():
    """Scores must be RECOMPUTED, not copied from whatever the opponent said.

    Halving the capture payout must move the scope. If it does not, some
    value was carried across instead of derived, and the digest would agree
    with the opponent for the wrong reason.
    """
    result, config, logs = _load()
    before = official_scope.digest(
        official_scope.build(result, config, logs, THEIR_COMMIT))

    config["scoring"]["capture_cop"] = config["scoring"]["capture_cop"] // 2
    after = official_scope.digest(
        official_scope.build(result, config, logs, THEIR_COMMIT))

    assert before != after, "the scoring table is not reaching the scope"


def test_roles_are_police_and_thief_never_cop():
    """Appendix-F vocabulary. settlement.py's police -> cop alias belongs to
    the HISTORICAL scope; leaking it here would move a settled digest."""
    result, config, logs = _load()
    scope = official_scope.build(result, config, logs, THEIR_COMMIT)

    for row in scope["sub_games"]:
        assert set(row["roles"].values()) == {"police", "thief"}, row["roles"]


def test_the_opponent_commit_is_an_argument_not_a_lookup():
    """It is the one value taken on disclosure, so it must be visible."""
    result, config, logs = _load()
    scope = official_scope.build(result, config, logs, "0" * 40)

    commits = scope["sub_games"][0]["github_commit"]
    assert "0" * 40 in commits.values()
    assert result["github_commit"] in commits.values()
