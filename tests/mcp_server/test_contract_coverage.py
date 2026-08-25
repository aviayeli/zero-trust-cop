"""Every key of the agreed contract is consumed, or declared informational.

`config/game.json` is stamped `agreed_between: ["aviayeli", "groupb"]`. Three
separate keys have now been found ASSUMED rather than read, each discovered
long after it shipped:

* `max_barriers` — configured from Phase 0, populated by nothing until Phase 9,
  and worth a measured 0.0% capture rate against a greedy evader.
* `barrier_seed` — added as REQUIRED, which made the agreed schema unloadable.
* `axis_origin_corner` — hardcoded in an `actions.py` docstring, never compared
  against the value both groups agreed on.

Two keys have since MOVED the other way, off the whitelist: `agreed_between`
(now the source of the opponent id both peers derive the match ids from) and
`world.map_area` (now the `setting` term inside the agreed-terms hash). Both
were declared informational and both turned out to be load-bearing, which is
the same finding from the opposite direction.

The pattern is the finding, not any one instance, so it gets a mechanical check
rather than another round of review. A key must be READ somewhere in `src/`, or
be listed below with the reason it never will be. Adding a key to the contract
without doing one of those two things now fails the suite.
"""

import json
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = PROJECT_ROOT / "config" / "game.json"

# Keys no implementation should read, each with the reason.
INFORMATIONAL = {
    "schema_version": "identifies the contract revision; read by humans and diffs",
    "board_and_agents.num_agents": "structurally fixed at 2 by the cop/thief roles",
    "network_and_league.diversity_reward": "league SCORING, awarded by the organiser",
    "network_and_league.min_games_to_pass": "league scoring, not a peer behaviour",
    "network_and_league.max_games_per_team": "league scheduling, not a peer behaviour",
}
# Section names exist to group keys; the loader reads them as paths, not values.
_SECTIONS = {
    "board_and_agents", "world", "movement_and_barriers", "scoring",
    "pheromones", "network_and_league", "rate_limiter_gatekeeper",
}


def _leaf_keys(payload, prefix=""):
    for key, value in payload.items():
        if isinstance(value, dict):
            yield from _leaf_keys(value, f"{prefix}{key}.")
        else:
            yield f"{prefix}{key}"


@pytest.fixture(scope="module")
def contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def source_text():
    """Every tracked Python source file, concatenated once."""
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((PROJECT_ROOT / "src").rglob("*.py"))
    )


def test_every_contract_key_is_consumed_or_declared(contract, source_text):
    """The check that would have caught all three historical misses."""
    unread = []
    for key in _leaf_keys(contract):
        name = key.rsplit(".", 1)[-1]
        if key in INFORMATIONAL:
            continue
        if not re.search(rf"\b{re.escape(name)}\b", source_text):
            unread.append(key)

    assert not unread, (
        "contract keys neither read in src/ nor declared informational: "
        f"{unread}. Implement them, or add them to INFORMATIONAL with the "
        "reason they will never be read."
    )


def _read_somewhere(name: str, source_text: str) -> bool:
    """Is this key ACCESSED in src/, as opposed to merely named there?

    A bare-name search is right for "is it consumed", where a false positive
    only means we believe a key is live. It is wrong here, because a module
    that EMITS a field of the same name into a different document would read
    as a contradiction: `league_result` writes the league report's own
    `schema_version` ("1.1"), which has nothing to do with the contract's
    ("1.3"). So this looks for a read, not a mention.
    """
    return bool(re.search(
        rf"""\[["']{re.escape(name)}["']\]|get\(["']{re.escape(name)}["']""",
        source_text,
    ))


def test_the_whitelist_does_not_cover_keys_that_are_actually_used(
    contract, source_text
):
    """A whitelist that silently absorbs live keys would defeat the check."""
    contradictions = [
        key
        for key in INFORMATIONAL
        if _read_somewhere(key.rsplit(".", 1)[-1], source_text)
    ]

    assert not contradictions, (
        f"declared informational but read in src/: {contradictions}"
    )


def test_the_whitelist_only_names_keys_that_exist(contract):
    """A stale whitelist entry hides the removal of a real key."""
    present = set(_leaf_keys(contract)) | _SECTIONS

    assert not set(INFORMATIONAL) - present, (
        f"whitelist names keys absent from the contract: "
        f"{sorted(set(INFORMATIONAL) - present)}"
    )


def test_every_whitelist_entry_states_a_reason():
    assert all(reason.strip() for reason in INFORMATIONAL.values())


def test_the_precision_does_not_hide_a_real_read(source_text):
    """The narrowed check must still catch a whitelisted key being consumed.

    Its whole job is to stop INFORMATIONAL absorbing a live key, so prove it
    against a key that IS read -- `response_timeout_sec`, which
    `transport.py` and `server.py` both pull off the contract.
    """
    assert _read_somewhere("response_timeout_sec", source_text)
    assert not _read_somewhere("no_such_contract_key_anywhere", source_text)
