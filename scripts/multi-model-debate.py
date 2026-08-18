"""Run the multi-model audit debate and write the consensus report.

Entry point only. The debate logic lives in `multi_model_debate.py` and the
transports in `model_connectors.py` / `cloud_connectors.py`, because THIS
filename cannot be imported: `multi-model-debate` is not a valid Python
identifier, so no test could ever `import` it and `python -m` cannot load it.
Keeping the logic in importable modules is what lets the suite cover it; this
file is the runnable wrapper that name requires.

Usage:
    .venv/bin/python scripts/multi-model-debate.py --question "..." \
        --evidence-file docs/PLAN.md
"""

import argparse
import asyncio
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from model_connectors import probe, timeout_for  # noqa: E402
from multi_model_debate import (  # noqa: E402
    debate,
    load_debate_config,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT = PROJECT_ROOT / "docs" / "SUPREME_MULTI_MODEL_CONSENUS.md"


def panel_status(config: dict) -> list:
    """Probe every panellist up front; never let a dead model surprise a round."""
    lines = []
    for agent in config["agents"] + [config["aggregator"]]:
        why = probe(agent["connector"], agent["model"])
        lines.append(
            (agent["role"], f"{agent['connector']}/{agent['model']}",
             "READY" if why is None else f"UNAVAILABLE — {why[:90]}")
        )
    return lines


def render_report(question: str, status: list, rounds: list, report: str) -> str:
    """Assemble the markdown record: who answered, every round, the synthesis."""
    stamp = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    out = [
        "# Supreme Multi-Model Consensus Audit",
        "",
        f"*Generated {stamp} by `scripts/multi-model-debate.py`.*",
        "",
        "> Every previous audit in this repository was ONE model playing four",
        "> specialists. This one is not: each panellist below runs on different",
        "> weights, so a disagreement is evidence rather than a rhetorical device.",
        "",
        f"**Question.** {question}",
        "",
        "## Panel",
        "",
        "| Role | Model | Status |",
        "| :--- | :--- | :--- |",
    ]
    out += [f"| {role} | `{model}` | {state} |" for role, model, state in status]
    out += ["", "## Consensus report", "", report, "", "## Full transcript", ""]
    for index, rnd in enumerate(rounds, start=1):
        out.append(f"### Round {index}")
        out.append("")
        for speaker, text in rnd:
            out += [f"**{speaker}**", "", text, ""]
    return "\n".join(out) + "\n"


def main(argv=None):
    """Probe the panel, run the debate, write the markdown report."""
    parser = argparse.ArgumentParser(description="Multi-model audit debate.")
    parser.add_argument("--question", required=True)
    parser.add_argument("--evidence-file", required=True)
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    parser.add_argument("--config", default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="probe the panel and exit without debating")
    args = parser.parse_args(argv)

    config = (
        load_debate_config(args.config) if args.config else load_debate_config()
    )
    status = panel_status(config)
    for role, model, state in status:
        print(f"  {role:14} {model:28} {state}")
    if args.dry_run:
        return None

    evidence = Path(args.evidence_file).read_text(encoding="utf-8")
    rounds, report = asyncio.run(debate(config, args.question, evidence))

    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        render_report(args.question, status, rounds, report), encoding="utf-8"
    )
    print(f"\nwrote {destination} ({destination.stat().st_size} bytes)")
    return destination


if __name__ == "__main__":
    main()
