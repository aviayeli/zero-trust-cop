"""The transport hardening: User-Agent, split timeouts, and RAM serialisation.

Each of these exists because something measurably failed on this machine, not
because it seemed prudent:

* urllib's default agent is rejected with 403 by bot filters in front of some
  APIs, before the request reaches the service.
* A cold local model spends over a minute loading weights; a 30s ceiling
  aborted it. The same 30s also aborted a HEALTHY cloud call while the host
  was paging that model in, which is why the cloud figure moved to 60s.
* Two 5GB local models do not fit in 7GB of RAM. Queried concurrently, ollama
  answers the second by closing the connection.
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import http_post
import model_connectors as connectors
import multi_model_debate as debate


def test_every_request_carries_a_browser_user_agent(monkeypatch):
    """A 403 from a bot filter never reaches the API to be diagnosed."""
    captured = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout=None):
        captured["headers"] = dict(request.header_items())
        return _Response()

    monkeypatch.setattr(http_post.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(http_post.json, "load", lambda handle: {"ok": True})

    http_post.post("https://example.test/x", {}, 5)

    agent = {k.lower(): v for k, v in captured["headers"].items()}["user-agent"]
    assert "Mozilla" in agent and "Chrome" in agent


def test_a_local_model_gets_far_longer_than_a_cloud_call():
    assert connectors.timeout_for("ollama") == 180.0
    assert connectors.timeout_for("gemini") == 60.0
    assert connectors.timeout_for("groq") == connectors.timeout_for("gemini")


def test_an_http_error_becomes_a_connector_error_naming_the_status(monkeypatch):
    """A 403 must arrive as a readable message, not a traceback."""
    import urllib.error

    def boom(request, timeout=None):
        raise urllib.error.HTTPError(
            "https://example.test/x", 403, "Forbidden", {}, None
        )

    monkeypatch.setattr(http_post.urllib.request, "urlopen", boom)

    with pytest.raises(http_post.ConnectorError, match="403"):
        http_post.post("https://example.test/x", {}, 5)


@pytest.mark.parametrize("name,env", [("groq", "GROQ_API_KEY"),
                                      ("deepseek", "DEEPSEEK_API_KEY")])
def test_a_missing_cloud_key_is_reported_not_raised(name, env, monkeypatch):
    """Fault tolerance: a keyless provider must not sink the panel."""
    monkeypatch.delenv(env, raising=False)

    assert env in connectors.probe(name, "any-model")


def test_local_models_are_queried_one_at_a_time(monkeypatch):
    """Two 5GB models loading at once is what closed the connection."""
    concurrent, peak = 0, 0

    def local(prompt, model, timeout):
        nonlocal concurrent, peak
        concurrent += 1
        peak = max(peak, concurrent)
        import time

        time.sleep(0.15)
        concurrent -= 1
        return "ok"

    monkeypatch.setitem(debate.CONNECTORS, "ollama", local)
    agents = [
        {"role": "A", "connector": "ollama", "model": "x"},
        {"role": "B", "connector": "ollama", "model": "y"},
    ]

    asyncio.run(debate.run_round(agents, "Q?", [], "E", 5))

    assert peak == 1, f"{peak} local models were loaded at once"


def test_cloud_models_are_still_queried_in_parallel(monkeypatch):
    """Serialising everything would make the panel needlessly slow."""
    concurrent, peak = 0, 0

    def cloud(prompt, model, timeout):
        nonlocal concurrent, peak
        concurrent += 1
        peak = max(peak, concurrent)
        import time

        time.sleep(0.15)
        concurrent -= 1
        return "ok"

    monkeypatch.setitem(debate.CONNECTORS, "gemini", cloud)
    agents = [
        {"role": "A", "connector": "gemini", "model": "x"},
        {"role": "B", "connector": "gemini", "model": "y"},
    ]

    asyncio.run(debate.run_round(agents, "Q?", [], "E", 5))

    assert peak > 1, "cloud calls were serialised along with local ones"
