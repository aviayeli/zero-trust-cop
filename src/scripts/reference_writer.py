"""Writing a reference-v3 series to disk (PRD_10 10.19).

Split from ``reference_artifacts`` at the payload/placement seam: that module
decides WHAT the artifacts say, this decides where they land and under which
names. Everything about placement comes from ``match_log`` -- one source of
truth for artifact naming, id derivation and deterministic JSON -- so the
files a reference-v3 series leaves are indistinguishable in shape and
location from the ones the native dialect leaves.
"""

from __future__ import annotations

import json
import os

from engine.barriers import barrier_layout
from engine.config import load_config
from mcp_server.declaration import write_declaration
from scripts.match_log import _dump, _settled, _stamp_config, derive_ids
from scripts.reference_artifacts import build_log, build_result


def write_series_artifacts(output_root, summaries: list, group_id: str,
                           config_root=None, opponent_id=None) -> dict:
    """Write all four and return their paths; ``log`` is one path per sub-game.

    Raises:
        ValueError: no sub-games. An artifact set asserting a series that was
            never played is worse than none at all.
    """
    if not summaries:
        raise ValueError(
            "refusing to write artifacts for a series with no sub-games: "
            "nothing was played"
        )
    group_dir = os.path.join(str(output_root), group_id)
    os.makedirs(group_dir, exist_ok=True)
    root = config_root or "config"
    contract = os.path.join(root, "game.json")
    with open(contract, encoding="utf-8") as shared:
        config = json.load(shared)

    ids = derive_ids(config, group_id, opponent_id)
    game_id = ids["game_id"]
    barriers = barrier_layout(load_config(contract))
    result = build_result(ids, summaries, group_id)

    return {
        "declaration": write_declaration(game_id, group_dir, config_root,
                                         game_uid=ids["game_uid"]),
        # The pair that actually played, not the contract's placeholder.
        "config": _stamp_config(root, group_dir, f"{game_id}_series",
                                ids["game_uid"],
                                pair=[group_id, ids["opponent_id"]]),
        "log": [
            _dump(
                os.path.join(
                    group_dir, f"log_{game_id}_g{s['sub_game']:02d}.json"),
                build_log(ids, s, group_id, barriers),
            )
            for s in summaries
        ],
        "result": _dump(
            os.path.join(group_dir, f"result_{game_id}.json"),
            # The settlement needs the side we played each sub-game; every
            # game row carries it, so `our_role` here only names the series.
            _settled(result, config, ids, group_id, summaries[0]["role"]),
        ),
    }


def write_sub_game_log(output_root, summary: dict, group_id: str,
                       config_root=None, opponent_id=None) -> str:
    """Write ONE sub-game's log the moment it closes.

    The series writer used to be the only writer, so a run that finished
    sub-game 1 cleanly and then lost the opponent in sub-game 2 left nothing
    at all -- thirty-five verified steps and a mutual audit, deleted by a 502
    that arrived afterwards. A sub-game that completed is evidence; what
    happens next cannot un-play it.

    Byte-identical to what ``write_series_artifacts`` writes for the same
    summary, so a partial run and a completed one agree exactly.
    """
    group_dir = os.path.join(str(output_root), group_id)
    os.makedirs(group_dir, exist_ok=True)
    root = config_root or "config"
    contract = os.path.join(root, "game.json")
    with open(contract, encoding="utf-8") as shared:
        config = json.load(shared)
    ids = derive_ids(config, group_id, opponent_id)
    return _dump(
        os.path.join(group_dir,
                     f"log_{ids['game_id']}_g{summary['sub_game']:02d}.json"),
        build_log(ids, summary, group_id,
                  barrier_layout(load_config(contract))),
    )
