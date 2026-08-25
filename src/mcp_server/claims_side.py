"""Our own half of a reference-v3 sub-game (PRD_10 FR3-FR5).

One peer, one piece. The wire never carries a move, so nothing here can
resolve the opponent's -- our position is known, theirs is not, and capture is
settled by CLAIM and honest ANSWER rather than by a resolver holding both.

Three properties are worth stating because none is obvious from the tool
list:

* BOTH peers emit a ``smell_grid``, every turn, of their own accumulated
  trail. Sending ``{}`` reads as conformant and plays as a one-sided
  disclosure: silent about ourselves, fully informed about them.

* The police claims the cell it is STANDING ON. Capture is co-location, so
  that is the only cell it can honestly claim, and the claim rides free on a
  message we were sending anyway.
* The thief answers on its NEXT turn. Their claim for step n arrives after we
  have already pushed step n; answering in n+1 is deterministic, answering
  "in n if it happened to land first" is a race between two peers on public
  tunnels.

The answer is HONEST. Our own sealed chain carries ``position`` at every
step, so a thief that answers "not caught" on a cell its own records place it
on has forged the evidence that convicts it -- at ``submit_audit``, in front
of the opponent's re-hash.
"""

from __future__ import annotations

from engine.actions import parse_action
from engine.player import PlayerState, intended_position
from mcp_server.barrier_record import BarrierRecord
from mcp_server.directions import decode
from mcp_server.smell_trail import SmellTrail

POLICE, THIEF = "police", "thief"
_START = {POLICE: "cop_start", THIEF: "thief_start"}
SURVIVAL_CLAIM = {"type": "survival"}


class Side:
    """The piece WE play, the smell WE emit, and the claims WE owe."""

    def __init__(self, config, board, sender: str):
        if sender not in _START:
            raise ValueError(f"sender must be {POLICE!r} or {THIEF!r}: {sender!r}")
        self.config, self.board, self.sender = config, board, sender
        self.position = tuple(getattr(config, _START[sender]))
        # BOTH peers emit (SPEC 5, confirmed with ali-ahm1 2026-08-24). The
        # opening deposit is our start cell, so our very first turn discloses
        # a trail rather than an empty field.
        self._trail = SmellTrail(config)
        self._trail.step(self.position)
        self._answer: dict | None = None
        # Barriers THEY have placed, and the two endings they settle.
        self._barriers = BarrierRecord(self.board)
        self.caught = False
        self.captured_them = False
        self.they_claimed_survival = False

    def walk(self, move) -> tuple:
        """Move our piece. Off the board or into a barrier resolves to STAY.

        The rule is the engine's own (``resolver._resolve_agent_position``),
        applied to one piece: an illegal move is not an error, it is a move
        that does not happen, and both peers must read it the same way.
        """
        target = intended_position(
            PlayerState(self.position, self.sender), parse_action(decode(move))
        )
        if (self.board.in_bounds(target) and not self.board.is_barrier(target)
                and target not in self._barriers):
            self.position = target
        self._trail.step(self.position)
        return self.position

    def smell_grid(self) -> dict:
        """Our own accumulated trail, whichever side we are playing."""
        return self._trail.grid()

    def extras(self, step: int) -> dict:
        """The optional fields THIS turn carries. Call AFTER ``walk``.

        The claim names our post-move cell, so a caller that builds the turn
        before walking would claim the cell we have just left.
        """
        extras = {}
        if self.sender == POLICE:
            extras["capture_claim"] = list(self.position)
        if self._answer is not None:
            extras["claim_response"], self._answer = self._answer, None
        if self.sender == THIEF and step >= self.config.survival_threshold:
            extras["win_claim"] = dict(SURVIVAL_CLAIM)
        return extras

    def _concede(self) -> None:
        """The game-ending final only WE can see, in the league's vocabulary.

        A ``caught: true`` that ECHOES the cell they claimed is an answer; one
        naming any other cell is a CONCESSION. Ours names our own cell, and
        both settle capture immediately.
        """
        self.caught = True
        self._answer = {"claim": list(self.position), "caught": True}

    def read(self, turn: dict) -> None:
        """Absorb THEIR turn: a barrier, a claim to answer, or our answer."""
        if self._barriers.place(turn.get("barrier_placed")):
            if self._barriers.captures(self.position):
                self._concede()

        claim = turn.get("capture_claim")
        if claim is not None and self.sender == THIEF:
            caught = tuple(claim) == self.position
            self._answer = {"claim": list(claim), "caught": caught}
            self.caught = self.caught or caught

        response = turn.get("claim_response")
        if isinstance(response, dict) and self.sender == POLICE:
            self.captured_them = self.captured_them or bool(response.get("caught"))

        if turn.get("win_claim") is not None:
            self.they_claimed_survival = True
