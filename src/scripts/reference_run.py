"""Assembling one live run: servers, dialler, loop and artifacts.

Split from ``run_reference_match`` at the 150-line limit; that module is now
the module docstring and the re-exported entry points, this is the wiring.

Two orderings here were each paid for with a lost series. Our servers bind
BEFORE we dial, so the whole time we wait for the opponent we are also
answering them. And each of their endpoints opens ON FIRST USE -- holding one
idle through a 190-second sub-game outlived their 180s watchdog, and it was
dead before the sub-game that needed it began.
"""

from __future__ import annotations

import asyncio
import contextlib

from mcp_server.server import PEER_ROLES, create_app
from scripts.claims_runner import play_series
from scripts.match_report import group_id
from scripts.opponent_endpoints import resolve_endpoints
from scripts.reference_dial import lazy_opponents
from scripts.reference_launch import connect_and_play, polls_for
from scripts.reference_writer import write_sub_game_log

_BOOT_SECONDS = 0.5
_DIAL_RETRY_SEC = 5.0


async def run(args) -> list:
    """Serve both our peers, then play the series through them."""
    apps = {role: create_app(role, config_root=args.config_root)
            for role in PEER_ROLES}
    servers = [asyncio.create_task(app.mcp.run_streamable_http_async())
               for app in apps.values()]
    await asyncio.sleep(_BOOT_SECONDS)
    config = apps[args.first_role].config

    interval = apps[args.first_role].binding.poll_interval_sec

    async def wait():
        await asyncio.sleep(interval)

    # ONE retry mechanism. A probe used to run first, for the full window,
    # and then the connect retried for another -- so `--wait-minutes 30` held
    # for up to sixty and nothing said so. The probe was added when the
    # connect could not retry and left in when it could; a peer that is down
    # fails `open_session` with the same 502 the probe was reading.
    #
    # Our servers are bound before any of this and stay bound throughout, so
    # the whole time we wait for them we are also answering 200 to them --
    # the state their side waits to observe before launching.
    endpoints = resolve_endpoints(args.opponent_url, args.opponent_cop_url,
                                  args.opponent_thief_url)
    # Endpoints open ON FIRST USE (`lazy_opponents`): holding a session for
    # their other process through all of sub-game 1 outlived their watchdog,
    # and it was dead before the sub-game that needed it began.

    pushed = {"n": 0}

    def counted(call):
        async def counting(name, **kwargs):
            if name == "receive_turn":
                pushed["n"] += 1
            return await call(name, **kwargs)
        return counting

    def report(entry):
        # Unbuffered by the -u the entry point is run with, so a live series
        # shows OUR side of the timeline as it happens rather than only at
        # the end -- which for a series that never ends never came.
        print(f"  step {entry['step']:>2} pushed {entry['move']} "
              f"| theirs +{entry['theirs']}s", flush=True)

    def keep(closed):
        """Land this sub-game's log before the next one can go wrong."""
        if not args.write_artifacts:
            return
        path = write_sub_game_log(
            args.logs_dir, closed, group_id=group_id(args.config_root),
            config_root=args.config_root, opponent_id=args.opponent_id)
        print(f"  saved {path}", flush=True)

    async def play(reach):
        async def reach_counted(role):
            return counted(await reach(role))

        return await play_series(
            apps, None, sub_games=args.sub_games, seed=args.seed,
            wait=wait, first_role=args.first_role,
            max_polls=polls_for(args.wait_minutes, interval),
            call_for=reach_counted,
            progress=report, on_sub_game=keep,
        )

    try:
        # Reconnect while they flap -- but only until our first turn is
        # pushed. After that the series is underway and a reconnect would
        # hand them a second sub-game 1 while they still hold the first.
        return await connect_and_play(
            lambda: lazy_opponents(endpoints, config),
            play, args.wait_minutes * 60, lambda: pushed["n"] > 0,
            interval=_DIAL_RETRY_SEC,
        )
    finally:
        for server in servers:
            server.cancel()
        for server in servers:
            with contextlib.suppress(asyncio.CancelledError):
                await server


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
