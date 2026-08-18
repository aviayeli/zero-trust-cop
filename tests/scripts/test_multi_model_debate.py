"""The debate harness, exercised entirely against stubs.

No test here touches a network or a subprocess. A suite that called three
model providers would be slow, non-deterministic, and would burn a metered
quota on every run — and the properties worth checking are structural anyway:
that peers are quoted verbatim into the next round, that agents are queried
concurrently rather than in sequence, that one dead model does not sink the
panel, and that the aggregator is asked for exactly four sections.

`sys.path` gymnastics: the debate scripts live in `scripts/` (dev tooling)
rather than `src/`, matching `thief_readme.py`.
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import model_connectors  # noqa: E402
import multi_model_debate as debate  # noqa: E402


@pytest.fixture
def panel():
    return {
        "rounds": 2,
        "timeout_sec": 5,
        "agents": [
            {"role": "Alpha", "connector": "stub", "model": "a"},
            {"role": "Beta", "connector": "stub", "model": "b"},
        ],
        "aggregator": {"role": "Aggregator", "connector": "stub", "model": "z"},
    }


@pytest.fixture
def stub(monkeypatch):
    """A connector that records its prompts and answers deterministically."""
    seen = []

    def call(prompt, model, timeout):
        seen.append((model, prompt))
        return f"answer-from-{model}"

    monkeypatch.setitem(debate.CONNECTORS, "stub", call)
    return seen


def test_the_shipped_config_names_three_distinct_providers():
    """The point of the exercise: not one model wearing three hats."""
    config = debate.load_debate_config()
    connectors = {agent["connector"] for agent in config["agents"]}

    assert len(connectors) == 3, f"only {connectors} — that is not a multi-model panel"


def test_the_first_round_carries_no_peer_context(panel):
    prompt = debate.build_prompt(panel["agents"][0], "Q?", [], "EVIDENCE")

    assert "PREVIOUS ROUND" not in prompt
    assert "EVIDENCE" in prompt


def test_a_later_round_quotes_peers_verbatim(panel):
    transcript = [("Alpha", "alpha said this"), ("Beta", "beta said that")]

    prompt = debate.build_prompt(panel["agents"][0], "Q?", transcript, "E")

    assert "beta said that" in prompt, "peer arguments must be passed on verbatim"
    assert "alpha said this" not in prompt, "an agent must not be fed its own answer"


def test_every_agent_is_queried_each_round(panel, stub):
    rounds = asyncio.run(debate.run_round(panel["agents"], "Q?", [], "E", 5))

    assert [speaker for speaker, _ in rounds] == ["Alpha", "Beta"]
    assert {model for model, _ in stub} == {"a", "b"}


def test_agents_are_queried_concurrently_not_in_sequence(panel, monkeypatch):
    """Sequential querying would make a three-model round three times as slow."""
    running, peak = 0, 0

    def slow(prompt, model, timeout):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        import time

        time.sleep(0.2)
        running -= 1
        return "ok"

    monkeypatch.setitem(debate.CONNECTORS, "stub", slow)
    asyncio.run(debate.run_round(panel["agents"], "Q?", [], "E", 5))

    assert peak > 1, "agents were queried sequentially"


def test_one_dead_model_does_not_sink_the_panel(panel, monkeypatch):
    """A failed connector must be recorded, not raised."""

    def dead(prompt, model, timeout):
        if model == "a":
            raise model_connectors.ConnectorError("quota exhausted")
        return "fine"

    monkeypatch.setitem(debate.CONNECTORS, "stub", dead)
    result = dict(asyncio.run(debate.run_round(panel["agents"], "Q?", [], "E", 5)))

    assert "unavailable" in result["Alpha"] and "quota exhausted" in result["Alpha"]
    assert result["Beta"] == "fine"


def test_the_aggregator_is_asked_for_exactly_the_four_sections(panel):
    rounds = [[("Alpha", "one")], [("Beta", "two")]]

    prompt = debate.build_aggregation_prompt("Q?", rounds)

    for section in ("Consensus", "Disagreement", "Unique Findings", "Analysis"):
        assert f"## {section}" in prompt
    assert "one" in prompt and "two" in prompt, "the full transcript must be passed"
    assert "manufacture agreement" in prompt


def test_a_full_debate_returns_every_round_and_a_report(panel, stub):
    rounds, report = asyncio.run(debate.debate(panel, "Q?", "E"))

    assert len(rounds) == panel["rounds"]
    assert report == "answer-from-z"


def test_probe_reports_why_a_model_is_unusable(monkeypatch):
    def dead(prompt, model, timeout):
        raise model_connectors.ConnectorError("insufficient_quota")

    monkeypatch.setitem(model_connectors.CONNECTORS, "stub", dead)

    assert "insufficient_quota" in model_connectors.probe("stub", "x", 1)
    assert "unknown connector" in model_connectors.probe("nope", "x", 1)
