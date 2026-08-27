"""Recording a settlement that was reached off the wire (PRD 20).

`confirmed` may only flip when WE derived the scope and OUR digest equals
theirs. There is deliberately no flag, argument or env var meaning "set it to
true" -- an opponent's assertion is not evidence, exactly as silence was never
acceptance. The last test in this file is that requirement, as a test.
"""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from reporting import official_scope
from scripts import settle_official

EVIDENCE = Path("logs/evidence/ZeroOne0-vs-aviayeli")
SETTLED_SHA = "5077306a3703467941ce7593bcf805a022c9f162588acc4f3feca97a045b0373"
SETTLED_LEN = 3997
THEIR_COMMIT = "62404917a4c43acdc600c4b72adecbbe8d6df341"
HISTORICAL = "c39d331ce8c45e30823baf2aeae58053020836542aa6e14d584fa2a58af23ee6"


@pytest.fixture
def bundle(tmp_path):
    if not EVIDENCE.exists():
        pytest.skip("the ZeroOne0 evidence bundle is not in this checkout")
    for path in EVIDENCE.glob("*.json"):
        shutil.copy(path, tmp_path / path.name)
    return tmp_path


def _load(bundle):
    result = json.loads((bundle / "result_ZeroOne0-vs-aviayeli.json").read_text())
    config = json.loads(
        (bundle / "config_ZeroOne0-vs-aviayeli_series.json").read_text())
    logs = {n: json.loads(
        (bundle / f"log_ZeroOne0-vs-aviayeli_g0{n}.json").read_text())
        for n in range(1, 7)}
    return result, config, logs


def _scope(bundle):
    result, config, logs = _load(bundle)
    return official_scope.build(result, config, logs, THEIR_COMMIT), logs


def test_a_wrong_digest_refuses(bundle):
    scope, logs = _scope(bundle)
    wrong = "0" + SETTLED_SHA[1:]

    reason = settle_official.verify(scope, logs, wrong, SETTLED_LEN)

    assert reason and "digest" in reason.lower()


def test_a_wrong_byte_length_refuses_and_says_length(bundle):
    """Length is checked FIRST: it localises a divergence, a digest only
    reports one."""
    scope, logs = _scope(bundle)

    reason = settle_official.verify(scope, logs, SETTLED_SHA, SETTLED_LEN + 1)

    assert reason and "length" in reason.lower()
    assert "digest" not in reason.lower()


def test_a_tampered_record_refuses_before_any_digest_check(bundle):
    scope, logs = _scope(bundle)
    logs[3]["their_audit_response"]["records"][0]["commit"] = "f" * 64

    reason = settle_official.verify(scope, logs, SETTLED_SHA, SETTLED_LEN)

    assert reason and "record" in reason.lower()


def test_a_matching_pair_passes(bundle):
    scope, logs = _scope(bundle)

    assert settle_official.verify(scope, logs, SETTLED_SHA, SETTLED_LEN) == ""


def test_a_refusal_leaves_the_artifact_byte_identical(bundle):
    path = bundle / "result_ZeroOne0-vs-aviayeli.json"
    scope, _ = _scope(bundle)
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    with pytest.raises(ValueError):
        settle_official.confirm(path, scope, "0" * 64, SETTLED_LEN)

    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_a_match_sets_confirmed_and_records_provenance(bundle):
    path = bundle / "result_ZeroOne0-vs-aviayeli.json"
    scope, _ = _scope(bundle)

    settle_official.confirm(path, scope, SETTLED_SHA, SETTLED_LEN)
    written = json.loads(path.read_text())["mutual_agreement"]

    assert written["confirmed"] is True
    official = written["official_settlement"]
    assert official["sha256"] == SETTLED_SHA
    assert official["byte_length"] == SETTLED_LEN
    assert "sort_keys" in official["serialization"]
    assert "submit_audit" in official["channel"]


def test_the_historical_digest_survives_the_write(bundle):
    path = bundle / "result_ZeroOne0-vs-aviayeli.json"
    scope, _ = _scope(bundle)

    settle_official.confirm(path, scope, SETTLED_SHA, SETTLED_LEN)

    assert json.loads(path.read_text())["mutual_agreement"]["sha256"] == HISTORICAL


def test_no_cli_argument_can_set_confirmed_without_the_comparison():
    """PRD 20's "no manual override", as a test. A convenience flag added
    later fails the suite instead of passing review."""
    banned = ("force", "override", "assume", "skip", "yes", "confirm-only")
    options = [option
               for action in settle_official.build_parser()._actions
               for option in action.option_strings]

    for option in options:
        assert not any(word in option.lower() for word in banned), option
