"""Play a live series against a reference-v3 opponent (PRD_10).

    PYTHONPATH=src .venv/bin/python -m scripts.run_reference_match \\
        --seed 20260801 --sub-games 6 --first-role police \\
        --opponent-url https://their-tunnel.ngrok-free.dev/mcp

This is the entry point for ali-ahm1, replacing ``run_push_match``. Their peer
SERVES the push dialect's ``receive_commit`` and their game loop never reads
it, so a series driven through that wire pushes into a void that answers 200.
Here every half-turn goes out as one ``receive_turn``, and the sub-game closes
with ``submit_audit``.

Our peer runs IN THIS PROCESS. Their turns land in ``app.inbox``, which lives
inside the server, so a runner in another process would complete the
handshake and then poll an inbox it cannot see.

That is also why ``--wait-minutes`` matters. Our peers exist only while a run
does -- they come up with the runner and go down with it -- so a short wait
window forces both teams onto the same minute. On 2026-08-24 three attempts
against ali-ahm1 were lost to exactly that and none to the protocol: their
client retried into our gap, collected 502s, gave up, and never tried again
during the five minutes we were up and answering. Widen the window to come up
first and let them join whenever.

BOTH our peers are served for the whole series: the sides swap every
sub-game, so their turns land in one of our inboxes in one sub-game and the
other in the next.

Unlike the push dialect this surface is NOT opt-in -- it is the league's own,
registered by default -- and unlike the push dialect it VERIFIES: every
disclosed record is re-hashed and compared against the digest that peer
pushed at the time.
"""

from __future__ import annotations


async def run(args) -> list:
    """Re-exported from ``scripts.reference_run``; see that module."""
    from scripts.reference_run import run as _run

    return await _run(args)


def parse_args(argv=None):
    """Re-exported from ``scripts.reference_cli``; see that module."""
    from scripts.reference_cli import parse_args as _parse

    return _parse(argv)


def main(argv=None):
    """Re-exported so ``python -m scripts.run_reference_match`` keeps working."""
    from scripts.reference_cli import main as _main

    return _main(argv)


if __name__ == "__main__":
    main()
