"""Verify a reference-v3 log offline (PRD_17).

`scripts.replay_match` reads the NATIVE dialect, whose turns carry a
``submissions`` block of commit, reveal and Ed25519 signature. A reference-v3
turn carries ``{step, ours, theirs}``, because on that wire the move stays
sealed until ``submit_audit`` and is never revealed per turn. So the native
verifier reported ``TAMPERED!`` on a clean graded series -- the worst failure
an evidence-based submission can have, the evidence being real and the tool
that reads it saying otherwise.

WHAT THIS CAN PROVE, and it is deliberately less than the native verifier:
our own sealed chain is intact and self-consistent, its steps have no gap, and
every move we sealed was legal and reachable on the board the log records.

WHAT IT CANNOT: that THEIR disclosed chain matched the digests they pushed.
That evidence crosses the wire once, inside ``submit_audit``, and is judged
live by ``audit_check.verify_records`` rather than stored here. The verdict
says so out loud -- a verifier that let ``Verified OK`` imply more than it
checked would be worse than none.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.actions import action_delta, parse_action
from mcp_server import interop
from mcp_server.directions import decode

VERIFIED = "Verified OK"
TAMPERED = "TAMPERED!"
_CAVEAT = (
    "NOT COVERED: the opponent's disclosed chain is not in this file. It "
    "crossed the wire once inside submit_audit, where it was judged live; "
    "their verdict on ours is recorded as their_audit_response."
)


@dataclass
class Report:
    """The verdict, what it rests on, and what it does not cover."""

    records: int = 0
    steps: str = ""
    caveat: str = _CAVEAT
    failures: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures

    def __str__(self) -> str:
        if not self.ok:
            return TAMPERED
        return (f"{VERIFIED} (reference-v3)\n"
                f"  {self.records} sealed records re-hashed, "
                f"steps {self.steps} contiguous")


def _contiguity(turns: list) -> list:
    """Steps must run 1..n with no gap; a fabricated middle hides in one."""
    numbers = [turn.get("step") for turn in turns]
    expected = list(range(1, len(numbers) + 1))
    if numbers != expected:
        return [f"steps are not contiguous and ascending from 1: got "
                f"{numbers[:8]}{'...' if len(numbers) > 8 else ''}"]
    return []


def _reachable(previous, position, move: str) -> bool:
    """Did this move actually carry us from the previous cell to this one?

    A payload edited to a plausible move still has to be reachable: re-sealing
    it defeats the digest check, and this is what it does not defeat.
    """
    if previous is None:
        return True
    delta = action_delta(parse_action(decode(move)))
    return (previous[0] + delta[0], previous[1] + delta[1]) == tuple(position)


def _on_board(position, size: int) -> bool:
    return 0 <= position[0] < size and 0 <= position[1] < size


def _seal(record: dict, step) -> list:
    """The load-bearing check: the record must re-hash to its own commit."""
    payload, nonce = record.get("payload"), record.get("nonce")
    if payload is None or nonce is None:
        return [f"step {step}: record carries no payload/nonce to re-hash"]
    if interop.commit(payload, nonce) != record.get("commit"):
        return [f"step {step}: record does not re-hash to its own commit"]
    return []


def _walk(turns: list, size: int) -> list:
    """Every sealed position on the board, and reached by the move claimed."""
    faults, previous = [], None
    for turn in turns:
        payload = (turn.get("ours") or {}).get("payload") or {}
        step = turn.get("step")
        position = payload.get("position")
        move = payload.get("move")
        if not isinstance(position, list) or len(position) != 2 or not move:
            faults.append(f"step {step}: sealed record names no position/move")
            continue
        if not _on_board(position, size):
            faults.append(f"step {step}: sealed position {position} is off a "
                          f"{size}x{size} board")
        elif not _reachable(previous, position, move):
            faults.append(f"step {step}: {move} does not carry {previous} to "
                          f"{position}")
        previous = tuple(position)
    return faults


def _claim(log: dict, turns: list) -> list:
    """A claim of a longer game than the log records is refused."""
    claimed = (log.get("result_claim") or {}).get("steps")
    if isinstance(claimed, int) and claimed != len(turns):
        return [f"result_claim says {claimed} steps; the log records "
                f"{len(turns)}"]
    return []


def verify(log: dict, grid_size: int = 7) -> Report:
    """Judge one reference-v3 sub-game log."""
    turns = log.get("turns") or []
    report = Report(records=len(turns))
    if not turns:
        report.failures.append("log records no turns")
        return report

    report.steps = f"{turns[0].get('step')}-{turns[-1].get('step')}"
    report.failures.extend(_contiguity(turns))
    for turn in turns:
        report.failures.extend(_seal(turn.get("ours") or {},
                                     turn.get("step")))
    report.failures.extend(_walk(turns, grid_size))
    report.failures.extend(_claim(log, turns))
    return report
