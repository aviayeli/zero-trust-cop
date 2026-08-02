# zero-trust-cop

**A zero-trust, cryptographically verifiable pursuit–evasion game between two
mutually distrusting reinforcement-learning agents, played over a real wire.**

Two independent MCP peers — a cop and a thief — play a simultaneous-move
Dec-POMDP on a 7×7 grid. Neither peer trusts the other's engine, clock, or
honesty. Every move is bound by a SHA-256 commit–reveal exchange and an
Ed25519 signature before it reaches either engine, both peers maintain
independent ground truth that is cross-checked every turn, and the finished
match produces a log that a standalone verifier can replay and certify
(`Verified OK`) or reject (`TAMPERED!`) — cryptographically, not by trust.

```
seed=20260801  turns=5  terminal_reason=capture  peers_agreed=True
$ python -m scripts.replay_match logs/groupa/log_ztc001_g01.json
Verified OK
```

### Academic submission index

| Required topic | Where |
|---|---|
| Dec-POMDP model & pursuit–evasion dynamics | [§1](#1-project-overview) |
| FastMCP orchestration & wire protocol | [§4](#4-wire-protocol-and-local-p2p-simulation) |
| Strategy (Q-learning, pheromone belief, deception) | [§3](#3-reinforcement-learning-and-convergence) |
| Performance curves | [§3 — convergence](#empirical-convergence) |
| Live GUI & Replay App | [§7](#7-tkinter-gui-live-heatmap-and-replay-viewer) |
| Cross-repository links | [§0](#0-the-two-repositories) |

Two viewers ship: a Tkinter **Live Belief Heatmap** and a Tkinter **Replay
App** (§7), plus a terminal ASCII renderer (§6 step 6) for headless use.

---

## 0. The two repositories

This submission is one half of a **two-repository pair**. Each peer is an
independent process with its own config, keys and runtime; neither imports
the other, and they meet only over the authenticated wire.

| Role | Repository |
|---|---|
| **Cop / police** (this repo) | https://github.com/aviayeli/zero-trust-cop |
| **Thief / evader** — *cross-link* | **https://github.com/aviayeli/zero-trust-thief** |

> **Cross-repository link:** the evading half of this pair lives at
> **https://github.com/aviayeli/zero-trust-thief**. Both peers share one
> engine and one wire protocol; they differ in which policy they load and
> which `config/<role>/` workspace they run from.

Both URLs are declared once in each peer's `config/<role>/game.toml` under
`[game.repos]`, and are emitted into `declaration_<game_id>.json` and
`result_<game_id>.json`, so a marker holding either artifact can find the
other half of the pair.

---

## 1. Project overview

### The game

A decentralised partially observable Markov decision process (Dec-POMDP) in
the classic pursuit–evasion family:

- **Board** — 7×7 grid, shared move set `{N, S, E, W, STAY}`, up to 35
  simultaneous turns.
- **Cop** starts at `(0,0)`, **thief** at `(3,3)`. Both submit moves
  simultaneously; an illegal move (off-board or into a barrier) resolves to
  `STAY`.
- **Capture** — same cell after resolution, or a swap/cross of cells. If the
  thief survives 35 turns, the game ends in survival.
- **Scoring** (shared contract, `config/game.json`): capture pays the cop
  20 / thief 5; survival pays the cop 5 / thief 10; a technical loss pays 0.
- **Partial observability** — a peer sees its opponent's position only as of
  the last *resolved* turn, and receives a natural-language `intent` hint
  (≤ 15 words) whose honesty is never guaranteed: the cop states its true
  direction, the thief states the opposite (`STAY` maps to `STAY` — a
  deterministic deception baseline with a documented honest hole).

### Formal Dec-POMDP model

The match is the tuple $\langle n, S, \{A_i\}, P, R, \{\Omega_i\}, O, \gamma \rangle$:

| Symbol | Instantiation here |
|---|---|
| $n$ | $2$ agents — $i \in \{\text{cop}, \text{thief}\}$ |
| $S$ | $\{(c, t, B, k)\}$ — cop cell $c$, thief cell $t$ on the $7 \times 7$ grid, barrier set $B \subseteq \text{cells}$, turn index $k \le 35$ |
| $A_i$ | $\{\texttt{N}, \texttt{S}, \texttt{E}, \texttt{W}, \texttt{STAY}\}$, identical for both agents |
| $P$ | **Transition function** $P(s' \mid s, a_{\text{cop}}, a_{\text{thief}})$. **Deterministic**: each agent's intended cell is resolved independently, and an illegal target (off-board or in $B$) collapses to $\texttt{STAY}$; the turn then terminates iff the resolved cells coincide or the agents swapped. So $P(s' \mid s, \vec{a}) \in \{0, 1\}$ for every $(s, \vec{a})$ |
| $R$ | $R_{\text{cop}}$: $+20$ capture, $+5$ survival. $R_{\text{thief}}$: $+5$ capture, $+10$ survival. $0$ on technical loss. **Sparse** — paid only on the terminating transition |
| $\Omega_i$ | Own cell, the opponent's **last resolved** cell, the barrier mask of the four adjacent cells, and the opponent's committed $\langle \textit{move}, \textit{intent} \rangle$ |
| $O$ | **Observation probability** $O(o_i \mid s', \vec{a})$. **Deterministic** ($\in \{0,1\}$) and *lagging*: a peer observes the opponent's position as of the last resolved turn, never mid-turn. Honesty is not observable — $\textit{intent}$ is self-reported and may be a lie |
| $\gamma$ | $0.9$ (`discount_factor`, `config/<role>/game.toml`) |

Both $P$ and $O$ are degenerate distributions: the environment is
deterministic, and *partial observability — not stochasticity — is the entire
source of difficulty*. Neither agent can see the other's move before
committing to its own, which is exactly what the commit–reveal protocol (§2)
enforces cryptographically.

### Two grids, not one

Two $5 \times 5$-vs-$7 \times 7$ sizes are easy to conflate:

| Grid | Size | Meaning |
|---|---|---|
| **Board** | $7 \times 7$ | the playing field; what the GUI renders (49 cells) |
| **Scent kernel** | $5 \times 5$ | `pheromone_grid_size = 5` — the emission *footprint* stamped around an observed opponent, centre intensity $0.90$, decay $0.10$/turn |

The kernel is a $5 \times 5$ **stamp applied onto** the $7 \times 7$ board, not
a board of its own; it is clipped at the edges, never wrapped. Overlapping
stamps accumulate, so a cell's concentration can exceed $0.90$ (peak $2.41$
observed) — it is a concentration, not a normalised probability.

### The architecture

Four strictly layered packages. The import direction is enforced by an
AST-based test, not by convention (§5):

```
        scripts/                    mcp_server/
  (trainer, match harness,    (wire: crypto, commit book,
   log writer, verifier)       signatures, policy, tools)
            │                          │
            └───────────┬──────────────┘
                        ▼
                    agent/            policy layer: decides, learns,
                        │             observes, truncates intents
            ┌───────────┴───────────┐
            ▼                       ▼
        strategy/               engine/
  (Q-learning, pheromone    (board, resolver, episode —
   belief field, honesty     deterministic, replayable,
   tracking, settings)       imports NOTHING above it)
```

The engine never learns that `strategy` or `agent` exist. That intention is
converted into a mechanical check: a test walks every module under
`src/engine/` with Python's `ast` parser and fails on any import of a
forbidden root — including aliased, dotted, relative, and function-local
forms.

### Design lineage

The project was built in strictly documented phases, each governed by a
PRD → PLAN → TODO lifecycle under `docs/`:

| Phase | Deliverable |
|---|---|
| 1 | Deterministic game engine with replayable episodes |
| 2 | MCP server: async 2-slot move buffer under an `asyncio.Lock` |
| 3 | Security primitives: SHA-256 commit–reveal, Ed25519 identity |
| 4 | Strategy: tabular Q-learning, pheromone belief field, honesty tracker |
| 5 | Wiring + offline training: the policy layer and the 2,000-game series |
| 6 | The wire: authenticated tools, live P2P match, artifacts, verifier |

---

## 2. Zero-trust security architecture

### Threat model

Each peer assumes its opponent may lie about its state, front-run a revealed
move, replay old signatures, impersonate the other role, or silently stall.
Every one of these is closed by a specific mechanism with a specific test.

### Commit–reveal (anti-front-running)

Each turn is two-phase. Both peers first publish a **commitment**:

```
h_commit = SHA256( State || Move || Intent || Nonce )   # Rulebook 5.3
```

The payload states a **direction** and an **honesty flag** separately
(payload v3.0.0):

```
move   = 'north' | 'south' | 'east' | 'west' | 'stay'
intent = 'truth' | 'lie'
```

The engine speaks `N/S/E/W/STAY`, so the translation lives at the protocol
layer (`mcp_server/directions.py`) — `src/engine/` must never learn a wire
encoding exists, and an AST test enforces that. The honesty flag is *derived*
by comparing the policy's untruncated claim against the move it actually
plays, so it stays correct if the deception policy changes, and a small
`hint_max_words` cannot empty the hint and make an honest peer look like a
liar. The hint an opponent's belief tracker scores is reconstructed from the
pair: the move when truthful, its opposite when not.

Commitments use a 32-hex-character random nonce (`secrets.token_hex`). Only after *both*
commitments are booked may either peer **reveal** `(state, move, intent,
nonce)`. The `CommitmentBook` refuses early reveals (`reveal_before_commit`),
double commits (`already_committed`), and reveals that fail to re-derive the
committed digest (`broken_commitment`) — so a peer cannot wait to see its
opponent's move and then choose its own. Digest comparison uses
`secrets.compare_digest` to avoid timing leaks.

The `intent` is truncated to the configured `hint_max_words` **before** the
digest is computed, so the commitment covers exactly the text that is
revealed — a peer cannot commit to one hint and disclose another.

### Ed25519 identity and replay resistance

Every submission is signed over `canonical_json({role, turn, h_commit})`:

- a signature made with the wrong key → `invalid_signature`, and the
  commitment is *not* stored;
- a peer submitting under its opponent's role → `invalid_signature` (the
  claimed role must match the key that signed);
- a caller-supplied turn that disagrees with the server's authoritative
  `turn_count` → `wrong_turn`;
- a turn-N signature re-presented at turn N+1 → rejected, because the turn is
  bound inside the signed payload.

### Key isolation

```
config/<role>/signing_key.pem      # PRIVATE — gitignored, never committed
config/<role>/peers/<peer>.pub     # PUBLIC  — 32-byte raw hex, committed
```

The server needs only **public** keys (it verifies both sides of every turn),
so a clean checkout can run a peer with no secrets present. Signing is a
client concern. `mcp_server.keygen.ensure_keys()` generates any missing
keypair idempotently — an existing private key is never regenerated, since
that would silently invalidate every published public half. A pre-push audit
confirms no *parseable* private key is ever tracked.

### No unauthenticated path

The original plaintext `make_move(role, direction)` tool was **removed, not
deprecated**. A move reaches either engine only through
`submit_commitment` → `reveal_move`. A test asserts the tool is absent from
the registered surface, and a mutation that re-registers it fails the suite.

---

## 3. Reinforcement learning and convergence

### Q-learning setup

Tabular Q-learning per role (`strategy/qvalues.py`), with the exact update

```
Q(s,a) ← Q(s,a) + α · (r + γ · max_a' Q(s',a') − Q(s,a))
```

and the bootstrap term omitted on terminal transitions. The state key is
`(relative_opponent, barrier_mask)` — the opponent's position relative to the
agent's own, plus a 4-bit mask of blocked adjacent cells (off-board counts as
blocked). Turn count is deliberately excluded so states generalise across the
episode. The layout is frozen under `STATE_LAYOUT_VERSION = 1`; loading a
table with a different version raises rather than silently mislearning.

All hyperparameters live in each peer's private `config/<role>/game.toml`
`[strategy]` block — `learning_rate` 0.1, `discount_factor` 0.9,
`exploration_rate` 0.1 decayed by 0.999/game to a floor of 0.01 — never as
literals in Python. Missing keys raise `KeyError`; there are no silent
defaults.

### Sparse terminal rewards — and the arithmetic that proves them

Per the accepted Conductor ruling, **only the terminating transition pays**;
every earlier transition learns from reward 0.0. Distance shaping was
explicitly rejected. The 2,000-game training run's totals are themselves the
proof:

```
captures=1713  survivals=287
cop_total   = 1713·20 + 287·5  = 35,695   ✓ exactly
thief_total = 1713·5  + 287·10 = 11,435   ✓ exactly
```

A per-turn reward would inflate these by ~35×. (An earlier delegated
implementation paid a survival reward every turn — scores of (175, 350) per
game — and was caught and rejected by exactly this check.)

### Empirical convergence

Offline self-play, 2,000 games, seed `20260801`, ε decayed once per game.
Cop capture rate per 200-game block:

```
capture rate, by 200-game block          seed 20260801
100% ┤                    ●───●───●───●───●───●───●
     │            ●───●
 75% ┤        ●
     │
 50% ┤    ●
     │
 25% ┤
     │●
  0% ┼────┬───┬───┬───┬───┬───┬───┬───┬───┬───
     0   200 400 600 800 1k  1.2k 1.4k 1.6k 2k

games    0– 200   10.5%      games 1000–1200   99.5%
games  200– 400   53.0%      games 1200–1400  100.0%
games  400– 600   94.0%      games 1400–1600  100.0%
games  600– 800   99.5%      games 1600–1800  100.0%
games  800–1000  100.0%      games 1800–2000  100.0%
```

The committed deliverables `data/q_table_police.json` (160 entries, 147
non-zero, max value 20.0 = `capture_cop`) and `data/q_table_thief.json`
(128 entries, 121 non-zero) reproduce **byte-for-byte** from the recorded
seed; a different seed provably produces different tables.

**Honest caveats, recorded rather than glossed:** the trainer places no
barriers, so the `barrier_mask` dimension has only ever encoded board edges;
and the belief tracker's training data comes from our own deterministic
deception baseline, so it measures our generator, not an adversary. These
tables are evidence that learning ran and converged — protocol correctness is
established separately (§4).

### Match-time play is greedy

Competitive peers load their tables with
`match_exploration_rate = 0.0` (a configured value, not a literal): after
2,000 decayed games the residual training ε ≈ 0.0135 would still throw away
roughly one move in 74 to exploration.

---

## 4. Wire protocol and local P2P simulation

### Transport

Each peer is an independent **FastMCP** server on **streamable HTTP**, bound
to configured local ports. The canonical block is `[network]` in each peer's
`game.toml` — `my_port` is where that peer listens and `opponent_url` is where
it reaches the other half (police 8801, thief 8802). `public_url` carries an
ngrok/Localtonet endpoint for league play and is empty for local matches. Tool parameter names are part of
the wire contract — FastMCP derives the public JSON schema from the Python
signatures, so a rename is a protocol change and the schemas are pinned by
test. Four tools per peer:

`get_observation` · `submit_commitment` · `reveal_move` · `get_match_status`

### Mirrored local ground truth

Zero-trust means **two engines, not one**: every submission is broadcast to
*both* peers, and each advances its own `GameEpisode` independently. After
every turn the harness compares `turn_count`, both positions, `captured`, and
`is_terminated` across the two engines. A disagreement raises
`DivergenceError` naming the field — divergence detection is a feature, not
an error case to absorb. A test with a peer that deliberately lies about a
position proves the branch fires.

### Technical loss on stall (no silent hangs)

A commitment starts a deadline (`response_timeout_sec`, configured). A peer
that commits and then goes silent — or never commits at all — is detected by
`CommitmentBook.stalled_roles()`, and the match resolves immediately to
**`technical_loss`** against the non-responsive peer. Blame follows the phase
that is actually blocked: while a commitment is outstanding only the silent
committer is at fault, because reveals are refused until both commitments are
in. Further submissions to a forfeited match return `match_forfeited`. The
clock is injected everywhere; no test sleeps.

### Match artifacts

A completed series writes four deterministic (byte-reproducible) JSON
artifacts under `logs/<group_id>/`:

```
declaration_<game_id>.json      # Step-0 declaration (schema fixed by PRD_03 FR6)
config_<game_id>_g<NN>.json     # snapshot of the shared game contract
log_<game_id>_g<NN>.json        # per-turn commitments, signatures, reveals, results
result_<game_id>.json           # series outcome summary
```

The log records, per turn and per role: `h_commit`, `signature`, `state`,
`move`, `intent`, `nonce`, and the resolved outcome — everything a verifier
needs, and nothing secret.

### The replay verifier

`scripts/replay_match.py` certifies a log independently. **`Verified OK`**
requires *all three* of:

1. every commitment digest re-derives from its revealed tuple;
2. every Ed25519 signature re-verifies against that role's public key **for
   that turn**;
3. replaying the logged moves through a fresh `GameEpisode` reproduces the
   logged final state exactly.

Anything less prints **`TAMPERED!`** with the precise reason and exits
non-zero. The three checks are proven *independently* fail-able — an edited
intent breaks only the digest check, a forged signature only the signature
check, an edited result only the replay — because a tamper that trips all
three at once would hide a check that never runs. (Cross-peer log agreement
is enforced at match time by the divergence check, so a disagreeing pair
never produces an artifact.)

---

## 5. Code quality and governance

### The numbers

| Discipline | State |
|---|---|
| Test suite | **635 tests**, all passing (unit → live two-process HTTP) |
| Line limit | every one of the **135** tracked Python files ≤ **150 lines** (max: 149) |
| TDD | strict red→green: every implementation change preceded by a confirmed failing test |
| Hyperparameters | zero tunables inlined in Python — all in `config/game.json` / per-peer `game.toml` |
| Lifecycle | PRD → PLAN → TODO under `docs/`, per phase |

### Mutation testing as a review gate

Passing tests are treated as a *claim*, verified by breaking the code and
requiring the suite to notice. Across phases 5–6, **38+ targeted mutants**
were introduced and all killed, including: dense per-turn rewards, disabled
signature verification, a removed reveal-before-commit gate, `crypto.verify`
forced true, the plaintext tool re-registered, an inert divergence detector,
key regeneration, truncation applied after hashing, an always-`Verified OK`
verifier, and each verifier check skipped in turn.

The standard exists because it caught real failures: a delegated
implementation once shipped an MCP-import guard built on `find_module` — a
protocol removed in Python 3.12, so the guard passed while enforcing
*nothing*. Every guard since is required to be **provably able to fail**, and
several tests exist purely to prove another test's teeth
(`test_the_guard_itself_can_fail`, the zero-word truncation cap, the
lying-peer divergence test).

### Architectural guards that cannot decay

- **Import direction** — an AST walk over every `src/engine/` module fails on
  any import of `strategy` or `agent`. Modules are globbed, not listed, so
  new files are covered automatically; a discovery assertion fails loudly if
  the glob goes empty rather than passing vacuously.
- **No MCP in the trainer** — the offline trainer runs in a subprocess with a
  `find_spec` meta-path blocker that raises on any `mcp*` import, then scans
  `sys.modules` after a full training series, catching deferred imports.
- **Declaration/transport agreement** — the published Step-0 declaration is
  pinned by test against the ports the peers actually bind (this caught a
  live swapped-endpoint defect).
- **Artifact purity** — test runs provably never write to `data/` (fingerprint
  comparison, not name listing) and never touch production key material.

---

## 6. Execution and verification guide

### Prerequisites

Python ≥ 3.12. Dependencies are locked in `uv.lock`
(`cryptography`, `mcp`; dev: `pytest`):

```bash
uv sync          # or: python -m venv .venv && .venv/bin/pip install -e . pytest
```

All commands below run from the repository root. `pythonpath = ["src"]` is
configured for pytest; standalone scripts take `PYTHONPATH=src`.

### 1 — Run the full test suite

```bash
.venv/bin/python -m pytest -q
# expected: 635 passed
```

(Includes the live-transport tests: they spawn both peer processes on
127.0.0.1:8801/8802 against an isolated temporary config root.)

### 2 — Train the agents offline (reproduces `data/q_table_*.json`)

```bash
PYTHONPATH=src .venv/bin/python -m scripts.run_tournament --seed 20260801
# seed=20260801  games=2000  captures=1713  survivals=287
# cop_total=35695  thief_total=11435
```

Re-running with the same seed reproduces both tables byte-for-byte
(`sha256sum data/q_table_*.json` before and after to confirm).

### 3 — Generate peer keypairs (fresh checkout only)

```bash
PYTHONPATH=src .venv/bin/python -c "from mcp_server.keygen import ensure_keys; print(ensure_keys())"
# ['police', 'thief'] on first run; [] (idempotent no-op) thereafter
```

The match harness also does this automatically at startup.

### 4 — Play a live P2P match and write the artifacts

```bash
PYTHONPATH=src .venv/bin/python -m scripts.run_local_mcp_match \
    --seed 20260801 --game-id ztc001 --game-number 1
# seed=20260801  turns=5  terminal_reason=capture  peers_agreed=True
# → logs/groupa/{declaration_ztc001,config_ztc001_g01,log_ztc001_g01,result_ztc001}.json
```

This spawns both peer servers over streamable HTTP, plays the full
commit→commit→reveal→reveal protocol to termination with signatures in
force, cross-checks both engines every turn, and tears the processes down
even on failure.

### 5 — Verify the match log cryptographically

```bash
PYTHONPATH=src .venv/bin/python -m scripts.replay_match \
    logs/groupa/log_ztc001_g01.json --own-role police
# Verified OK          (exit 0)
```

To see it refuse a forgery, edit any `intent`, `move`, `signature`, or result
field in a *copy* of the log and re-run — it prints `TAMPERED!` with the
exact turn and reason, and exits 1.

### 6 — Watch the replay on the terminal grid (`--render`)

| Flag | Effect |
|---|---|
| `--render` | draw each turn on an ASCII board before reporting the verdict |
| `--render-delay N` | seconds between turns (default `0.5`; `0` renders instantly) |
| `--step` | wait for **Enter** between turns instead of pausing |

On a terminal the belief heatmap shades cells in red intensity proportional
to pheromone concentration, and the verdict prints as a green `Verified OK`
or red `TAMPERED!` badge. Piped or redirected output stays byte-clean.

```bash
PYTHONPATH=src .venv/bin/python -m scripts.replay_match \
    logs/groupa/log_ztc001_g01.json --render --render-delay 0.5
```

```
legend: C=cop T=thief X=capture #=barrier .=clear 1-9=scent

── Turn 3 ──────────────────────────────
  police move=E     commit=OK signature=OK  intent='east'
  thief  move=N     commit=OK signature=OK  intent='south'

    . C 8 T 8 3 .
    . 3 9 9 9 3 .
    . 3 7 9 7 3 .
    . . 3 7 3 . .
    . . . 3 . . .
    . . . . . . .
    . . . . . . .

    cop=(0, 1)  thief=(0, 3)

… Turn 5 …

    3 9 X 9 9 5 .
    . 5 9 9 9 2 .
    . 2 9 9 6 2 .

    cop=(0, 2)  thief=(0, 2)  ** CAPTURED **

Verified OK
```

Scent levels `1`–`9` come from the real `PheromoneField`, so the thief's
trail visibly thickens and decays as the match runs. Two properties become
legible that plain output hides: the thief's **deception** (`move=N` while
`intent='south'` — always inverted, §1), and per-turn tampering, flagged in
place rather than only in the summary:

```
  thief  move=N     commit=OK signature=!!  intent='south'
...
TAMPERED!
  - turn 2 thief: signature invalid          (exit 1)
```

The renderer steps a **fresh `GameEpisode` from the logged moves** rather than
reading the recorded positions — a view that echoed the file would draw a
forged match exactly as its author intended. Two tests falsify a recorded
position while leaving the moves genuine to hold that line.

Rendering is purely additive: without `--render` the tool is byte-for-byte
the same fast cryptographic check (~0.06 s), pinned by test.

---

## 7. Tkinter GUI: live heatmap and replay viewer

```bash
# Live belief heatmap — auto-advances, red intensity ∝ pheromone concentration
PYTHONPATH=src .venv/bin/python -m gui.live_heatmap logs/groupa/log_ztc001_g01.json

# Replay viewer — steps turn by turn, stamps the verdict badge
PYTHONPATH=src .venv/bin/python -m gui.replay logs/groupa/log_ztc001_g01.json
```

**Live Belief Heatmap** — renders the $7 \times 7$ **board** (49 cells); the
$5 \times 5$ figure in the spec is the *scent kernel* stamped onto it, not the
display size (see §1, "Two grids, not one"). Every cell is shaded red in
proportion to that cell's pheromone concentration, which decays each turn, so the thief's trail
builds and fades as the match runs. The field is a *concentration*, not a
normalised probability (overlapping kernels reach 2.41 on a real match), so
the shading clamps rather than claiming a probability it does not compute.

**Replay Viewer** — a green `Verified OK` badge on a clean log, a red
`TAMPERED!` banner on an altered one. The badge is driven by the *same*
`verify_log` the headless CLI uses, so the window cannot disagree with
`scripts.replay_match`, and frames are replayed from the logged **moves**
rather than the recorded positions — a forged log is drawn as it truly
reconstructs.

Canvas exports of all three states are committed under
[`docs/screenshots/`](docs/screenshots): `replay_verified_ok.eps`,
`replay_tampered.eps`, `live_belief_heatmap.eps`. They are **EPS, not PNG**:
this build environment has neither Pillow nor ImageMagick, so no raster
capture was possible. Run either command above to see the windows live.

---

## 8. End-of-series reporting (Rulebook 9.3)

After the artifacts are written, the harness reports the series:

```bash
PYTHONPATH=src .venv/bin/python -m scripts.run_local_mcp_match \
    --seed 20260801 --game-id ztc001 --game-number 1
# … result=logs/groupa/result_ztc001.json
# email_report=ok mode=auto
```

Recipient and mode come from each peer's private `[email]` block
(`config/<role>/game.toml`): `auto` sends when OAuth credentials exist and
drafts otherwise, `draft` never contacts Google, and `send` **requires** a
real delivery and reports failure rather than quietly drafting.

**Mutual agreement is a precondition, not a label.** A result is reported only
when `mutual_agreement.confirmed` is literally `true`, and that flag is
written only after both peers' independent engines agreed on every turn
(§4). Reporting an unagreed result would launder a divergence into a
submission, so `send_game_report` refuses and returns `False`.

**Graceful fallback.** The Google client libraries are an *optional*
dependency, imported inside the send path so the suite collects on a machine
that has never installed them. With no `token.json` the reporter writes a
readable draft under `logs/` and returns `True`, so CI never breaks — and the
draft records exactly why nothing was sent:

```
# not sent: ModuleNotFoundError: No module named 'googleapiclient'
To: rmisegal+uoh26finalgame@gmail.com
Subject: [zero-trust] match report ztc001
```

Scope is `gmail.send` only — a reporter has no business holding read access.
`token.json` and `credentials.json` are gitignored alongside the Ed25519
keys.

> **Honest limitation:** no message has ever been delivered from this
> environment. The Google libraries are not installed and no OAuth token
> exists, so every run to date has taken the draft path. The send path is
> exercised only by mocked tests.

---

## Repository layout

```
config/               shared game.json (Step-0 contract) + per-peer private
                      game.toml, public keys under <role>/peers/
data/                 trained Q-tables (committed, seed-reproducible)
docs/                 PRD / PLAN / TODO lifecycle documents, per phase
logs/<group_id>/      match artifacts (submission evidence, replay-verified)
src/engine/           deterministic game core — imports nothing above it
src/strategy/         Q-learning, pheromones, belief, private settings
src/agent/            the policy layer consuming both
src/mcp_server/       crypto, identity, commitment book, gate, tools, server
src/scripts/          trainer, match harness, log writer, replay verifier
scripts/              ops tooling: sync_repos.sh, thief_readme.py
tests/                79 test modules mirroring the source layout
```

## Known limitations (stated, not hidden)

- **The Q-tables cover ~2% of the representable state space.** Measured, not
  estimated: the police table holds 68 distinct states and the thief 46, out
  of the 2,704 that `(relative_opponent, barrier_mask)` can express on a 7×7
  board — **2.51%** and **1.70%** respectively. Only 14/68 and 13/46 of those
  states have all five actions valued. In an unseen state `best_action` falls
  back to `move_set[0]` (`N`) by tie order, and with match-time ε = 0 there is
  no exploration to escape it, so an opponent that steers play off the trained
  manifold meets a fixed-direction agent.

  This is characteristic of tabular Q-learning under **deterministic
  self-play**: once the cop wins reliably the trajectory distribution
  collapses, the same states are revisited, and exploration stops discovering
  new ones. The 100% capture rate in §3 should therefore be read as
  convergence *against this specific thief on this trajectory manifold*, not
  as general competence. Broadening it needs opponent diversity (randomised
  or pooled policies) or a function approximator — a training phase in its own
  right, not a tuning change.
- **Barriers are never placed.** `max_barriers: 14` is config-driven but the
  engine never populates the board, so both training and matches run on a
  bare grid; the Q-tables have never seen an interior barrier. This is also
  why the `barrier_mask` half of the state key only ever encodes board edges.
- **The thief's deception is deterministic** and therefore predictable — a
  belief tracker drives its honesty score to 0 and inverts it. It is the
  specified baseline, not a strong strategy.
- **A match log is reproducible in trajectory, not byte-for-byte.** Re-running
  a seeded match reproduces every move and every per-turn result exactly
  (verified by diffing the regenerated artifact), but the commitment nonces
  come from `secrets.token_hex` and are deliberately unseedable — a
  predictable nonce would let an opponent brute-force a commitment over the
  five-element move set and destroy the anti-front-running property. So
  digests and signatures differ between runs by design. The Q-tables, which
  carry no nonces, *are* byte-reproducible from their seed.
- **Peers bind loopback by default.** `host = "127.0.0.1"` in each peer's
  `[transport]` block keeps a local match off the network. For a live remote
  match through a tunnel (ngrok, Localtonet), set `host = "0.0.0.0"` in that
  peer's `config/<role>/game.toml` and point the tunnel at its port. This is
  a deliberate opt-in: the wire is authenticated but not encrypted, so
  exposing a peer publicly is a decision, not a default.
- **Local simulation ≠ interop.** A passing local match proves our two peers
  agree with each other, not that either matches an external group's schema
  reading. The `config_*`/`log_*`/`result_*` artifact field layouts are this
  project's design pending reconciliation with the course appendix
  (`declaration_*` follows the fixed PRD_03 FR6 schema).

---

*Built under Dr. Segal's course constraints: strict TDD, ≤150 lines per
Python file, no hardcoded hyperparameters, and a documented
PRD → PLAN → TODO lifecycle for every phase.*
