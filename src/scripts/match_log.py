"""Write the four Phase-6 match artifacts under ``logs/<group_id>/`` (D4).

SCHEMA CAVEAT: Appendix F of ``police_thief_p2p.pdf`` is not in this
repository. Only the four FILENAMES come from the specification; the field
layout of the config/log/result payloads is this project's own design and must
be reconciled with the real appendix before submission.
``declaration_<game_id>.json`` is the exception — its schema is fixed by
PRD_03 FR6 and is produced unchanged by ``mcp_server.declaration``.

The log is written to be sufficient for replay on its own: every commitment
digest, every signature and every revealed tuple, so a verifier needs nothing
but the file and the peers' public keys.
"""

import json
import os
import shutil

from mcp_server.declaration import github_commit, write_declaration
from mcp_server.repos import load_repos

ARTIFACT_VERSION = 1
_SUBMISSION_FIELDS = ("h_commit", "signature", "state", "move", "intent", "nonce")


def _plain(value):
    """Make positions JSON-safe without changing their meaning."""
    if isinstance(value, tuple):
        return list(value)
    return value


def _submission_record(submission) -> dict:
    return {field: getattr(submission, field) for field in _SUBMISSION_FIELDS}


def _turn_record(entry) -> dict:
    """One turn: both peers' commitments and reveals, plus the outcome."""
    return {
        "turn": entry["turn"],
        "submissions": {
            submission.role: _submission_record(submission)
            for submission in entry["submissions"]
        },
        "result": {key: _plain(value) for key, value in entry["result"].items()},
    }


def build_log(game_id, game_number, history, group_id) -> dict:
    """Assemble the replayable per-game log payload."""
    return {
        "artifact_version": ARTIFACT_VERSION,
        "game_id": game_id,
        "game_number": game_number,
        "group_id": group_id,
        "turns": [_turn_record(entry) for entry in history],
    }


def build_result(game_id, game_number, history, group_id) -> dict:
    """Assemble the series result payload."""
    final = history[-1]["result"]
    return {
        "artifact_version": ARTIFACT_VERSION,
        "game_id": game_id,
        "group_id": group_id,
        "github_commit": github_commit(),
        "repos": load_repos(),
        "games": [
            {
                "game_number": game_number,
                "turns": len(history),
                "captured": final["captured"],
                "terminal_reason": final["terminal_reason"],
                "cop_position": _plain(final["cop_position"]),
                "thief_position": _plain(final["thief_position"]),
            }
        ],
    }


def _dump(path, payload) -> str:
    """Write deterministic JSON so repeated runs are byte-identical."""
    with open(path, "w", encoding="utf-8", newline="\n") as artifact:
        json.dump(payload, artifact, indent=2, sort_keys=True)
        artifact.write("\n")
    return path


def write_artifacts(
    output_root, game_id, game_number, history, group_id, config_root=None
) -> dict:
    """Write all four artifacts and return their paths by kind."""
    group_dir = os.path.join(str(output_root), group_id)
    os.makedirs(group_dir, exist_ok=True)
    suffix = f"{game_id}_g{game_number:02d}"
    root = config_root or "config"

    shutil.copyfile(
        os.path.join(root, "game.json"),
        os.path.join(group_dir, f"config_{suffix}.json"),
    )
    return {
        "declaration": write_declaration(game_id, group_dir, config_root),
        "config": os.path.join(group_dir, f"config_{suffix}.json"),
        "log": _dump(
            os.path.join(group_dir, f"log_{suffix}.json"),
            build_log(game_id, game_number, history, group_id),
        ),
        "result": _dump(
            os.path.join(group_dir, f"result_{game_id}.json"),
            build_result(game_id, game_number, history, group_id),
        ),
    }
