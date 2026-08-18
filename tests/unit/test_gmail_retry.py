"""A transient Google failure must not abort straight to a draft.

`send_game_report` treats ANY exception from `gmail_send` as "no delivery" and
writes a draft. A refused OAuth token deserves that. A momentary 503 does not
— and the contract already names the policy for exactly this: retry_backoff_sec
and max_retries, sitting unread in `rate_limiter_gatekeeper`.

The sleeper is injected so the policy costs no real seconds, and the retry
count is read from the contract rather than inlined.
"""

import pytest

from engine.config import load_config
from reporting.gmail_transport import gmail_send


class _Service:
    """A Gmail service double that fails a set number of times first."""

    def __init__(self, failures, error=None):
        self.failures = failures
        self.attempts = 0
        self.error = error or ConnectionError("503 backend error")

    def __call__(self, message, token_path):
        self.attempts += 1
        if self.attempts <= self.failures:
            raise self.error
        return True


@pytest.fixture
def slept():
    return []


def _send(sender, slept, **kwargs):
    return gmail_send(
        object(), token_path="unused", _transport=sender,
        _sleeper=slept.append, **kwargs,
    )


def test_a_transient_failure_is_retried_and_then_succeeds(slept):
    sender = _Service(failures=2)

    assert _send(sender, slept, retries=3, backoff_sec=5) is True
    assert sender.attempts == 3


def test_the_backoff_grows_and_comes_from_configuration(slept):
    _send(_Service(failures=2), slept, retries=3, backoff_sec=5)

    assert slept == [5, 10]


def test_a_permanent_failure_still_raises_after_the_configured_retries(slept):
    sender = _Service(failures=99)

    with pytest.raises(ConnectionError):
        _send(sender, slept, retries=2, backoff_sec=1)

    assert sender.attempts == 3, "one attempt plus max_retries"


def test_a_missing_token_is_not_retried(slept):
    """No credential is a decision, not a hiccup: draft immediately."""
    sender = _Service(failures=99, error=FileNotFoundError("no OAuth token"))

    with pytest.raises(FileNotFoundError):
        _send(sender, slept, retries=3, backoff_sec=1)

    assert sender.attempts == 1
    assert slept == []


def test_unusable_credentials_are_not_retried_either(slept):
    sender = _Service(failures=99, error=PermissionError("not usable"))

    with pytest.raises(PermissionError):
        _send(sender, slept, retries=3, backoff_sec=1)

    assert sender.attempts == 1


def test_the_retry_policy_defaults_to_the_agreed_contract():
    """No invented numbers: the same block the rate limiter reads."""
    config = load_config("config/game.json")
    sender = _Service(failures=config.max_retries)
    slept = []

    assert gmail_send(object(), "unused", _transport=sender, _sleeper=slept.append)
    assert sender.attempts == config.max_retries + 1
    assert slept[0] == config.retry_backoff_sec
