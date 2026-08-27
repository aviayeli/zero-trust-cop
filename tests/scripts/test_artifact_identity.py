"""An artifact must not disagree with its own name.

We found one of these by accident -- a config filenamed for rstabcde carrying
agreed_between ['aviayeli', 'groupb'] -- and SMNGRP05 generalised it across
their 484 named artifacts and found 79, including 37 where ROLES ('cop',
'thief') had been written into a field that names two GROUPS.

Neither team would have looked. It is in no Appendix F table and in no
handshake digest, so every existing guard was green. It survived because it
never reached a filing.

Reports, never enforces, for the same reason as artifact_audit: these are
records of what was agreed, and a failing check would put the shortest path
back to green through editing them.
"""

import json

from scripts import artifact_identity


def test_a_matching_config_reports_nothing():
    data = {"agreed_between": ["aviayeli", "rstabcde"]}

    assert artifact_identity.check_one(
        "config_aviayeli-vs-rstabcde_series.json", data) is None


def test_a_config_naming_a_different_opponent_is_reported():
    data = {"agreed_between": ["aviayeli", "groupb"]}

    finding = artifact_identity.check_one(
        "config_aviayeli-vs-rstabcde_series.json", data)

    assert finding and "groupb" in finding
    assert "aviayeli-vs-rstabcde" in finding


def test_roles_written_where_group_codes_belong_are_called_out():
    """SMNGRP05's 37-file class. 'cop' and 'thief' are seats, not groups."""
    data = {"agreed_between": ["cop", "thief"]}

    finding = artifact_identity.check_one(
        "config_a-vs-b_series.json", data)

    assert finding
    assert "role" in finding.lower() or "placeholder" in finding.lower()


def test_a_placeholder_opponent_is_called_out():
    data = {"agreed_between": ["aviayeli", "opponent-group"]}

    finding = artifact_identity.check_one("config_a-vs-b_series.json", data)

    assert finding and "placeholder" in finding.lower()


def test_our_group_id_must_appear_in_the_filename():
    data = {"group_id": "someone-else"}

    finding = artifact_identity.check_one(
        "result_ZeroOne0-vs-aviayeli.json", data)

    assert finding and "someone-else" in finding


def test_a_declaration_naming_its_own_group_is_fine():
    data = {"group_name": "aviayeli"}

    assert artifact_identity.check_one(
        "declaration_ZeroOne0-vs-aviayeli.json", data) is None


def test_an_unnamed_artifact_is_skipped_not_guessed_about():
    assert artifact_identity.check_one("SHA256SUMS", {"anything": 1}) is None


def test_the_real_tree_reports_only_the_known_1833_case(tmp_path):
    """Our tree today: 112 named artifacts, exactly one disagreement, already
    recorded. This fails loudly if a second one ever appears."""
    report = artifact_identity.scan("logs")

    assert report["scanned"] > 50
    unknown = [f for f in report["findings"]
               if "friendly-1833" not in f]
    assert unknown == [], f"a NEW name/content disagreement appeared: {unknown}"


def test_scanning_never_writes(tmp_path):
    path = tmp_path / "config_a-vs-b_series.json"
    path.write_text(json.dumps({"agreed_between": ["cop", "thief"]}))
    before = path.read_bytes()

    artifact_identity.scan(tmp_path)

    assert path.read_bytes() == before
