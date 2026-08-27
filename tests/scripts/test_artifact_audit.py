"""Reporting Appendix F deviations in LOGGED artifacts, never enforcing them.

SMNGRP05 took our "check every config" point, ran it against their own logged
tree -- 205 artifacts, 5 deviations, none in a counted series -- and handed
back a better design than ours. Our exclusion was a silent one, and as they
put it: a silent exclusion list is the same bug as a silent glob.

So this REPORTS. A logged config records what was agreed for a series already
played; editing it falsifies the record and breaks hashes an opponent
independently verified, and a check that FAILED here would put the shortest
path back to green through rewriting history.

Every exemption carries its reason, and an artifact whose id is not a known
exemption is flagged INVESTIGATE rather than passing quietly.
"""

import json

from scripts import artifact_audit


def _config(**over):
    base = {
        "agreed_between": ["aviayeli", "them"],
        "board_and_agents": {"num_agents": 2, "grid_size": 7},
        "movement_and_barriers": {"move_set": ["N", "S", "E", "W", "STAY"],
                                  "max_barriers": 14, "max_moves": 35,
                                  "survival_threshold": 35},
        "pheromones": {"pheromone_center_intensity": 0.9, "pheromone_decay": 0.1,
                       "pheromone_grid_size": 5},
        "scoring": {"capture_cop": 20, "capture_thief": 5, "survival_cop": 5,
                    "survival_thief": 10, "tie_score": 2},
        "network_and_league": {"num_games": 6, "diversity_reward": 10,
                               "min_games_to_pass": 2},
        "rate_limiter_gatekeeper": {"requests_per_minute": 30,
                                    "concurrent_requests": 2,
                                    "retry_backoff_sec": 5, "max_retries": 3,
                                    "queue_depth": 100},
    }
    base.update(over)
    return base


def test_a_declaration_is_not_a_config_and_is_skipped():
    """A declaration carries identity and hardware, not the mandated sections.
    Running the checker over it produced 22 spurious 'absent' findings in a
    first draft -- noise, which is the same failure as silence."""
    declaration = {"game_uid": "x", "group_name": "aviayeli",
                   "hardware": {"cpu": "..."}, "members": ["Avi"]}

    assert not artifact_audit.is_config(declaration)


def test_a_series_config_is_recognised_by_structure_not_filename():
    assert artifact_audit.is_config(_config())


def test_a_clean_artifact_reports_nothing():
    assert artifact_audit.audit_one("any-id", _config()) == []


def test_a_deviating_artifact_with_a_known_exemption_reports_its_reason():
    config = _config(network_and_league={"num_games": 1, "diversity_reward": 10,
                                         "min_games_to_pass": 2})
    findings = artifact_audit.audit_one("aviayeli", config)

    assert findings
    assert any("num_games" in f for f in findings)
    assert any(artifact_audit.EXEMPT["aviayeli"] in f for f in findings)


def test_an_unknown_id_is_flagged_for_investigation_not_passed_quietly():
    """The part of SMNGRP05's design worth copying."""
    config = _config(network_and_league={"num_games": 1, "diversity_reward": 10,
                                         "min_games_to_pass": 2})

    findings = artifact_audit.audit_one("some-series-nobody-recorded", config)

    assert any("INVESTIGATE" in f for f in findings)


def test_reporting_never_raises_and_never_edits(tmp_path):
    """It reports. A run that could fail would put the shortest path back to
    green through rewriting an artifact."""
    path = tmp_path / "config_x_series.json"
    config = _config(network_and_league={"num_games": 1, "diversity_reward": 10,
                                         "min_games_to_pass": 1})
    path.write_text(json.dumps(config), encoding="utf-8")
    before = path.read_bytes()

    report = artifact_audit.audit_tree(tmp_path)

    assert report["scanned"] == 1
    assert report["deviating"] == 1
    assert path.read_bytes() == before


def test_every_known_exemption_states_a_reason():
    for game_id, reason in artifact_audit.EXEMPT.items():
        assert reason.strip(), f"{game_id} is exempt with no reason given"


def test_the_real_tree_scan_runs_and_reports(capsys):
    """Smoke: the repo's own logs/ scan completes and reports rather than
    raising, whatever it currently finds."""
    report = artifact_audit.audit_tree("logs")

    assert report["scanned"] >= 0
    assert isinstance(report["findings"], list)
