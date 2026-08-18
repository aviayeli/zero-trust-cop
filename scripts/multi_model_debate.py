"""A debate between physically different models, not one model in four hats.

Every audit in this repository so far has been one model playing four
specialists, and its own closing caveat each time was that a single reviewer
shares one set of blind spots. This runs the same structure across Anthropic,
Google and a local Meta model: each argues from its own weights, sees the
others' previous round, and a final aggregator reports where they actually
disagreed.

Disagreement is the product. A consensus reached by three vendors is worth
something; a consensus reached by one model asked three times is worth
nothing, and that distinction is the whole reason this exists.
"""

import argparse
import asyncio
import json
from pathlib import Path

from model_connectors import CONNECTORS, ConnectorError, probe

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG = PROJECT_ROOT / "config" / "debate.json"
SECTIONS = ("Consensus", "Disagreement", "Unique Findings", "Analysis")


def load_debate_config(path=CONFIG) -> dict:
    """Load the panel: who debates, on what connector, for how many rounds."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_prompt(agent: dict, question: str, transcript: list, evidence: str) -> str:
    """One agent's prompt: its role, the question, and the others' last round.

    Peers are quoted verbatim rather than summarised. A summary would be this
    process editing its own inputs, which is the failure it exists to avoid.
    """
    parts = [
        f"You are the {agent['role']} on a four-member audit committee reviewing"
        " a zero-trust P2P pursuit-evasion project.",
        f"QUESTION: {question}",
        f"EVIDENCE:\n{evidence}",
    ]
    if transcript:
        peers = "\n\n".join(
            f"--- {speaker} said ---\n{text}"
            for speaker, text in transcript
            if speaker != agent["role"]
        )
        parts.append(f"YOUR PEERS' PREVIOUS ROUND:\n{peers}")
        parts.append(
            "State where you AGREE and where you DISAGREE with them, and why."
            " Do not restate your previous answer."
        )
    parts.append("Answer in under 200 words. Be concrete and cite the evidence.")
    return "\n\n".join(parts)


async def _ask(agent: dict, prompt: str, timeout: float) -> tuple:
    """Query one model off the event loop; a failure never sinks the round."""
    call = CONNECTORS[agent["connector"]]
    try:
        answer = await asyncio.to_thread(call, prompt, agent["model"], timeout)
    except ConnectorError as failure:
        answer = f"[unavailable: {failure}]"
    return agent["role"], answer


async def run_round(agents, question, transcript, evidence, timeout) -> list:
    """Query every agent CONCURRENTLY and return this round's transcript."""
    prompts = [build_prompt(a, question, transcript, evidence) for a in agents]
    return list(
        await asyncio.gather(
            *(_ask(a, p, timeout) for a, p in zip(agents, prompts))
        )
    )


def build_aggregation_prompt(question: str, rounds: list) -> str:
    """Ask the aggregator for exactly the four required sections."""
    body = "\n\n".join(
        f"=== ROUND {index + 1} ===\n"
        + "\n\n".join(f"[{speaker}]\n{text}" for speaker, text in rnd)
        for index, rnd in enumerate(rounds)
    )
    headings = "\n".join(f"## {section}" for section in SECTIONS)
    return (
        "You are the Aggregator. Below is a multi-round debate between three "
        "DIFFERENT models on this question:\n"
        f"{question}\n\n{body}\n\n"
        "Compile the Supreme Consensus Audit Report using EXACTLY these four "
        f"sections and no others:\n{headings}\n\n"
        "Under Disagreement, name which model held which position. Do not "
        "manufacture agreement that is not in the transcript."
    )


async def debate(config: dict, question: str, evidence: str) -> tuple:
    """Run every round, then aggregate. Returns (rounds, report)."""
    timeout = config["timeout_sec"]
    rounds, transcript = [], []
    for _ in range(config["rounds"]):
        transcript = await run_round(
            config["agents"], question, transcript, evidence, timeout
        )
        rounds.append(transcript)
    aggregator = config["aggregator"]
    _, report = await _ask(
        aggregator, build_aggregation_prompt(question, rounds), timeout
    )
    return rounds, report


def main(argv=None):
    """Probe every panellist, run the debate, print the report."""
    parser = argparse.ArgumentParser(description="Multi-model audit debate.")
    parser.add_argument("--question", required=True)
    parser.add_argument("--evidence-file", required=True)
    parser.add_argument("--config", default=str(CONFIG))
    args = parser.parse_args(argv)

    config = load_debate_config(args.config)
    for agent in config["agents"] + [config["aggregator"]]:
        why = probe(agent["connector"], agent["model"])
        print(f"{agent['role']:14} {agent['connector']}/{agent['model']:20}"
              f" {'READY' if why is None else 'UNAVAILABLE: ' + why[:70]}")

    evidence = Path(args.evidence_file).read_text(encoding="utf-8")
    rounds, report = asyncio.run(debate(config, args.question, evidence))
    print("\n" + "=" * 72 + "\nSUPREME CONSENSUS AUDIT REPORT\n" + "=" * 72)
    print(report)
    return rounds, report


if __name__ == "__main__":
    main()
