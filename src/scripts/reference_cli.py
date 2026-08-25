"""The command line for a live reference-v3 series (PRD_10 10.19).

Split from ``run_reference_match`` at the 150-line limit: that module wires a
run together, this decides what an operator may ask for and what they see
when it ends.

Artifacts are written BY DEFAULT. A graded series that leaves only stdout
leaves nothing to grade, and making the operator remember a flag for the
thing the run exists to produce is the wrong default.
"""

from __future__ import annotations

import argparse

from mcp_server.server import PEER_ROLES
from reporting.email_sender import MODES
from scripts.match_report import group_id, report_by_email
from scripts.opponent_endpoints import resolve_endpoints
from scripts.reference_writer import write_series_artifacts


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Live reference-v3 series.")
    parser.add_argument("--seed", type=int, required=True,
                        help="drives the policy RNG for the whole series; a "
                             "series with no seed is unreplayable")
    parser.add_argument("--opponent-url", default=None,
                        help="their /mcp endpoint, when ONE serves both their "
                             "roles and the role rides in the message")
    parser.add_argument("--opponent-cop-url", default=None,
                        help="their COP endpoint, when they run two "
                             "processes. Needs --opponent-thief-url with it")
    parser.add_argument("--opponent-thief-url", default=None,
                        help="their THIEF endpoint. The sides swap every "
                             "sub-game, so both are required together")
    parser.add_argument("--first-role", default="police", choices=PEER_ROLES,
                        help="the side WE play in sub-game 1; it alternates "
                             "from there")
    parser.add_argument("--sub-games", type=int, default=6)
    parser.add_argument("--wait-minutes", type=float, default=5,
                        help="how long to wait for one of THEIR steps before "
                             "declaring the peer stalled. Our peers only "
                             "exist while a run does, so the default 5 forces "
                             "both sides onto the same minute; widen it to "
                             "come up first and let them join")
    parser.add_argument("--config-root", default=None)
    parser.add_argument("--opponent-id", default=None,
                        help="opposing group id; the match ids derive from it "
                             "and ours, SORTED, so both peers name the "
                             "artifacts alike. Defaults to the other party in "
                             "the contract's agreed_between pair -- which is "
                             "only right if that pair names the group you are "
                             "actually playing.")
    parser.add_argument("--logs-dir", default="logs",
                        help="where the four artifacts land, under "
                             "<logs-dir>/<group_id>/")
    parser.add_argument("--email-mode", default=None, choices=MODES,
                        help="override the peer's [email] mode for THIS run. "
                             "Absent, the config decides -- which ships as "
                             "'auto', drafting silently when the OAuth token "
                             "has expired. A graded series should pass "
                             "'send', which reports the failure instead")
    parser.add_argument("--no-artifacts", dest="write_artifacts",
                        action="store_false",
                        help="play without leaving the four files behind; a "
                             "graded run must NOT use this")
    parser.set_defaults(write_artifacts=True)
    args = parser.parse_args(argv)
    # Validated HERE rather than by `required=True`, because the requirement
    # is "one form or the other", which argparse cannot state.
    try:
        resolve_endpoints(args.opponent_url, args.opponent_cop_url,
                          args.opponent_thief_url)
    except ValueError as bad:
        parser.error(str(bad))
    return args


def main(argv=None):
    import asyncio

    args = parse_args(argv)
    from scripts.run_reference_match import run

    summaries = asyncio.run(run(args))
    for summary in summaries:
        print(f"sub_game={summary['sub_game']} role={summary['role']} "
              f"steps={summary['steps']} "
              f"outcome={summary['terminal_reason']}")
        from scripts.reference_artifacts import _accepted

        verdict = summary.get("their_audit_response") or {}
        signed = summary.get("handshake_counter_signed")
        shown = "accepted" if _accepted(verdict) else (
            verdict.get("status") or ("refused" if verdict else "no answer"))
        print(f"  their_audit={shown} "
              f"handshake={'counter-signed' if signed else 'UNVERIFIED'}")

    if args.write_artifacts:
        paths = write_series_artifacts(
            args.logs_dir, summaries, group_id=group_id(args.config_root),
            config_root=args.config_root, opponent_id=args.opponent_id,
        )
        for kind, path in sorted(paths.items()):
            for one in (path if isinstance(path, list) else [path]):
                print(f"{kind}={one}")
        _report(paths["result"], args)
    return summaries


def _report(result_path, args) -> None:
    """Email the series -- and never let that failure discard the series.

    Six played sub-games and a dead OAuth token is a MAIL problem: the four
    artifacts are already on disk and re-sendable by hand. A traceback here
    would throw away the summaries the caller returns and make a completed
    graded run look like a crashed one.
    """
    try:
        report_by_email(result_path, args.config_root, args.logs_dir,
                        mode=args.email_mode)
    except Exception as failure:  # noqa: BLE001 - reporting may not fail play
        print(f"email_report=FAILED {type(failure).__name__}: {failure}",
              flush=True)


if __name__ == "__main__":
    main()
