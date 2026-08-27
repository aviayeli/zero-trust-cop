"""Report Appendix F deviations in LOGGED artifacts. Never enforce them.

SMNGRP05 took PRD 21's "check every config" point, ran it over their own
logged tree -- 205 artifacts, 5 deviations, none in a counted series -- and
handed back a better design than ours had. Ours excluded logged artifacts
with a test; theirs reports them with a reason each and flags anything
unrecognised. Their line for it: a silent exclusion list is the same bug as
a silent glob.

WHY THIS REPORTS RATHER THAN FAILS. A logged config records what was AGREED
for a series already played. Editing it falsifies the record and breaks
hashes an opponent independently verified. A check that FAILED here would put
the shortest path back to green through rewriting history -- so this one
cannot fail. ``engine.appendix_f`` enforces the LIVE configs; this reports on
the filed ones.

Run it:  PYTHONPATH=src python -m scripts.artifact_audit [logs]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from engine import appendix_f

# The sections a series config carries. A declaration has identity and
# hardware and none of these -- running the checker over one produced 22
# spurious "absent" findings in a first draft, which is noise, and noise is
# the same failure as silence.
_CONFIG_SECTIONS = ("board_and_agents", "movement_and_barriers", "scoring",
                    "network_and_league")

# Known exemptions, each with the reason it is one. An id absent from here is
# reported as INVESTIGATE, never passed quietly.
EXEMPT = {
    "aviayeli":
        "local demonstration config, one sub-game, opponent 'groupb' is a "
        "placeholder; never played against a real group, never filed",
    "ZeroOne0-vs-aviayeli":
        "min_games_to_pass 1 predates the 2026-08-27 correction; the series "
        "was played and reported on it and the record stands as filed",
    "aviayeli-vs-bb-ai-12":
        "min_games_to_pass 1 predates the correction; played and reported, "
        "record stands as filed",
    "aviayeli-vs-rstabcde":
        "min_games_to_pass 1 predates the correction; uncounted friendly",
    # Found by this tool's INVESTIGATE flag on its first run, and recorded
    # rather than quietly mapped: logs/friendly-1833 is FILENAMED for
    # rstabcde but carries agreed_between ['aviayeli', 'groupb'] -- the
    # placeholder -- while sharing the game_uid of the rstabcde configs
    # beside it. The artifact disagrees with its own name. Uncounted
    # friendly, so the stake is low; noted because an inconsistency inside a
    # filed artifact is worth a line even when nothing turns on it.
    "19ce4d0d-dca8-5862-eebd-10c7fed6e4c9":
        "uncounted friendly; artifact is named for rstabcde but records the "
        "placeholder opponent 'groupb' -- inconsistency left as filed",
}


def is_config(data) -> bool:
    """Whether an artifact is a series config, judged by STRUCTURE.

    Not by filename: a config carrying mandated values under another name is
    exactly what our filename-keyed checker could not see.
    """
    if not isinstance(data, dict):
        return False
    return all(isinstance(data.get(section), dict) for section in _CONFIG_SECTIONS)


def _identity(data, path) -> str:
    """The series this artifact belongs to."""
    pair = data.get("agreed_between")
    if isinstance(pair, list) and len(pair) == 2:
        joined = "-vs-".join(sorted(pair))
        if joined in EXEMPT:
            return joined
    return data.get("game_id") or data.get("game_uid") or Path(path).name


def audit_one(identity: str, data: dict) -> list[str]:
    """Deviations in one artifact, each carrying its exemption or a flag."""
    problems = appendix_f.check(data)
    if not problems:
        return []
    reason = EXEMPT.get(identity)
    tail = (f"exempt: {reason}" if reason
            else "NOT a known exemption -- INVESTIGATE")
    return [f"{identity}: {problem} [{tail}]" for problem in problems]


def audit_tree(root) -> dict:
    """Scan every JSON under ``root``; report, never raise, never write."""
    scanned = deviating = 0
    findings: list[str] = []
    unknown = 0
    for path in sorted(Path(root).rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not is_config(data):
            continue
        scanned += 1
        found = audit_one(_identity(data, path), data)
        if found:
            deviating += 1
            unknown += any("INVESTIGATE" in line for line in found)
            findings.extend(f"{path}: {line}" for line in found)
    return {"scanned": scanned, "deviating": deviating,
            "unknown": unknown, "findings": findings}


def main(argv=None) -> int:
    root = (argv or sys.argv[1:] or ["logs"])[0]
    report = audit_tree(root)
    print(f"scanned {report['scanned']} logged config artifacts under {root}")
    print(f"deviating: {report['deviating']} | unrecognised: {report['unknown']}")
    for line in report["findings"]:
        print(f"  {line}")
    if report["unknown"]:
        print("\n[!!] artifacts above marked INVESTIGATE have no recorded "
              "exemption. They are reported, not failed -- decide and record "
              "a reason rather than editing the artifact.")
    return 0  # reporting only: this must never gate a build


if __name__ == "__main__":
    raise SystemExit(main())
