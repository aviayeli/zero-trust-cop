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
seed=20260801  turns=3  terminal_reason=capture  peers_agreed=True
$ python -m scripts.replay_match logs/aviayeli/log_aviayeli_g01.json
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
| $R$ | $R_{\text{cop}}$: $+20$ capture, $+5$ survival. $R_{\text{thief}}$: $+5$ capture, $+10$ survival. $0$ on technical loss — paid only on the terminating transition. Two much smaller shaping terms ride on top: $-1.0$ for a move a wall refused, $-0.01$ per non-capture turn (§3) |
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

### Terminal-dominated rewards — and the arithmetic that proves them

**Only the terminating transition pays the engine's payoff**; a per-turn
*survival* reward remains rejected, as does distance shaping. The 2,000-game
training run's totals are themselves the proof, because the reported GAME
SCORE is the payoff alone:

```
captures=1994  survivals=6
cop_total   = 1994·20 + 6·5  = 39,910   ✓ exactly
thief_total = 1994·5  + 6·10 = 10,030   ✓ exactly
```

A per-turn reward would inflate these by ~35×. (An earlier delegated
implementation paid a survival reward every turn — scores of (175, 350) per
game — and was caught and rejected by exactly this check.)

**What the learner additionally sees, and why.** Terminal-*only* rewards were
degenerate: bumping the north wall and advancing toward the opponent were both
worth exactly 0.0, so nothing separated a pursuing policy from one grinding
into a boundary — and the shipped policy was in fact stuck on "always N", with
three of five turns in the old flagship log spent immovable on row 0. Two
configured terms in each peer's private `[strategy]` block close that gap:
`invalid_move_penalty = -1.0` when a non-`STAY` move leaves the agent where it
started, and `step_cost = -0.01` on every turn that is not a capture. Both are
orders of magnitude below the payoff matrix — a whole 35-move match of
`step_cost` is $-0.35$ against a capture worth 20 — so the terminal signal
still dominates, and neither term looks at the opponent. They steer learning
only: the score above is untouched by them
(`tests/scripts/test_shaped_rewards.py`, `test_shaping_terms.py`).

### Empirical convergence

Offline self-play, 2,000 games, seed `20260801`, ε decayed once per game.

| Benchmarked result | Value |
|---|---|
| Cop captures across the training series | **1,994 of 2,000 games — 99.7%** |
| Capture rate, first 200 games | **97.5%** (legacy terminal-only signal: 10.5%) |
| Capture rate, games 200–1,800 | **100.0%** in every block |
| Games the thief survived to the move limit | 6 |

Cop capture rate per 200-game block:

```
capture rate, by 200-game block          seed 20260801
100% ┤    ●───●───●───●───●───●───●───●───●
     │●                                    ╲●
 75% ┤
     │
 50% ┤
     │
 25% ┤
     │
  0% ┼────┬───┬───┬───┬───┬───┬───┬───┬───┬───
     0   200 400 600 800 1k  1.2k 1.4k 1.6k 2k

games    0– 200   97.5%      games 1000–1200  100.0%
games  200– 400  100.0%      games 1200–1400  100.0%
games  400– 600  100.0%      games 1400–1600  100.0%
games  600– 800  100.0%      games 1600–1800  100.0%
games  800–1000  100.0%      games 1800–2000   99.5%
```

Convergence is now effectively immediate — 97.5% in the first block against
10.5% under the old terminal-only signal — because the shaping terms above
make a refused move cost something the moment it is tried, rather than
leaving the learner to discover it from a payoff 35 turns away. Under the
legacy signal the series needed roughly 800 games to reach the rate the
shaped run reaches inside its first block.

The committed deliverables `data/q_table_police.json` (508 entries, all
non-zero, max value 19.99 → `capture_cop` discounted by the living penalty)
and `data/q_table_thief.json` (391 entries, all non-zero) reproduce
**byte-for-byte** from the recorded seed; a different seed provably produces
different tables. The tables are ~3× larger than the terminal-only ones for a
good reason: a policy that stops wall-bumping actually visits the board, so
many more states are reached often enough to carry a value.

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
it reaches the other half (**police/cop 8802, thief 8801**). `config/declaration.json`
advertises the same pair, and a test pins the declaration to the binding so the
two cannot drift apart. `public_url` carries an ngrok/Localtonet endpoint for
league play and is empty for local matches; it is *validated* at config load
(`mcp_server.tunnel.parse_public_url`) rather than passed through, because
nothing local ever dials it — a malformed endpoint would otherwise surface only
as the opposing group failing to reach us mid-series. http/https with a host is
accepted and normalised; a bare host, a scheme-relative `//host`, and ngrok's
`tcp://` forwarder are rejected. Tool parameter names are part of
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
| Test suite | **757 tests**, all passing (unit → live two-process HTTP) |
| Line limit | every one of the **155** tracked Python files ≤ **150 lines** (max: 149) |
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
# expected: 757 passed
```

(Includes the live-transport tests: they spawn both peer processes on
127.0.0.1:8802/8801 against an isolated temporary config root.)

### 2 — Train the agents offline (reproduces `data/q_table_*.json`)

```bash
PYTHONPATH=src .venv/bin/python -m scripts.run_tournament --seed 20260801
# seed=20260801  games=2000  captures=1994  survivals=6
# cop_total=39910  thief_total=10030
```

Re-running with the same seed reproduces both tables byte-for-byte
(`sha256sum data/q_table_*.json` before and after to confirm).

To probe those same tables from starts they never trained on — the benchmark
`docs/PLAN.md` §10.10 publishes:

```bash
PYTHONPATH=src .venv/bin/python -m scripts.benchmark_offmanifold
# | qtable-only       | trained | 42.0% | 4.65 | 63.6% |
# | qtable-primary    | trained | 69.2% | 9.83 | 47.4% |
# | manhattan-primary | trained | 84.8% | 9.74 | 43.5% |
# | heuristic         | trained | 98.2% | 11.00 | 100.0% |
```

Sample size, seed and opponent set come from `config/benchmark.json`;
`tests/scripts/test_benchmark_plan_claims.py` re-derives every figure §10.10
quotes, so the documented numbers cannot drift from the shipped tables.

### 3 — Generate peer keypairs (fresh checkout only)

```bash
PYTHONPATH=src .venv/bin/python -c "from mcp_server.keygen import ensure_keys; print(ensure_keys())"
# ['police', 'thief'] on first run; [] (idempotent no-op) thereafter
```

The match harness also does this automatically at startup.

> ⚠️ **Note on fresh checkouts.** If you run `ensure_keys` on a clean clone
> without the corresponding private `.pem` files, the tool prints a warning and
> **skips overwriting the shipped public key (`.pub`) files**. This safeguard is
> intentional: those public halves are the keys the flagship tournament log
> (`log_aviayeli_g01.json`) was signed under, and republishing them would turn a
> genuine log into a `TAMPERED!` verdict. No further action is required to
> **verify** the shipped log — it is cryptographically sealed and passes step 5
> out of the box:
>
> ```
> ⚠️ Shipped public key exists but private key is missing (clean checkout). Skipping key generation to protect log signature integrity.
>    Restore signing_key.pem to play live, or delete the shipped config/*/peers/*.pub files to publish a fresh set.
> ```
>
> The trade-off is stated rather than hidden (`PLAN.md` §10.8): on such a
> checkout the freshly generated private key does *not* match the published
> public one, so **playing a new live match** (step 4) is signature-rejected
> until you either restore the original `signing_key.pem` or delete
> `config/*/peers/*.pub` to publish a fresh, self-consistent set. Verifying the
> shipped evidence is treated as outranking live play on a clone.

### 4 — Play a live P2P match and write the artifacts

```bash
PYTHONPATH=src .venv/bin/python -m scripts.run_local_mcp_match \
    --seed 20260801 --game-id aviayeli --game-number 1
# seed=20260801  turns=3  terminal_reason=capture  peers_agreed=True
# → logs/aviayeli/{declaration_aviayeli,config_aviayeli_g01,log_aviayeli_g01,result_aviayeli}.json
```

This spawns both peer servers over streamable HTTP, plays the full
commit→commit→reveal→reveal protocol to termination with signatures in
force, cross-checks both engines every turn, and tears the processes down
even on failure.

**Reporting runs automatically at the end, and cannot halt the run.** Both
peers ship `mode = "auto"` in their `[email]` block, so on an examiner's
machine the harness *attempts* a real submission to the course inbox and
degrades gracefully when it cannot:

| On the examiner's machine | What happens |
|---|---|
| Google credentials present (`token.json`) | the multipart report is really sent; the run prints `email_report=ok mode=auto` |
| Credentials absent, or `googleapiclient` not installed | no send, no crash — a readable draft is written to `logs/email_draft_<game_uid>.txt` and the run still prints `email_report=ok mode=auto` |

Either way the on-disk evidence is identical and is written **before** the
reporter is reached: the four artifacts above, including
`logs/<group_id>/result_<game_id>.json`, are produced by the artifact writer
and do not depend on email succeeding. The draft additionally embeds the
decoded result, so the fallback is complete evidence rather than a stub. §8
covers the mechanics.

### 5 — Verify the match log cryptographically

```bash
PYTHONPATH=src .venv/bin/python -m scripts.replay_match \
    logs/aviayeli/log_aviayeli_g01.json --own-role police
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
    logs/aviayeli/log_aviayeli_g01.json --render --render-delay 0.5
```

```
legend: C=cop T=thief X=capture #=barrier .=clear 1-9=scent

── Turn 1 ──────────────────────────────
  police move=MOVE:E commit=OK signature=OK  intent='truth'
  thief  move=MOVE:N commit=OK signature=OK  intent='lie'

    . C . 3 . . .
    . . 3 6 3 . .
    . 3 6 T 6 3 .
    . . 3 6 3 . .
    . . . 3 . . .
    . . . . . . .
    . . . . . . .

    cop=(0, 1)  thief=(2, 3)

… Turn 2 …

    cop=(1, 1)  thief=(2, 2)

── Turn 3 ──────────────────────────────
  police move=MOVE:E commit=OK signature=OK  intent='truth'
  thief  move=MOVE:N commit=OK signature=OK  intent='lie'

    . 3 8 5 . . .
    3 8 X 9 5 . .
    3 9 9 9 7 3 .
    . 3 9 7 3 . .
    . . 3 3 . . .
    . . . . . . .
    . . . . . . .

    cop=(1, 2)  thief=(1, 2)  ** CAPTURED **

Verified OK
```

Scent levels `1`–`9` come from the real `PheromoneField`, so the thief's
trail visibly thickens and decays as the match runs. This is also where the
field's role is easiest to see: the replay REBUILDS it from the signed log to
draw the heatmap — during the live match itself, every turn carried a revealed
coordinate and the field was never consulted (PLAN §4.1).

Two properties become legible that plain output hides: the thief's
**deception**, and per-turn tampering. The wire carries an honesty FLAG rather
than a direction word, so the thief's `intent='lie'` above is the deception
made explicit — its stated intent inverts its move by design (§1). Tampering
is flagged in place rather than only in the summary:

```
  thief  move=MOVE:N commit=OK signature=!!  intent='lie'
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
PYTHONPATH=src .venv/bin/python -m gui.live_heatmap logs/aviayeli/log_aviayeli_g01.json

# Replay viewer — steps turn by turn, stamps the verdict badge
PYTHONPATH=src .venv/bin/python -m gui.replay logs/aviayeli/log_aviayeli_g01.json
```

**Live Belief Heatmap** — renders the $7 \times 7$ **board** (49 cells); the
$5 \times 5$ figure in the spec is the *scent kernel* stamped onto it, not the
display size (see §1, "Two grids, not one"). Every cell is shaded red in
proportion to that cell's pheromone concentration, which decays each turn, so the thief's trail
builds and fades as the match runs. The field is a *concentration*, not a
normalised probability (overlapping kernels reach 2.41 on a real match), so
the shading clamps rather than claiming a probability it does not compute.

**Decay rate.** Both constants are configured in `config/game.json`, never
inlined: `pheromone_center_intensity = 0.9` at the observed cell and
`pheromone_decay` ρ = `0.10` per turn. The recurrence is *geometric* —
$\tau(t{+}1) = \max(0,\ (1-\rho)\,\tau(t) + \delta)$ — so a lone 0.9 deposit
retains $0.9 \times 0.9^{10} = 0.314$ after ten turns, drops below 0.01 at
turn 43, and is only retired at turn 268 by the field's 12-digit rounding. It
fades; it does not expire inside a 35-move match. Read ρ = 0.10 as "loses a
tenth of what remains each turn", not "gone in ten turns" — the latter would
describe *subtractive* decay, which is a different model and not the one
implemented here.

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
    --seed 20260801 --game-id aviayeli --game-number 1
# … result=logs/aviayeli/result_aviayeli.json
# email_report=ok mode=auto
```

Recipient and mode come from each peer's private `[email]` block
(`config/<role>/game.toml`): `auto` sends when OAuth credentials exist and
drafts otherwise, `draft` never contacts Google, and `send` **requires** a
real delivery and reports failure rather than quietly drafting.

**Both peers ship `mode = "auto"`, and that is the only mode that survives an
examiner's machine.** `send` would fail the run wherever no OAuth token
exists — it reports failure rather than drafting — and `draft` would never
attempt the real submission the rulebook asks for. `auto` does both: attempt,
then fall back to on-disk evidence. The shipped recipient
(`rmisegal+uoh26finalgame@gmail.com`) and mode are held in place by
`tests/unit/test_shipped_email_config.py`, so neither can drift back before a
graded run.

**Mutual agreement is a precondition, not a label.** A result is reported only
when `mutual_agreement.confirmed` is literally `true`, and that flag is
written only after both peers' independent engines agreed on every turn
(§4). Reporting an unagreed result would launder a divergence into a
submission, so `send_game_report` refuses and returns `False`.

**The result is an attachment, never body text** (Rulebook 34 / §9.3.3). The
message is `multipart/mixed`: a short summary body, plus the result as a
base64-encoded `application/json` part filed under the same name it has on
disk, `result_<game_uid>.json`. Body text is not merely discouraged — the body
is asserted brace-free by test, so a serialised result cannot creep back in
"for readability". A body would also be reflowed and line-wrapped in transit;
the attachment arrives byte-identical to the artifact both peers agreed on.

**Graceful fallback.** The Google client libraries are an *optional*
dependency, imported inside the send path so the suite collects on a machine
that has never installed them. With no `token.json` the reporter writes a
readable draft under `logs/` and returns `True`, so CI never breaks — and the
draft records exactly why nothing was sent. The draft carries the summary
*and* the decoded attachment, so it stays complete evidence even though the
body no longer holds the report:

```
# not sent: ModuleNotFoundError: No module named 'googleapiclient'
To: rmisegal+uoh26finalgame@gmail.com
Subject: [zero-trust] match report aviayeli

zero-trust match report for game_uid=aviayeli
…
The full result is attached as result_aviayeli.json (application/json).

{ …the attached payload, decoded… }
```

Scope is `gmail.send` only — a reporter has no business holding read access.
`token.json` and `credentials.json` are gitignored alongside the Ed25519
keys.

> **Delivery status:** the send path has been exercised for real. With
> `token.json` present and `mode = "auto"`, the harness run of 2026-08-11 that
> regenerated the flagship log delivered the multipart report —
> `result_aviayeli.json` attached as `application/json` — to
> `rmisegal+uoh26finalgame@gmail.com`, the address configured in
> `config/<role>/game.toml`, and printed `email_report=ok mode=auto`. The draft
> path remains the fallback and is what runs wherever no OAuth token exists;
> the *failure* branches are still exercised only by mocked tests, since
> provoking a real Gmail rejection is not something CI can do.

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
src/scripts/          trainer, match harness, log writer, replay verifier, probe
scripts/              ops tooling: sync_repos.sh, thief_readme.py
tests/                86 test modules mirroring the source layout
```

## Known limitations (stated, not hidden)

- **The Q-tables cover ~6% of the representable state space.** Measured, not
  estimated: the police table holds 177 distinct states and the thief 144,
  out of the 2,704 that `(relative_opponent, barrier_mask)` can express on a
  7×7 board — **6.55%** and **5.33%** respectively. Only 40/177 and 32/144 of
  those states have all five actions valued. (Coverage roughly tripled when
  the shaping terms stopped the policies wall-bumping: an agent that moves
  visits more of the board. It is still a small fraction.) An unseen state used
  to fall through `best_action`'s tie order to `move_set[0]` (`N`) — with
  match-time ε = 0 and no exploration to escape it, an opponent that steered
  play off the trained manifold met a fixed-direction agent. Such states are
  **58.2%** of decisions from random starts, so this was the dominant regime,
  not an edge case. The shipped cop now runs `policy_mode = "manhattan_primary"`:
  the Manhattan distance rule narrows each turn to the distance-optimal legal
  moves and the trained table ranks what is left, so both strategies stay live
  on every decision. That lifts cop capture rate to **100.0%** against a random
  thief and **84.8%** against the trained one, from 71.0% / 42.0% for the table
  alone. It still trails the **98.2%** of the same rule with an EMPTY table —
  the learned values cost 13.5 points as a tie-breaker, which is recorded
  rather than argued away. Against a *greedy* evader all four score 0.0%: one
  pursuer cannot corner a perfect evader on a bare grid. Full protocol, the
  four-policy table and the shipped-log provenance note are in `docs/PLAN.md`
  §10.10.

  This is characteristic of tabular Q-learning under **deterministic
  self-play**: once the cop wins reliably the trajectory distribution
  collapses, the same states are revisited, and exploration stops discovering
  new ones. The 99.7% series capture rate in §3 should therefore be read as
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
