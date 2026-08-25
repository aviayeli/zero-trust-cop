"""A sub-game that was played survives its own closing audit (PRD_13).

On 2026-08-25 against bb-ai-12 we played a full 35-turn sub-game in lockstep,
every turn sealed and answered, and then their peer exited before our closing
`submit_audit` landed. The exception from that one call propagated out of the
sub-game, out of the series, and out of the run: summaries discarded,
`on_sub_game` never called, no log written. Thirty-five sealed records thrown
away, and we played the whole thing again.

An opponent hanging up first does not un-play a sub-game.
"""

import pytest
from unsettled import config, play_closing  # noqa: F401


def test_a_failed_audit_does_not_discard_the_sub_game(config):
    client, summary = play_closing(config, RuntimeError("502 Bad Gateway"))

    assert summary["steps"] == 2
    assert summary["terminal_reason"] == "survival"
    assert client.audits == 1, "the audit must be attempted exactly once"


def test_our_sealed_chain_survives(config):
    """The thing actually being rescued. Without it the artifact holds
    numbers and no evidence."""
    _, summary = play_closing(config, RuntimeError("502 Bad Gateway"))

    assert summary["our_chain"], "the sealed chain was lost"
    assert summary["our_chain"][0]["commit"] == "c"


def test_their_turns_survive_too(config):
    _, summary = play_closing(config, RuntimeError("502 Bad Gateway"))

    assert [turn["step"] for turn in summary["their_turns"]] == [1, 2]


def test_an_anyio_exception_group_is_survived_too(config):
    """A peer's 502 reaches us wrapped by anyio's task group, which does NOT
    subclass Exception -- the trap that cost a live window on 2026-08-24."""
    wrapped = BaseExceptionGroup("tg", [RuntimeError("502 Bad Gateway")])

    _, summary = play_closing(config, wrapped)

    assert summary["steps"] == 2


def test_an_interrupt_is_not_an_audit_failure(config):
    with pytest.raises(KeyboardInterrupt):
        play_closing(config, KeyboardInterrupt())
