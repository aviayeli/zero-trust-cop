"""Step 5: the replay verifier, and proof that it can FAIL.

Each of the three checks is broken INDEPENDENTLY, because a tampered move
would trip all of them at once and hide a check that never actually runs:

  * edit the intent  -> only the commitment digest breaks
  * forge a signature -> only the signature check breaks
  * edit the result   -> only the replay breaks
"""

import asyncio
import copy
import json
from random import Random

import pytest

from engine.barriers import barrier_layout, populated_board
from mcp_server.identity import sign
from mcp_server.peer_client import PeerClient
from mcp_server.peer_keys import load_public_keys
from mcp_server.server import create_app
from scripts.match_payloads import build_log

# The two derived match ids; this suite only needs them present.
IDS = {"game_id": "aviayeli-vs-groupb",
       "game_uid": "1e73c318-5b29-4a7b-1c60-ecb8286265f0"}
from scripts.match_loop import play_match
from scripts.replay_match import TAMPERED, VERIFIED, verify_log


@pytest.fixture
def played(secure_config_root, peer_keys):
    """A genuine in-process match, plus everything needed to verify it."""
    apps = {
        role: create_app(role, config_root=secure_config_root)
        for role in ("police", "thief")
    }
    clients = {
        role: PeerClient(role, apps[role].policy, peer_keys[role], Random(5))
        for role in ("police", "thief")
    }
    config = apps["police"].config
    history = asyncio.run(
        play_match(clients, [apps["police"], apps["thief"]], populated_board(config), config)
    )
    log = build_log(IDS, 1, history, group_id="aviayeli",
                    barriers=barrier_layout(config))
    keys = load_public_keys("police", secure_config_root)
    return log, config, keys


def test_a_genuine_match_verifies(played):
    log, config, keys = played

    report = verify_log(log, config, keys)

    assert report.ok
    assert str(report) == VERIFIED


def test_an_edited_intent_breaks_only_the_commitment_digest(played):
    log, config, keys = played
    tampered = copy.deepcopy(log)
    entry = tampered["turns"][0]["submissions"]["police"]
    entry["intent"] = "lie" if entry["intent"] == "truth" else "truth"

    report = verify_log(tampered, config, keys)

    assert not report.ok
    assert str(report) == TAMPERED
    assert any("commitment" in failure for failure in report.failures)


def test_a_forged_signature_is_caught(played, peer_keys):
    log, config, keys = played
    tampered = copy.deepcopy(log)
    entry = tampered["turns"][0]["submissions"]["police"]
    entry["signature"] = sign(peer_keys["thief"], "police", 0, entry["h_commit"])

    report = verify_log(tampered, config, keys)

    assert not report.ok
    assert any("signature" in failure for failure in report.failures)


def test_an_edited_result_is_caught_by_the_replay(played):
    """Digest and signature stay valid; only the engine replay disagrees."""
    log, config, keys = played
    tampered = copy.deepcopy(log)
    tampered["turns"][-1]["result"]["thief_position"] = [6, 6]

    report = verify_log(tampered, config, keys)

    assert not report.ok
    assert any("replay" in failure for failure in report.failures)


def test_a_flipped_move_is_caught(played):
    log, config, keys = played
    tampered = copy.deepcopy(log)
    police = tampered["turns"][0]["submissions"]["police"]
    police["move"] = "S" if police["move"] != "S" else "N"

    report = verify_log(tampered, config, keys)

    assert not report.ok


def test_a_signature_lifted_to_another_turn_is_caught(played):
    """Signatures bind the turn, so a shuffled log must not verify."""
    log, config, keys = played
    if len(log["turns"]) < 2:
        pytest.skip("needs a multi-turn match")
    tampered = copy.deepcopy(log)
    first = tampered["turns"][0]["submissions"]["police"]
    second = tampered["turns"][1]["submissions"]["police"]
    first["signature"] = second["signature"]

    report = verify_log(tampered, config, keys)

    assert not report.ok
    assert any("signature" in failure for failure in report.failures)


def test_the_report_is_serialisable_for_a_ci_gate(played):
    log, config, keys = played

    json.dumps(verify_log(log, config, keys).as_dict())
