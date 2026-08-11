"""A clean checkout must not destroy the public keys it was shipped with.

The shipped ``.pub`` files are tracked; ``signing_key.pem`` is gitignored. So a
fresh clone is exactly the state "public half present, private half absent" —
and republishing there would overwrite the tracked public keys that the
FLAGSHIP MATCH LOG was signed under, turning a genuine log into a verifier
"TAMPERED" verdict on the grader's machine.

``ensure_keys`` therefore refuses that overwrite. This reverses the earlier
ruling in ``test_keygen.py`` that a regenerated key must always republish: log
verifiability on an untouched clone outranks live play on one, and the refusal
is announced so the operator is never left guessing.
"""

import pytest

from mcp_server.keygen import CLEAN_CHECKOUT_WARNING, ensure_keys

PEER_ROLES = ("police", "thief")


@pytest.fixture
def clean_checkout(tmp_path):
    """A workspace holding shipped public halves and no private keys."""
    ensure_keys(str(tmp_path))
    shipped = {
        (own, peer): (tmp_path / own / "peers" / f"{peer}.pub").read_text()
        for own in PEER_ROLES
        for peer in PEER_ROLES
    }
    for role in PEER_ROLES:
        (tmp_path / role / "signing_key.pem").unlink()
    return tmp_path, shipped


def test_a_shipped_public_half_is_never_clobbered(clean_checkout):
    root, shipped = clean_checkout

    ensure_keys(str(root))

    for (own, peer), text in shipped.items():
        assert (root / own / "peers" / f"{peer}.pub").read_text() == text


def test_the_refusal_is_announced_on_stdout(clean_checkout, capsys):
    root, _ = clean_checkout

    ensure_keys(str(root))

    assert CLEAN_CHECKOUT_WARNING in capsys.readouterr().out


def test_one_stale_public_half_protects_only_itself(tmp_path):
    """The thief's own regenerated key still publishes; only police is held."""
    ensure_keys(str(tmp_path))
    police_pub = (tmp_path / "police" / "peers" / "police.pub").read_text()
    thief_pub = (tmp_path / "police" / "peers" / "thief.pub").read_text()
    (tmp_path / "police" / "signing_key.pem").unlink()
    (tmp_path / "thief" / "signing_key.pem").unlink()
    (tmp_path / "police" / "peers" / "thief.pub").unlink()

    ensure_keys(str(tmp_path))

    assert (tmp_path / "police" / "peers" / "police.pub").read_text() == police_pub
    assert (tmp_path / "police" / "peers" / "thief.pub").read_text() != thief_pub


def test_the_private_key_is_still_generated_so_the_gap_is_visible(clean_checkout):
    """Refusing to publish is not refusing to work: the peer is still built."""
    root, _ = clean_checkout

    created = ensure_keys(str(root))

    assert sorted(created) == ["police", "thief"]
    for role in PEER_ROLES:
        assert (root / role / "signing_key.pem").exists()


def test_a_bare_directory_publishes_without_any_warning(tmp_path, capsys):
    """Nothing is shipped in a bare directory, so nothing needs protecting."""
    ensure_keys(str(tmp_path))

    assert CLEAN_CHECKOUT_WARNING not in capsys.readouterr().out


def test_a_rerun_with_both_halves_present_stays_silent(tmp_path, capsys):
    ensure_keys(str(tmp_path))
    capsys.readouterr()

    ensure_keys(str(tmp_path))

    assert capsys.readouterr().out == ""
