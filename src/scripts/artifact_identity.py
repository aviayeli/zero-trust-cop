"""An artifact must not disagree with its own name. Report it; never enforce.

We found one of these by accident: a config filenamed for `rstabcde` carrying
``agreed_between: ['aviayeli', 'groupb']``. SMNGRP05 generalised the check
across their 484 named artifacts and found 79 -- including 37 where ROLES
('cop', 'thief') sat in a field that names two GROUPS.

Neither team would have looked. This is in no Appendix F table and in no
handshake digest, so every guard either side had was green. It survived
because it never reached a filing -- which is exactly how a defect like this
survives until it does.

REPORTS, NEVER ENFORCES, for the same reason as ``artifact_audit``: these are
records of what was agreed for series already played. A check that failed
here would put the shortest path back to green through editing the record.

Run it:  PYTHONPATH=src python -m scripts.artifact_identity [logs]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Seats within a sub-game, never group codes. A role here is SMNGRP05's
# 37-file class.
ROLES = {"cop", "thief", "police", "evader"}

# Names that were meant to be filled in and were not.
PLACEHOLDERS = {"groupb", "group-b", "opponent-group", "opponent", "them",
                "yourgroup", "your-group", "tbd"}

# filename pattern -> the field inside that must agree with it
_NAMED = (
    (re.compile(r"^config_(.+)_series\.json$"), "agreed_between"),
    (re.compile(r"^declaration_(.+)\.json$"), "group_name"),
    (re.compile(r"^result_(.+)\.json$"), "group_id"),
    (re.compile(r"^log_(.+)_g\d+\.json$"), "group_id"),
)


def _named_as(filename: str):
    """(game id from the filename, field to compare), or None if unnamed."""
    for pattern, field in _NAMED:
        found = pattern.match(filename)
        if found:
            return found.group(1), field
    return None


def _suspect(token: str) -> str:
    """Why a token is wrong beyond simply not matching, if it is."""
    lowered = str(token).strip().lower()
    if lowered in ROLES:
        return " -- that is a ROLE, not a group code"
    if lowered in PLACEHOLDERS:
        return " -- that is an unfilled placeholder"
    return ""


def check_one(filename: str, data) -> str | None:
    """One finding for this artifact, or None when it agrees with its name."""
    named = _named_as(filename)
    if named is None or not isinstance(data, dict):
        return None
    game_id, field = named
    groups = set(game_id.split("-vs-"))
    value = data.get(field)
    if value is None:
        return None

    if field == "agreed_between":
        if not isinstance(value, list) or len(value) != 2:
            return f"{filename}: {field} is {value!r}, expected two group codes"
        if set(value) == groups:
            return None
        notes = "".join(_suspect(token) for token in value)
        return (f"{filename}: filename says {game_id}, {field} says "
                f"{sorted(value)}{notes}")

    if value in groups:
        return None
    return (f"{filename}: filename says {game_id}, {field} says {value!r}"
            f"{_suspect(value)}")


def scan(root) -> dict:
    """Every named artifact under ``root``. Reads only; never writes."""
    scanned, findings = 0, []
    for path in sorted(Path(root).rglob("*.json")):
        if _named_as(path.name) is None:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        scanned += 1
        found = check_one(path.name, data)
        if found:
            findings.append(f"{path.parent}/{found}")
    return {"scanned": scanned, "findings": findings}


def main(argv=None) -> int:
    root = (argv or sys.argv[1:] or ["logs"])[0]
    report = scan(root)
    print(f"scanned {report['scanned']} named artifacts under {root}")
    print(f"disagreeing with their own filename: {len(report['findings'])}")
    for line in report["findings"]:
        print(f"  {line}")
    return 0  # reporting only: this must never gate a build


if __name__ == "__main__":
    raise SystemExit(main())
