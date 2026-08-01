"""Independently verify a saved match log (Step 5).

``Verified OK`` is reported only when ALL of these hold:

1. every commitment digest re-derives from its revealed tuple;
2. every signature re-verifies against that peer's public key FOR THAT TURN;
3. replaying the logged moves through a fresh GameEpisode reproduces the
   logged final state.

Anything less is ``TAMPERED!``. A verifier that only replayed would accept a
log with forged signatures; one that only checked signatures would accept a
log whose recorded outcome never happened.

The fourth PRD_06 clause — that the two peers' logs agree — is enforced at
MATCH time instead: play_match compares both engines every turn and raises
DivergenceError, so a disagreeing pair never reaches an artifact.
"""

import argparse
import json
from dataclasses import dataclass, field

from engine.config import load_config
from engine.game_loop import GameEpisode
from mcp_server.crypto import verify
from mcp_server.identity import verify_signature
from mcp_server.peer_keys import load_public_keys

VERIFIED = "Verified OK"
TAMPERED = "TAMPERED!"
_ENGINE_ORDER = ("police", "thief")


@dataclass
class VerificationReport:
    """The verdict, plus every reason it failed."""

    ok: bool
    failures: list = field(default_factory=list)

    def __str__(self) -> str:
        return VERIFIED if self.ok else TAMPERED

    def as_dict(self) -> dict:
        return {"status": str(self), "ok": self.ok, "failures": list(self.failures)}


def _check_commitments(log, failures) -> None:
    """Re-derive every digest from what was actually revealed."""
    for turn in log["turns"]:
        for role, entry in turn["submissions"].items():
            if not verify(
                entry["state"],
                entry["move"],
                entry["intent"],
                entry["nonce"],
                entry["h_commit"],
            ):
                failures.append(
                    f"turn {turn['turn']} {role}: commitment does not match reveal"
                )


def _check_signatures(log, public_keys, failures) -> None:
    """Re-verify every signature against the turn it claims to belong to."""
    for turn in log["turns"]:
        for role, entry in turn["submissions"].items():
            if role not in public_keys:
                failures.append(f"turn {turn['turn']} {role}: no public key")
                continue
            if not verify_signature(
                public_keys[role], role, turn["turn"], entry["h_commit"],
                entry["signature"],
            ):
                failures.append(f"turn {turn['turn']} {role}: signature invalid")


def _check_replay(log, config, failures) -> None:
    """Replay the logged moves and compare the reconstructed final state."""
    actions = [
        (
            turn["submissions"]["police"]["move"],
            turn["submissions"]["thief"]["move"],
        )
        for turn in log["turns"]
    ]
    episode = GameEpisode(config).replay(actions)
    recorded = log["turns"][-1]["result"]

    expected = {
        "cop_position": tuple(episode.cop_state.position),
        "thief_position": tuple(episode.thief_state.position),
        "turn_count": episode.turn_count,
    }
    for key, value in expected.items():
        logged = recorded[key]
        if isinstance(value, tuple):
            logged = tuple(logged)
        if logged != value:
            failures.append(f"replay disagrees on {key}: {logged!r} != {value!r}")


def verify_log(log, config, public_keys) -> VerificationReport:
    """Run all three checks and return the combined verdict."""
    failures: list = []
    _check_commitments(log, failures)
    _check_signatures(log, public_keys, failures)
    _check_replay(log, config, failures)
    return VerificationReport(ok=not failures, failures=failures)


def main(argv=None):
    """Verify a log file from disk and exit non-zero when it is tampered."""
    parser = argparse.ArgumentParser(description="Replay-verify a match log.")
    parser.add_argument("log_path")
    parser.add_argument("--config", default="config/game.json")
    parser.add_argument("--config-root", default=None)
    parser.add_argument("--own-role", default="police")
    args = parser.parse_args(argv)

    with open(args.log_path) as log_file:
        log = json.load(log_file)

    report = verify_log(
        log,
        load_config(args.config),
        load_public_keys(args.own_role, args.config_root),
    )
    print(report)
    for failure in report.failures:
        print(f"  - {failure}")
    raise SystemExit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
