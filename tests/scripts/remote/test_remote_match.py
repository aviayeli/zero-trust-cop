"""Against a remote opponent we own ONE half of the game.

``match_loop.play_match`` prepares both peers' submissions and broadcasts
them to both servers, which is correct for a local simulation and wrong for
league play: the opposing group produces its own signed moves and we must
not invent them. What survives the change is mirrored local truth (D2) —
our submission still goes to BOTH servers.

The recovery path, where a turn settles without the wire telling us, is
exercised in ``test_remote_recovery.py``.
"""

def test_only_our_own_role_is_ever_submitted(peers, fake_client, board, config, play, turns):
    """Fabricating the opponent's signed move is the bug this loop avoids."""
    local, remote = peers("cop", "thief", resolves_inline=True)

    play(fake_client("police"), local, remote, board, config)

    assert local.reveals, "the match never ran"
    for peer in (local, remote):
        assert {role for role, *_ in peer.commitments} == {"police"}
        assert {role for role, *_ in peer.reveals} == {"police"}


def test_every_submission_reaches_both_peers(peers, fake_client, board, config, play, turns):
    """Mirrored local truth: our move is broadcast, not sent to one side."""
    local, remote = peers("cop", "thief", resolves_inline=True)

    play(fake_client("police"), local, remote, board, config)

    for peer in (local, remote):
        assert len(peer.commitments) == turns
        assert len(peer.reveals) == turns


def test_a_commitment_precedes_its_reveal_on_every_peer(peers, fake_client, board, config, play, turns):
    """Revealing before committing would let the move be chosen after the fact."""
    local, remote = peers("cop", "thief", resolves_inline=True)

    play(fake_client("police"), local, remote, board, config)

    for peer in (local, remote):
        assert peer.order == ["commit", "reveal"] * turns


def test_an_inline_resolution_needs_no_polling(peers, fake_client, board, config, play, turns):
    local, remote = peers("cop", "thief", resolves_inline=True)

    history = play(fake_client("police"), local, remote, board, config)

    assert len(history) == turns
    assert history[-1]["result"]["is_terminated"] is True
    assert local.status_polls == 0
    assert remote.status_polls == 0


