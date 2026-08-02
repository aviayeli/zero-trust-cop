"""Tests for the computational-fairness declaration artifact."""

import json
import re
import shutil
import subprocess

import pytest

from mcp_server import declaration


EXPECTED_KEYS = {
    "group_name", "members", "repos", "mcp_servers", "hardware",
    "github_commit_hash",
    "github_commit", "timezone", "token_budget", "num_games",
}


def test_payload_has_exact_schema_keys():
    assert set(declaration.build_declaration()) == EXPECTED_KEYS


def test_payload_nested_objects_have_exact_schema_keys():
    payload = declaration.build_declaration()
    assert set(payload["repos"]) == {"cop", "thief"}
    assert set(payload["mcp_servers"]) == {"cop", "thief"}
    assert set(payload["hardware"]) == {"type", "os", "cpu", "ram", "gpu_vram"}


def test_budget_and_game_count_are_integer_values_from_game_config():
    payload = declaration.build_declaration()
    assert payload["token_budget"] == 200000
    assert payload["num_games"] == 1
    assert isinstance(payload["token_budget"], int)
    assert not isinstance(payload["token_budget"], str)
    assert isinstance(payload["num_games"], int)
    assert not isinstance(payload["num_games"], str)


def test_commit_hash_is_current_full_lowercase_hex():
    payload = declaration.build_declaration()
    expected = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    assert payload["github_commit_hash"] == expected
    assert re.fullmatch(r"[0-9a-f]{40}", payload["github_commit_hash"])


def test_declaration_fields_are_loaded_from_config_file(tmp_path):
    config_root = tmp_path / "config"
    config_root.mkdir()
    shutil.copy("config/game.json", config_root / "game.json")
    values = {
        "group_name": "different group",
        "members": ["Ada", "Grace"],
        "repos": {"cop": "https://cop.example", "thief": "https://thief.example"},
        "mcp_servers": {"cop": "https://cop-mcp.example", "thief": "https://thief-mcp.example"},
    }
    (config_root / "declaration.json").write_text(json.dumps(values), encoding="utf-8")
    payload = declaration.build_declaration(str(config_root))
    for key, value in values.items():
        assert payload[key] == value


def test_ram_has_documented_format():
    assert re.fullmatch(r"\d+ GB", declaration.build_declaration()["hardware"]["ram"])


def test_gpu_vram_is_none_without_nvidia_smi_and_always_present():
    gpu_vram = declaration.build_declaration()["hardware"]["gpu_vram"]
    assert "gpu_vram" in declaration.build_declaration()["hardware"]
    if shutil.which("nvidia-smi") is None:
        assert gpu_vram == "none"


def test_failed_probe_uses_sentinel_instead_of_omitting_key(monkeypatch):
    def fail_probe():
        raise OSError("probe unavailable")

    monkeypatch.setattr(declaration, "_probe_gpu_vram", fail_probe)
    payload = declaration.build_declaration()
    assert payload["hardware"]["gpu_vram"] == "none"


def test_write_uses_required_game_id_and_exact_filename(tmp_path):
    path = declaration.write_declaration("match-7", str(tmp_path))
    assert path == str(tmp_path / "declaration_match-7.json")
    assert (tmp_path / "declaration_match-7.json").is_file()
    with pytest.raises(TypeError):
        declaration.write_declaration()


def test_written_file_round_trips_with_exact_schema(tmp_path):
    """The WRITTEN file adds game_uid; build_declaration alone does not.

    The identifier is a property of the run, not of the declaration content,
    which is why it is stamped at write time and why the two key sets differ
    by exactly that one field.
    """
    path = declaration.write_declaration("match-8", str(tmp_path))
    with open(path, encoding="utf-8") as artifact:
        payload = json.load(artifact)
    assert set(payload) == EXPECTED_KEYS | {"game_uid"}
    assert payload["game_uid"] == "match-8"
    assert set(payload["repos"]) == {"cop", "thief"}
    assert set(payload["mcp_servers"]) == {"cop", "thief"}
    assert set(payload["hardware"]) == {"type", "os", "cpu", "ram", "gpu_vram"}


def test_same_game_id_produces_byte_identical_output(tmp_path):
    first = declaration.write_declaration("match-9", str(tmp_path))
    first_bytes = (tmp_path / "declaration_match-9.json").read_bytes()
    second = declaration.write_declaration("match-9", str(tmp_path))
    assert second == first
    assert (tmp_path / "declaration_match-9.json").read_bytes() == first_bytes


def test_missing_declared_config_is_a_setup_error(tmp_path):
    """Declared fields fail loudly: a missing config is a setup error, and
    'unknown' in an artifact submitted for grading is worse than a crash."""
    with pytest.raises(OSError):
        declaration.build_declaration(config_root=str(tmp_path))


def test_incomplete_declared_config_is_a_setup_error(tmp_path):
    """A present-but-incomplete declaration must not silently degrade."""
    (tmp_path / "declaration.json").write_text('{"group_name": "groupa"}')
    (tmp_path / "game.json").write_text(
        '{"network_and_league": {"token_budget_per_series": 1, "num_games": 1}}'
    )
    with pytest.raises(KeyError):
        declaration.build_declaration(config_root=str(tmp_path))


def test_the_hardware_block_is_sealed_as_a_system_spec():
    """Step-0 must name what the hardware block IS, not just list fields."""
    payload = declaration.build_declaration()

    assert payload["hardware"]["type"] == declaration.SYSTEM_SPEC == "system_spec"


def test_the_commit_hash_is_emitted_under_both_names():
    """github_commit_hash is the PRD_03 FR6 name; github_commit is the v3 name."""
    payload = declaration.build_declaration()

    assert payload["github_commit"] == payload["github_commit_hash"]
    assert len(payload["github_commit"]) in (7, 40) or payload["github_commit"] == "unknown"
