"""Byte-conformance against the community league interop kit's CORE vectors.

The opponent re-hashes OUR revealed records with THEIR serializer at the
end-of-game audit. A canonicalization difference on any record is read as
tampering and voids the sub-game for BOTH sides, so these constructions
cannot be verified by self-consistency -- only against a shared fixture.

Fixtures are vendored under ``tests/fixtures/interop/`` from
github.com/Imreec/copthief-league-protocol (CORE vectors only). They are
data, not code: nothing here imports or executes the kit.
"""

import json
from pathlib import Path

import pytest

from mcp_server import interop

VECTORS = Path(__file__).parent.parent / "fixtures" / "interop"


def _load(name: str) -> dict:
    return json.loads((VECTORS / f"{name}.json").read_text(encoding="utf-8"))


def _cases(name: str):
    """Vectors as pytest params, each labelled by the fixture's own note."""
    return [pytest.param(v, id=v.get("note", "")[:60]) for v in _load(name)["vectors"]]


@pytest.mark.parametrize("case", _cases("canonical_json"))
def test_canonical_form_reproduces_the_vector_bytes(case):
    """ensure_ascii=False is the load-bearing detail: Hebrew and emoji stay
    native UTF-8, and keys sort by Unicode CODE POINT."""
    assert interop.canonical_str(case["object"]) == case["canonical"]
    assert interop.canonical_hash(case["object"]) == case["sha256"]


@pytest.mark.parametrize("case", _cases("commit_reveal"))
def test_commit_seals_the_payload_with_a_pipe_appended_nonce(case):
    assert interop.commit(case["payload"], case["nonce"]) == case["commit"]


def test_the_superseded_forms_are_not_what_we_emit():
    """The book publishes three commit constructions; we emit the reference
    one. Pinning the other two keeps a regression from passing silently."""
    divergent = _load("commit_reveal")["divergent_forms"]
    ours = interop.commit(divergent["payload"], divergent["nonce"])

    assert ours == divergent["reference_form"]
    assert ours != divergent["book_ch5_listing_form"]
    assert ours != divergent["book_audit_snippet_form"]


@pytest.mark.parametrize("case", _cases("terms_signature"))
def test_terms_signature_is_the_commit_construction_over_the_terms(case):
    assert interop.terms_signature(case["terms"], case["nonce"]) == case["signature"]


@pytest.mark.parametrize("case", _cases("game_uid"))
def test_both_match_ids_sort_the_group_pair(case):
    assert interop.game_uid(case["terms"], case["group_a"], case["group_b"]) == case["game_uid"]
    assert interop.game_id(case["group_a"], case["group_b"]) == case["game_id"]


@pytest.mark.parametrize("case", _cases("game_uid"))
def test_the_ids_do_not_depend_on_which_peer_derives_them(case):
    """A peer that names ITSELF first derives a different id on each side,
    so one match yields two sets of artifact filenames that never join."""
    forward = interop.game_id(case["group_a"], case["group_b"])
    reversed_ = interop.game_id(case["group_b"], case["group_a"])

    assert forward == reversed_
    assert interop.game_uid(case["terms"], case["group_a"], case["group_b"]) == \
        interop.game_uid(case["terms"], case["group_b"], case["group_a"])


@pytest.mark.parametrize("case", _cases("report_consensus"))
def test_consensus_signature_uses_the_spaced_second_canonical_form(case):
    assert interop.report_consensus_signature(case["report"]) == case["signature"]


@pytest.mark.parametrize("case", _cases("report_consensus"))
def test_the_compact_form_does_not_reproduce_the_consensus_signature(case):
    """The settlement signature is the release's ONE spaced-separator hash.
    Signing it compact fails at the exact moment both teams must agree."""
    assert interop.canonical_hash(case["report"]) == case["compact_form_sha256"]
    assert case["compact_form_sha256"] != case["signature"]


@pytest.mark.parametrize("case", _cases("report_consensus"))
def test_signing_inserts_the_signature_it_excluded_from_its_own_preimage(case):
    """Sign-then-insert: the signature key is absent from what was signed,
    so a verifier pops it, re-serializes spaced, and re-hashes."""
    signed = interop.sign_report(case["report"])

    assert signed == case["signed_report"]
    assert interop.CONSENSUS_KEY not in case["report"]
    popped = {k: v for k, v in signed.items() if k != interop.CONSENSUS_KEY}
    assert interop.report_consensus_signature(popped) == signed[interop.CONSENSUS_KEY]
