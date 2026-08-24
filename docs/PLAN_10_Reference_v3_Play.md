# PLAN 10 — Playing a sub-game on reference-v3

Derived from `PRD_10_Reference_v3_Play.md`. Approved shape before any code.

## 1. The model this phase adopts

The push dialect's loop holds ONE engine resolving TWO pieces. reference-v3
holds one peer resolving ONE piece:

```
push dialect (PRD_09)            reference-v3 (this phase)
-----------------------          --------------------------
their commit  -> store           their turn -> inbox[step]
their reveal  -> store             (commit only; no move, ever)
MatchState.submit(ours)          Side.walk(ours)      <- our piece only
MatchState.submit(theirs)        (their piece is UNKNOWN)
resolver -> captured?            capture_claim / claim_response
```

`MatchState`, `GameEpisode` and `resolve_turn` are untouched: they remain the
engine for our own authenticated dialect and for local play. Nothing in this
phase edits them, because nothing in this phase can supply their second move.

## 2. Modules

Seven small modules rather than two large ones — the 150-line limit is the
constraint, and the seams below are real rather than arithmetic.

| module | holds |
| --- | --- |
| `mcp_server/smell_trail.py` | the thief's own decaying trail, and reading theirs |
| `mcp_server/turn_message.py` | build one conformant `TurnMessage` + the sealed payload |
| `mcp_server/claims_side.py` | OUR piece: walk, smell, claim, honest answer |
| `mcp_server/turn_client.py` | outbound `receive_turn` + `submit_audit`, records buffered |
| `scripts/claims_match_loop.py` | one sub-game: push, poll, adjudicate, audit |
| `scripts/claims_runner.py` | policy/board/schedule glue for a whole series |
| `scripts/run_reference_match.py` | the live entry point |

`reference_tools.submit_audit` gains the FR8 cross-check; that is the only
edit to existing source.

## 3. One step, precisely

```
step n, our side:
  move, hint, intent  <- policy
  position            <- Side.walk(move)          # bounds/barrier -> STAY
  payload             <- {step, state, position, move, intent, hint}
  commit, nonce       <- TurnClient.seal(payload) # buffered for the audit
  message             <- {step, sender, hint, smell_grid, commit, timestamp,
                          + capture_claim | claim_response | win_claim}
  push receive_turn(message=message)
  if we just answered "caught": terminal = capture, stop
  theirs              <- poll our inbox for a turn with step == n
  Side.read(theirs)   # their claim to answer next turn, or their answer to ours
  pheromones.advance(strongest cell of their smell_grid)
  if they answered caught: terminal = capture, stop
```

## 4. Decisions, with their reasons

* **The police claims its own cell, every step.** Capture is co-location, so
  the only cell we may honestly claim is the one we are standing on. Claiming
  every step is free — the field rides on a message we send anyway.
* **The thief answers on the NEXT turn.** Their claim for step n arrives
  after we have already sent step n. Answering in step n+1 is deterministic;
  answering "in the same step if it happened to arrive first" is a race.
* **A claim on the FINAL step goes unanswered on the wire.** Both chains
  disclose `position` at `submit_audit`, so that one is settled there. Stated
  because it is the one capture this loop does not report live.
* **The thief transmits its trail; the police transmits `{}`.** The police
  has no smell to give. Assumption flagged to ali-ahm1 in PRD_10.
* **`state` uses the kit's own vector spelling**, `grid=7x7;self=[4, 3];
  barriers=[]`, so a record we seal is shaped like the records the fixture
  publishes.

## 5. Test strategy

Failing test first, every item. The scripted opponent is a fake `call` that
appends a turn to our inbox, so a whole sub-game runs with no network and no
sleeping. Assertions that matter:

* `receive_turn` is the ONLY game tool called; `receive_commit` never appears.
* the message validates against `wire_v3.validate_turn_message` — asserted
  through the real validator, not a hand-rolled copy.
* a thief that is claimed on answers `caught: true` **and the answer reaches
  the wire** before the sub-game stops.
* a thief that is claimed on the WRONG cell answers `caught: false` and play
  continues.
* the audit carries one record per step played, and re-hashes clean.
* FR8: a record whose `commit` differs from the pushed digest is reported as
  a mismatch even though it re-hashes against itself.
