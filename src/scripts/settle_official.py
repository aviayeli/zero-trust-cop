"""Record a settlement reached off the wire, or refuse (PRD 20).

`mutual_agreement.confirmed` is normally written during a live run, from the
opponent's `submit_audit` replies. When a series is settled afterwards --
over `receive_control`, which touches no game state -- that path never runs
and a complete, verified, mutually agreed series stays unreportable.

This closes that gap WITHOUT weakening it. There is no flag meaning "set it
to true". The flag flips only when we rebuilt the official scope from our own
artifacts and our digest equals theirs byte for byte. An opponent's assertion
is not evidence; silence was never acceptance and neither is assertion.

The written block records `channel`, so a reader can always tell a settlement
earned live at `submit_audit` from one confirmed off the wire.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from mcp_server.interop import NONCE_SEPARATOR, canonical_str
from reporting import official_scope

SUB_GAMES = 6
_SERIALIZATION = "json.dumps(scope, sort_keys=True, ensure_ascii=False)"
_CHANNEL = "off-the-wire settlement, not earned at submit_audit"
_METHOD = "independent derivation from our own artifacts, digests compared"


def _records_verify(logs: dict) -> str:
    """Every disclosed opponent record must re-hash to its pushed digest."""
    for number in sorted(logs):
        records = logs[number]["their_audit_response"]["records"]
        for index, record in enumerate(records):
            preimage = (f"{canonical_str(record['payload'])}"
                        f"{NONCE_SEPARATOR}{record['nonce']}").encode()
            if hashlib.sha256(preimage).hexdigest() != record["commit"]:
                return (f"record {index} of sub-game {number} does not re-hash "
                        f"to its commit")
    return ""


def verify(scope: dict, logs: dict, claimed_sha: str, claimed_length: int) -> str:
    """"" when the settlement may be recorded, else the first failing check.

    Order matters. Length is compared BEFORE the digest because a length
    mismatch says roughly WHERE two scopes diverge, while a digest mismatch
    only says THAT they do.
    """
    if len(scope.get("sub_games", ())) != SUB_GAMES:
        return f"expected {SUB_GAMES} sub-games, scope carries " \
               f"{len(scope.get('sub_games', ()))}"
    if len(logs) != SUB_GAMES:
        return f"expected {SUB_GAMES} logs, got {len(logs)}"

    tampered = _records_verify(logs)
    if tampered:
        return tampered

    ours_sha, ours_length = official_scope.digest(scope)
    if ours_length != claimed_length:
        return (f"byte length differs: ours {ours_length}, theirs "
                f"{claimed_length}")
    if ours_sha != claimed_sha:
        return f"digest differs: ours {ours_sha}, theirs {claimed_sha}"
    return ""


def confirm(result_path, scope: dict, claimed_sha: str,
            claimed_length: int) -> dict:
    """Write the confirmation, or raise and leave the artifact untouched."""
    path = Path(result_path)
    result = json.loads(path.read_text(encoding="utf-8"))
    ours_sha, ours_length = official_scope.digest(scope)
    if ours_sha != claimed_sha or ours_length != claimed_length:
        raise ValueError(
            f"refusing to confirm: ours {ours_sha}/{ours_length}, "
            f"theirs {claimed_sha}/{claimed_length}")

    agreement = dict(result.get("mutual_agreement") or {})
    agreement["confirmed"] = True
    # The historical digest is PRESERVED, never overwritten: it is the record
    # of what the played series hashed to under our own settlement scope.
    agreement["official_settlement"] = {
        "sha256": ours_sha,
        "byte_length": ours_length,
        "serialization": _SERIALIZATION,
        "method": _METHOD,
        "channel": _CHANNEL,
    }
    result["mutual_agreement"] = agreement
    path.write_text(json.dumps(result, indent=2, sort_keys=True,
                               ensure_ascii=False) + "\n", encoding="utf-8")
    return agreement


def build_parser() -> argparse.ArgumentParser:
    """Deliberately offers no way to skip the comparison (PRD 20)."""
    parser = argparse.ArgumentParser(
        description="Confirm an off-the-wire settlement, or refuse.")
    parser.add_argument("result", help="path to the result artifact")
    parser.add_argument("--evidence", required=True,
                        help="directory holding the config and six logs")
    parser.add_argument("--their-sha", required=True,
                        help="the digest the opponent published")
    parser.add_argument("--their-length", required=True, type=int,
                        help="their scope's UTF-8 byte length")
    parser.add_argument("--their-commit", required=True,
                        help="the opponent's play-time commit, on disclosure")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    evidence = Path(args.evidence)
    result = json.loads(Path(args.result).read_text(encoding="utf-8"))
    game_id = result["game_id"]
    config = json.loads(
        (evidence / f"config_{game_id}_series.json").read_text(encoding="utf-8"))
    logs = {n: json.loads((evidence / f"log_{game_id}_g0{n}.json")
                          .read_text(encoding="utf-8"))
            for n in range(1, SUB_GAMES + 1)}

    scope = official_scope.build(result, config, logs, args.their_commit)
    reason = verify(scope, logs, args.their_sha, args.their_length)
    if reason:
        print(f"[!!] refusing to confirm: {reason}")
        return 1
    confirm(args.result, scope, args.their_sha, args.their_length)
    print(f"[ok] confirmed off-the-wire settlement {args.their_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
