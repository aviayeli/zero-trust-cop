"""The settlement signature: the spaced form, and reaching the artifact.

The scope half -- what the signature is computed OVER -- lives in
``test_settlement.py``. This file covers the serialization (the release's one
SPACED canonical form, signed before the signature key is inserted) and the
wiring that puts it into the result artifact both teams actually email.

The form itself is pinned against the league's shared vectors in
``mcp_server/test_interop_vectors.py``; here we pin our own row onto it.
"""

import json
from pathlib import Path

import pytest

from mcp_server import interop
from reporting.settlement import build_consensus, sign_consensus

US = "aviayeli"
THEM = "groupb"


@pytest.fixture
def config():
    return json.loads(Path("config/game.json").read_text(encoding="utf-8"))


def _result(games):
    return {"game_id": interop.game_id(US, THEM), "games": games}


def _game(number, captured, reason="capture"):
    return {"game_number": number, "captured": captured,
            "terminal_reason": reason, "turns": 12}


@pytest.fixture
def consensus(config):
    return build_consensus(_result([_game(1, True), _game(2, False, "max_moves_reached")]),
                           config, group_id=US, opponent_id=THEM, our_role="cop")


def test_signing_inserts_the_signature_it_excluded_from_its_own_preimage(consensus):
    signed = sign_consensus(consensus)
    signature = signed[interop.CONSENSUS_KEY]

    assert interop.CONSENSUS_KEY not in consensus
    popped = {k: v for k, v in signed.items() if k != interop.CONSENSUS_KEY}
    assert interop.report_consensus_signature(popped) == signature


def test_the_signature_uses_the_spaced_form_not_the_compact_one(consensus):
    """Signing compact fails at the exact moment both teams must agree."""
    signed = sign_consensus(consensus)

    assert signed[interop.CONSENSUS_KEY] != interop.canonical_hash(consensus)


def test_the_signature_moves_when_the_outcome_moves(config):
    """A consensus, not a cache."""
    one = build_consensus(_result([_game(1, True)]), config, group_id=US,
                          opponent_id=THEM, our_role="cop")
    other = build_consensus(_result([_game(1, False, "max_moves_reached")]),
                            config, group_id=US, opponent_id=THEM, our_role="cop")

    assert interop.report_consensus_signature(one) != \
        interop.report_consensus_signature(other)


# --- wiring into the emitted result artifact -------------------------------


def test_the_result_artifact_carries_the_consensus_and_its_signature(tmp_path):
    """The settlement has to reach the artifact both teams actually email, or
    it is a function nobody runs. It lands under `mutual_agreement`, which
    already existed and until now asserted agreement without evidencing it."""
    from scripts.match_log import write_artifacts

    history = [{
        "turn": 0, "submissions": [],
        "result": {"cop_position": (0, 1), "thief_position": (3, 3),
                   "captured": True, "turn_count": 1, "is_terminated": True,
                   "terminal_reason": "capture"},
    }]
    paths = write_artifacts(tmp_path, 1, history, group_id=US,
                            config_root="config", our_role="cop")
    agreement = json.loads(Path(paths["result"]).read_text())["mutual_agreement"]

    assert agreement["confirmed"] is True
    assert agreement["sha256"] == \
        interop.report_consensus_signature(agreement["consensus"])
    assert sorted(agreement["consensus"]) == ["aggregate", "game_id", "sub_games"]


def test_without_a_role_the_result_claims_no_settlement(tmp_path):
    """Two of our own peers playing each other settle nothing. Emitting a
    signature there would assert cross-team agreement that never happened."""
    from scripts.match_log import write_artifacts

    history = [{
        "turn": 0, "submissions": [],
        "result": {"cop_position": (0, 1), "thief_position": (3, 3),
                   "captured": True, "turn_count": 1, "is_terminated": True,
                   "terminal_reason": "capture"},
    }]
    paths = write_artifacts(tmp_path, 1, history, group_id=US,
                            config_root="config")
    agreement = json.loads(Path(paths["result"]).read_text())["mutual_agreement"]

    assert "sha256" not in agreement
    assert "consensus" not in agreement


def test_our_wire_role_is_translated_into_the_contract_vocabulary(config):
    """We say "police" on the wire; the contract and the book say "cop", and
    the role names sit INSIDE the signed preimage."""
    ours = build_consensus(_result([_game(1, True)]), config, group_id=US,
                           opponent_id=THEM, our_role="police")
    contract_named = build_consensus(_result([_game(1, True)]), config,
                                     group_id=US, opponent_id=THEM, our_role="cop")

    assert ours == contract_named
    assert ours["sub_games"][0]["roles"] == {"cop": US, "thief": THEM}


def test_an_unknown_role_is_refused(config):
    with pytest.raises(ValueError, match="our_role"):
        build_consensus(_result([_game(1, True)]), config, group_id=US,
                        opponent_id=THEM, our_role="detective")
