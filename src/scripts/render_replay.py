"""Step-by-step ASCII rendering of a match replay (``--render``).

A VIEW over the same reconstruction the verifier performs: it steps a fresh
``GameEpisode`` from the logged moves, so the board drawn is what the log
actually replays to, not what it claims. Per-turn commitment and signature
status is drawn alongside, so a forged turn is flagged in the picture rather
than laundered into a tidy one. The pause is injected, like the match clock
elsewhere here, so tests drive the renderer without sleeping.
"""

import time
from dataclasses import dataclass

from engine.game_loop import GameEpisode
from mcp_server.crypto import verify
from mcp_server.identity import verify_signature
from scripts.heatmap import EMPTY, heat_cell
from strategy.pheromones import PheromoneField

COP, THIEF, CAPTURE, BARRIER = "C", "T", "X", "#"
_MARKS = {True: "OK", False: "!!"}
_ROLES = ("police", "thief")
DEFAULT_DELAY = 0.5


@dataclass
class Frame:
    """One rendered turn: the reconstructed board plus its crypto status."""

    turn: int
    moves: dict
    intents: dict
    cop: tuple
    thief: tuple
    captured: bool
    barriers: frozenset
    scent: dict
    checks: dict




def board_lines(config, cop, thief, barriers, scent, colour=False) -> list:
    """Draw the grid. Agents outrank barriers and traces on a shared cell."""
    lines = []
    for row in range(config.grid_size):
        cells = []
        for col in range(config.grid_size):
            cell = (row, col)
            if cell == cop and cell == thief:
                cells.append(CAPTURE)
            elif cell == cop:
                cells.append(COP)
            elif cell == thief:
                cells.append(THIEF)
            elif cell in barriers:
                cells.append(BARRIER)
            else:
                cells.append(heat_cell(scent.get(cell, 0.0), colour))
        lines.append(" ".join(cells))
    return lines


def turn_checks(turn, public_keys) -> dict:
    """Re-derive one turn's commitment digest and signature, per role."""
    checks = {}
    for role, entry in turn["submissions"].items():
        signed = role in public_keys and verify_signature(
            public_keys[role], role, turn["turn"], entry["h_commit"],
            entry["signature"],
        )
        checks[role] = {
            "commitment": verify(
                entry["state"], entry["move"], entry["intent"],
                entry["nonce"], entry["h_commit"],
            ),
            "signature": bool(signed),
        }
    return checks


def _barrier_cells(config, board) -> frozenset:
    size = range(config.grid_size)
    return frozenset((r, c) for r in size for c in size if board.is_barrier((r, c)))


def replay_frames(log, config, public_keys):
    """Yield one Frame per logged turn by stepping a fresh episode."""
    episode = GameEpisode(config)
    field = PheromoneField(config)
    barriers = _barrier_cells(config, episode.board)

    for turn in log["turns"]:
        moves = {role: entry["move"] for role, entry in turn["submissions"].items()}
        result = episode.step(moves["police"], moves["thief"])
        field.advance(deposits=[result.thief_position])
        yield Frame(
            turn=turn["turn"],
            moves=moves,
            intents={r: e["intent"] for r, e in turn["submissions"].items()},
            cop=result.cop_position,
            thief=result.thief_position,
            captured=result.captured,
            barriers=barriers,
            scent=field.heatmap(),
            checks=turn_checks(turn, public_keys),
        )


def frame_lines(frame, config, colour=False) -> list:
    """Header, per-role verification status, and the board for one turn."""
    lines = [f"── Turn {frame.turn + 1} " + "─" * 30]
    for role in _ROLES:
        check = frame.checks[role]
        lines.append(
            f"  {role:<6} move={frame.moves[role]:<5}"
            f" commit={_MARKS[check['commitment']]}"
            f" signature={_MARKS[check['signature']]}"
            f"  intent={frame.intents[role]!r}"
        )
    lines.append("")
    lines.extend(f"    {line}" for line in board_lines(
        config, frame.cop, frame.thief, frame.barriers, frame.scent, colour))
    capture = "  ** CAPTURED **" if frame.captured else ""
    lines += ["", f"    cop={frame.cop}  thief={frame.thief}{capture}", ""]
    return lines


def pause_for(step: bool):
    """The between-turn pause: a keypress in step mode, otherwise a sleep."""
    return (lambda _: input("    [Enter] ")) if step else time.sleep


def render_replay(log, config, public_keys, write=print, pause=time.sleep,
                  delay=DEFAULT_DELAY, colour=False) -> None:
    """Draw every turn in order, pausing between frames."""
    write(f"legend: {COP}=cop {THIEF}=thief {CAPTURE}=capture "
          f"{BARRIER}=barrier {EMPTY}=clear 1-9=scent")
    write("")
    for frame in replay_frames(log, config, public_keys):
        for line in frame_lines(frame, config, colour):
            write(line)
        pause(delay)
