"""Build UNSIGNED and UNENFORCED computational-fairness declarations.

This artifact records what a peer CLAIMS to be running.  It cannot detect a
peer running a different commit than declared, so it is not proof of fairness.

Two different failure postures, deliberately:
  * DECLARED fields (group_name, members, repos, mcp_servers, and the budget
    figures read from game.json) fail loudly.  A missing or incomplete config is
    a setup error, and emitting "unknown" into an artifact that gets submitted
    for grading is worse than crashing.
  * PROBED fields (hardware, timezone, commit hash) fall back to a sentinel.
    Host inspection varies by OS and must never prevent an artifact existing.
"""

import datetime
import json
import os
import platform
import subprocess


_UNKNOWN = "unknown"
_NO_HARDWARE = "none"


def _config_root(config_root: str | None) -> str:
    return config_root if config_root is not None else os.environ.get(
        "ZTC_CONFIG_ROOT", "config"
    )


def _load_required_json(path: str) -> dict:
    """Load a config file that MUST exist. Missing or malformed is a setup error,
    so it propagates rather than degrading into sentinels."""
    with open(path, encoding="utf-8") as source:
        return json.load(source)


def _probe_cpu() -> str:
    processor = platform.processor().strip()
    architectures = {platform.machine().lower(), "x86_64", "amd64", "arm64", "aarch64"}
    if processor and processor.lower() not in architectures:
        return processor
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as cpuinfo:
            for line in cpuinfo:
                field, separator, value = line.partition(":")
                if separator and field.strip() == "model name" and value.strip():
                    return value.strip()
    except OSError:
        pass
    return processor or _UNKNOWN


def _probe_ram() -> str:
    try:
        total_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        return f"{total_bytes // (1024 ** 3)} GB"
    except (AttributeError, OSError, ValueError):
        return _UNKNOWN


def _probe_gpu_vram() -> str:
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return _NO_HARDWARE
    return output or _UNKNOWN


def _probe_string(probe, sentinel: str) -> str:
    try:
        value = probe()
        return value if isinstance(value, str) and value else sentinel
    except Exception:  # Host inspection must never prevent an artifact.
        return sentinel


def _probe_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.SubprocessError):
        return _UNKNOWN


def build_declaration(config_root: str | None = None) -> dict:
    """Return a complete, deterministic declaration payload."""
    root = _config_root(config_root)
    declared = _load_required_json(os.path.join(root, "declaration.json"))
    league = _load_required_json(os.path.join(root, "game.json"))["network_and_league"]
    return {
        "group_name": declared["group_name"],
        "members": declared["members"],
        "repos": {
            "cop": declared["repos"]["cop"],
            "thief": declared["repos"]["thief"],
        },
        "mcp_servers": {
            "cop": declared["mcp_servers"]["cop"],
            "thief": declared["mcp_servers"]["thief"],
        },
        "hardware": {
            "os": _probe_string(platform.platform, _UNKNOWN),
            "cpu": _probe_string(_probe_cpu, _UNKNOWN),
            "ram": _probe_string(_probe_ram, _UNKNOWN),
            "gpu_vram": _probe_string(_probe_gpu_vram, _NO_HARDWARE),
        },
        "github_commit_hash": _probe_string(_probe_commit, _UNKNOWN),
        "timezone": _probe_string(
            lambda: datetime.datetime.now().astimezone().tzname(), _UNKNOWN
        ),
        "token_budget": league["token_budget_per_series"],
        "num_games": league["num_games"],
    }


def write_declaration(
    game_id: str, output_dir: str = ".", config_root: str | None = None
) -> str:
    """Write and return ``declaration_<game_id>.json`` in ``output_dir``."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"declaration_{game_id}.json")
    with open(path, "w", encoding="utf-8", newline="\n") as artifact:
        json.dump(build_declaration(config_root), artifact, indent=2, sort_keys=True)
        artifact.write("\n")
    return path
