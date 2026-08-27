"""The values Appendix F mandates, and a checker for them (PRD 21 Part 1).

WHY THIS EXISTS: ``min_games_to_pass`` read 1 for ten days and through two
graded series. Table 18 marks it קבוע, and printed p.139 defines that status as
"ערך מחייב שאינו ניתן לשינוי כלל. סטייה מן הערך הזה פוסלת את הקבוצה" -- a
binding value that cannot be changed at all; deviation DISQUALIFIES the group.

Nothing in this repository checked it, while a 150-line ceiling, a documented
test count and a tracked-file count were all mechanically enforced. That
asymmetry, not the field, was the defect.

PROVENANCE -- read this before trusting the numbers below.
``police_thief_p2p.pdf`` Appendix F is NOT in this repository; ``match_log``
and ``match_payloads`` already carry that caveat. Every value here was
transcribed for us by SMNGRP05, who hold the PDF, with printed page numbers:
the status column at p.135 and p.139, the values in Tables 13, 15, 16, 17
and 18. They are adopted on that transcription, not on our own reading.

THE THREE STATUSES, as defined at p.135/p.139:
  קבוע       binding, unchangeable; deviation disqualifies. Exact equality.
  מינימום    the example value is a FLOOR. Raising by mutual agreement is
             permitted; lowering below it is forbidden.
  משא ומתן   settled entirely in negotiation; the printed value is an example.

Not checked here, deliberately: ``pheromone_min_center_intensity``. Table 16
has three rows, not four, so it is negotiated rather than mandated. It sits in
our terms and our handshake digest because it is ours, not because the book
requires it.
"""

from __future__ import annotations

FIXED_STATUS = "קבוע"
FLOOR_STATUS = "מינימום"

# Thirteen values the book forbids changing at all. Declared once, here --
# a compliance table inlined at each call site is the same defect the
# project constitution forbids for tunables.
FIXED: dict[tuple[str, str], object] = {
    ("board_and_agents", "num_agents"): 2,                      # Table 13
    ("movement_and_barriers", "move_set"): ["N", "S", "E", "W", "STAY"],  # 15
    ("pheromones", "pheromone_center_intensity"): 0.9,          # Table 16
    ("pheromones", "pheromone_decay"): 0.10,                    # Table 16
    ("pheromones", "pheromone_grid_size"): 5,                   # Table 16
    ("scoring", "capture_cop"): 20,                             # Table 17
    ("scoring", "capture_thief"): 5,                            # Table 17
    ("scoring", "survival_cop"): 5,                             # Table 17
    ("scoring", "survival_thief"): 10,                          # Table 17
    ("scoring", "tie_score"): 2,                                # Table 17
    ("network_and_league", "num_games"): 6,                     # Table 18
    ("network_and_league", "diversity_reward"): 10,             # Table 18
    ("network_and_league", "min_games_to_pass"): 2,             # Table 18
}

# Nine values whose printed figure is a floor. Raising is legal; lowering is
# not. A 0 here reads as a clean symmetric experiment and is forbidden --
# SMNGRP05 measured 240 matches on max_barriers = 0 before discovering that.
FLOORS: dict[tuple[str, str], float] = {
    ("board_and_agents", "grid_size"): 7,                       # Table 13
    ("movement_and_barriers", "max_barriers"): 14,              # Table 15
    ("movement_and_barriers", "max_moves"): 35,                 # Table 15
    ("movement_and_barriers", "survival_threshold"): 35,        # Table 15
    ("rate_limiter_gatekeeper", "requests_per_minute"): 30,     # Table 19
    ("rate_limiter_gatekeeper", "concurrent_requests"): 2,      # Table 19
    ("rate_limiter_gatekeeper", "retry_backoff_sec"): 5,        # Table 19
    ("rate_limiter_gatekeeper", "max_retries"): 3,              # Table 19
    ("rate_limiter_gatekeeper", "queue_depth"): 100,            # Table 19
}

_MISSING = object()


def _read(config: dict, section: str, field: str):
    """One value, or ``_MISSING`` -- absence is a finding, not a default."""
    block = config.get(section)
    if not isinstance(block, dict):
        return _MISSING
    return block.get(field, _MISSING)


def check(config: dict) -> list[str]:
    """Every Appendix F violation in ``config``, as messages. Empty means ok.

    Messages rather than a boolean: "config invalid" would not have helped
    anyone find the ten-day-old ``min_games_to_pass``. Each names the field,
    the value we carry, the value required and the status that makes it so.
    """
    problems: list[str] = []

    for (section, field), required in FIXED.items():
        found = _read(config, section, field)
        if found is _MISSING:
            problems.append(
                f"{section}.{field}: absent, required {required!r} [{FIXED_STATUS}]")
        elif found != required:
            problems.append(
                f"{section}.{field}: ours {found!r}, required {required!r} "
                f"[{FIXED_STATUS} -- deviation disqualifies]")

    for (section, field), floor in FLOORS.items():
        found = _read(config, section, field)
        if found is _MISSING:
            problems.append(
                f"{section}.{field}: absent, floor {floor!r} [{FLOOR_STATUS}]")
        elif not isinstance(found, (int, float)) or isinstance(found, bool):
            problems.append(
                f"{section}.{field}: ours {found!r} is not numeric, "
                f"floor {floor!r} [{FLOOR_STATUS}]")
        elif found < floor:
            problems.append(
                f"{section}.{field}: ours {found!r} is below the floor "
                f"{floor!r} [{FLOOR_STATUS} -- may be raised, never lowered]")

    return problems
