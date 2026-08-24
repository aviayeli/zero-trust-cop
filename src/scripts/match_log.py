"""Write the four Phase-6 match artifacts under ``logs/<group_id>/`` (D4).

SCHEMA CAVEAT: Appendix F of ``police_thief_p2p.pdf`` is not in this
repository. Only the four FILENAMES come from the specification; the field
layout of the config/log/result payloads is this project's own design and must
be reconciled with the real appendix before submission.
``declaration_<game_id>.json`` is the exception — its schema is fixed by
PRD_03 FR6 and is produced unchanged by ``mcp_server.declaration``.

Both ids are DERIVED, never passed in (``mcp_server.interop``): ``game_id`` is
``"-vs-".join(sorted(pair))`` and ``game_uid`` a UUID over the extracted terms
and that same sorted pair. We used to take our own group name as the game_id,
so each side named the artifacts after itself — one match produced two sets of
filenames and two reports that could not be joined at all.

The log is written to be sufficient for replay on its own: every commitment
digest, every signature and every revealed tuple, so a verifier needs nothing
but the file and the peers' public keys.
"""

import json
import os

from engine.barriers import barrier_layout
from engine.config import load_config
from mcp_server import interop
from mcp_server.declaration import write_declaration
from mcp_server.terms import opponent_of, terms_from_config
from reporting.settlement import build_consensus

from scripts.match_payloads import (
    ARTIFACT_VERSION, ARTIFACT_KINDS, build_log, build_result,
)

def _stamp_config(config_root, group_dir, suffix, game_uid) -> str:
    """Snapshot the shared contract, stamped with the run's identity.

    Copied rather than referenced so the artifact records what the match
    ACTUALLY ran under, and stamped so all four files tie together.
    """
    with open(os.path.join(config_root, "game.json")) as shared:
        snapshot = json.load(shared)
    snapshot["game_uid"] = game_uid
    return _dump(os.path.join(group_dir, f"config_{suffix}.json"), snapshot)


def _dump(path, payload) -> str:
    """Write deterministic JSON so repeated runs are byte-identical."""
    with open(path, "w", encoding="utf-8", newline="\n") as artifact:
        json.dump(payload, artifact, indent=2, sort_keys=True)
        artifact.write("\n")
    return path


def derive_ids(config, group_id, opponent_id=None) -> dict:
    """The two match ids, from inputs both peers already share.

    ``opponent_id`` defaults to the other party in the contract's
    ``agreed_between`` pair, so a normal league match needs no extra argument
    and cannot disagree with the opponent about who is playing. Pass it
    explicitly only for a match the shipped contract does not name.

    The uid is derived from the EXTRACTED terms. Hashing the whole config
    instead yields a uid identical across all four of OUR artifacts -- they
    join each other perfectly, and only the cross-team join fails.
    """
    opponent = opponent_id or opponent_of(config, group_id)
    return {
        "opponent_id": opponent,
        "game_id": interop.game_id(group_id, opponent),
        "game_uid": interop.game_uid(
            terms_from_config(config), group_id, opponent
        ),
    }


def _settled(result, config, ids, group_id, our_role):
    """Attach the cross-team settlement consensus and its signature.

    ``mutual_agreement`` has always asserted agreement; this is the first
    thing in it an opponent can independently RECOMPUTE. Omitted without a
    role: two of our own peers playing each other settle nothing, and a
    signature there would evidence a cross-team agreement that never happened.
    """
    if not our_role:
        return result
    consensus = build_consensus(
        result, config, group_id, ids["opponent_id"], our_role
    )
    result["mutual_agreement"]["consensus"] = consensus
    result["mutual_agreement"]["sha256"] = \
        interop.report_consensus_signature(consensus)
    return result


def write_artifacts(
    output_root, game_number, history, group_id, config_root=None,
    opponent_id=None, our_role=None,
) -> dict:
    """Write all four artifacts and return their paths by kind."""
    group_dir = os.path.join(str(output_root), group_id)
    os.makedirs(group_dir, exist_ok=True)
    root = config_root or "config"
    contract = os.path.join(root, "game.json")
    with open(contract, encoding="utf-8") as shared:
        config = json.load(shared)
    ids = derive_ids(config, group_id, opponent_id)
    game_id = ids["game_id"]
    suffix = f"{game_id}_g{game_number:02d}"

    return {
        "declaration": write_declaration(game_id, group_dir, config_root,
                                         game_uid=ids["game_uid"]),
        "config": _stamp_config(root, group_dir, suffix, ids["game_uid"]),
        "log": _dump(
            os.path.join(group_dir, f"log_{suffix}.json"),
            build_log(
                ids, game_number, history, group_id,
                barriers=barrier_layout(load_config(contract)),
            ),
        ),
        "result": _dump(
            os.path.join(group_dir, f"result_{game_id}.json"),
            _settled(build_result(ids, game_number, history, group_id),
                     config, ids, group_id, our_role),
        ),
    }
