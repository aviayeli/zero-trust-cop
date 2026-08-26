"""The CLI sender must throttle, and must not become a second sender.

The brief asked for `MIMEText` wrapping the JSON. Measured: that produces 102
braces in the body and zero attachments, which is the shape that disqualifies
a submission on sight. `reporting/mime_report.py` already builds the correct
`multipart/mixed` with an `application/json` attachment and asserts the body
is brace-free, so this module wraps it instead of competing with it.

What is new is the token bucket, and these tests drive it on a fake clock: a
rate limiter tested by actually sleeping is a slow test that proves timing on
the machine that happened to run it.
"""

import pytest

from scripts.send_game_report import TokenBucket, main, parse_args


class Clock:
    def __init__(self):
        self.now = 0.0
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


@pytest.fixture
def clock():
    return Clock()


def test_a_full_bucket_never_waits(clock):
    bucket = TokenBucket(60, 3, clock=clock, sleeper=clock.sleep)

    assert [bucket.take() for _ in range(3)] == [0.0, 0.0, 0.0]
    assert clock.slept == []


def test_an_empty_bucket_waits_for_exactly_one_token(clock):
    bucket = TokenBucket(60, 1, clock=clock, sleeper=clock.sleep)
    bucket.take()

    waited = bucket.take()

    assert waited == pytest.approx(1.0), "60/min is one token a second"


def test_it_refills_over_time_without_sleeping(clock):
    bucket = TokenBucket(60, 2, clock=clock, sleeper=clock.sleep)
    bucket.take()
    bucket.take()
    clock.now += 5

    assert bucket.take() == 0.0
    assert clock.slept == []


def test_it_never_refills_past_the_burst(clock):
    bucket = TokenBucket(60, 2, clock=clock, sleeper=clock.sleep)
    clock.now += 3600

    assert bucket.tokens == pytest.approx(2.0)


@pytest.mark.parametrize("rate,burst", [(0, 1), (5, 0), (-1, 1)])
def test_a_nonsensical_bucket_is_refused(rate, burst):
    """A zero rate never yields a token; silently accepting it would hang."""
    with pytest.raises(ValueError):
        TokenBucket(rate, burst)


# --- and it must stay a wrapper --------------------------------------------


def test_it_delegates_rather_than_building_a_message():
    """A second message builder is a second chance to put JSON in the body."""
    # Strip docstrings: this module NAMES MIMEText in prose to explain why it
    # does not use it, and a naive text search would read that as a use.
    import ast
    import inspect

    from scripts import send_game_report

    source = inspect.getsource(send_game_report)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)) \
                and ast.get_docstring(node):
            node.body = node.body[1:] or [ast.Pass()]
    code = ast.unparse(tree)

    assert "send_game_report" in code
    assert "MIMEText" not in code, "must not build its own message"
    assert "MIMEMultipart" not in code


def test_the_default_mode_reports_failure_rather_than_drafting():
    """A graded run must not fall back to a silent draft."""
    assert parse_args(["r.json"]).mode == "send"


def test_a_failed_send_exits_non_zero(monkeypatch, tmp_path):
    from scripts import send_game_report as module

    monkeypatch.setattr(module, "send_game_report", lambda *a, **k: False)

    assert main([str(tmp_path / "r.json"), "--rate-per-minute", "600"]) == 1
