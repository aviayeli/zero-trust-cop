"""Independently verify a saved match log (Step 5).

``Verified OK`` is reported only when ALL of these hold:

1. the log has the structural shape a match record must have;
2. turn indices are contiguous and ascending;
3. every commitment digest re-derives from its revealed tuple;
4. every signature re-verifies against that peer's public key FOR THAT TURN;
5. replaying the logged moves reproduces EVERY recorded turn result, and the
   number of logged turns matches the number the replay actually reached.

Anything less is ``TAMPERED!``. Check 5 is stated per-turn deliberately: an
earlier version compared only the final state, so a wholly fabricated middle
certified clean. PRD_06's cross-peer clause is enforced at MATCH time, where
play_match compares both engines every turn. ``--render`` draws the same
reconstruction step by step; it changes no verdict.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field

from engine.config import load_config
from mcp_server.peer_keys import load_public_keys
from scripts.log_checks import check_commitments, check_replay, check_signatures
from scripts.log_shape import check_intents, check_structure, check_turn_indices
from scripts.render_replay import DEFAULT_DELAY, pause_for, render_replay

VERIFIED = "Verified OK"
TAMPERED = "TAMPERED!"
_GREEN, _RED, _RESET = "\033[32m", "\033[31m", "\033[0m"


def colour_enabled(stream=None) -> bool:
    """Colour only a real terminal, and never when NO_COLOR is set.

    Piped, redirected and pytest-captured output must stay byte-clean, or
    escape sequences leak into logs and into assertions on stdout.
    """
    if os.environ.get("NO_COLOR"):
        return False
    stream = sys.stdout if stream is None else stream
    return bool(getattr(stream, "isatty", lambda: False)())


def colourise(verdict: str, ok: bool, enabled: bool) -> str:
    """Wrap a verdict in green (pass) or red (fail) when colour is on."""
    if not enabled:
        return verdict
    return f"{_GREEN if ok else _RED}{verdict}{_RESET}"


@dataclass
class VerificationReport:
    """The verdict, plus every reason it failed."""

    ok: bool
    failures: list = field(default_factory=list)

    def __str__(self) -> str:
        return VERIFIED if self.ok else TAMPERED

    def as_dict(self) -> dict:
        return {"status": str(self), "ok": self.ok, "failures": list(self.failures)}


def verify_log(log, config, public_keys) -> VerificationReport:
    """Run every check and return the combined verdict.

    The blanket except is deliberate and is the V4 fix: a verifier exists to
    ANSWER, and a hostile artifact must not be able to trade a verdict for a
    traceback that a CI gate could mistake for infrastructure failure.
    """
    failures: list = []
    try:
        if check_structure(log, failures):
            check_turn_indices(log, failures)
            check_intents(log, failures)
            check_commitments(log, failures)
            check_signatures(log, public_keys, failures)
            check_replay(log, config, failures)
    except Exception as error:
        failures.append(f"malformed log: {type(error).__name__}: {error}")
    return VerificationReport(ok=not failures, failures=failures)


def parse_args(argv=None):
    """Parse the verifier CLI. Rendering is additive and off by default."""
    parser = argparse.ArgumentParser(description="Replay-verify a match log.")
    parser.add_argument("log_path")
    parser.add_argument("--config", default="config/game.json")
    parser.add_argument("--config-root", default=None)
    parser.add_argument("--own-role", default="police")
    parser.add_argument("--render", action="store_true",
                        help="draw each turn on an ASCII board before verifying")
    parser.add_argument("--render-delay", type=float, default=DEFAULT_DELAY,
                        help="seconds between rendered turns (0 for none)")
    parser.add_argument("--step", action="store_true",
                        help="with --render, wait for Enter between turns")
    return parser.parse_args(argv)


def main(argv=None):
    """Verify a log file from disk and exit non-zero when it is tampered."""
    args = parse_args(argv)

    with open(args.log_path) as log_file:
        log = json.load(log_file)
    config = load_config(args.config)
    public_keys = load_public_keys(args.own_role, args.config_root)

    if args.render:
        render_replay(log, config, public_keys, delay=args.render_delay,
                      pause=pause_for(args.step), colour=colour_enabled())

    report = verify_log(log, config, public_keys)
    print(colourise(str(report), report.ok, colour_enabled()))
    for failure in report.failures:
        print(f"  - {failure}")
    raise SystemExit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
