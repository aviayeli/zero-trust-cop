# Supreme Multi-Model Consensus Audit

*Generated 2026-08-18 23:34 IDT by `scripts/multi-model-debate.py`.*

> Every previous audit in this repository was ONE model playing four
> specialists. This one is not: each panellist below runs on different
> weights, so a disagreement is evidence rather than a rhetorical device.

**Question.** Analyze our pursuit agent's Transfer Gap on unseen layouts, state representation, and overall system security.

## Panel

| Role | Model | Status |
| :--- | :--- | :--- |
| Compliancer | `ollama/deepseek-r1:1.5b` | READY |
| Trust-Engine | `claude/cli` | READY |
| Strategist | `gemini/gemini-3.6-flash` | READY |
| QA | `ollama/qwen:latest` | READY |
| Aggregator | `claude/cli` | READY |

## Consensus report

## Consensus

Held by both substantive participants (Trust-Engine, Strategist) and uncontested by the end of the transcript:

1. **No positive transfer is measured off trained layouts.** §10.10: 60.6 vs 50.7 on trained (+9.9), 55.1 vs 57.4 off them (−2.2), n=8 per arm. Both models ended up treating −2.2 as inside sampling error rather than a demonstrated regression. Strategist's Round 1 framing ("performance drops," "fails to generalise") was retracted by Round 3.
2. **The non-learned Manhattan distance rule is the load-bearing component off-manifold**, not the Q-table. Neither model disputes this, only *why*.
3. **Tabular representation cannot generalise across layouts.** Function approximation is the named remedy (Strategist), never contested.
4. **`game_id` is missing from the signed payload.** §3 signs `canonical_json({role, turn, h_commit})` only; turn-binding blocks intra-match replay but a turn-N signature replays into the next game of a series. Trust-Engine adds that `game_uid` already exists in §7.1 artifacts and simply isn't in the signed message.
5. **The Step-0 declaration is provenance, not proof.** §5/§10.1: signing would establish authorship, not that a peer runs the commit it declares. §10.1 is not closable by crypto alone. Strategist's Round 1 "wrap it in the signed commit schema" recommendation was withdrawn.
6. **`mutual_agreement.confirmed` is unvalidated.** It rests on `play_match` comparing two engines spawned locally (§2); against a remote group, divergence detection depends on the opponent honestly running its own engine, and §10.7 records no cross-group match.
7. **The `strongest()` scent collapse costs nothing in live play** (§10.4 — the field is never consulted or deposited into in a P2P match). Strategist raised it as a representational loss in Round 1 and conceded it moot by Round 3.
8. **Open security items, raised and uncontested:** delimiter-free positional commit digest (§10.2), no wire confidentiality (§10.6).
9. **Compliancer and QA contributed no auditable findings.** Both substantive models stated this explicitly; Trust-Engine specifically ruled that QA must not be counted as a concurring vote.

## Disagreement

**1. The transfer mechanism — the central unresolved question.** This is a position *swap*, not a convergence.

- **Round 1** — Strategist: the table "becomes inert" because `barrier_mask` ties Q-values to specific spatial configurations, so unseen layouts fall through to Manhattan. Trust-Engine: this is wrong — `barrier_mask` is 4 bits of *local* N/S/W/E adjacency (§4.2), 16 values total, layout-agnostic; a new seed yields the same 16 masks, so off-manifold states are **hit with miscalibrated values, not missed**.
- **Round 2** — the two exchange positions. Trust-Engine writes "Agree with Strategist… means an unseen layout misses every entry… inert, not worse." Strategist writes "Agree with Trust-Engine… unseen layouts do *not* miss entries by construction… miscalibrated Q-values from other layouts."
- **Round 3** — they swap again. Trust-Engine: the §10.10 sentence is "structurally false" and should be **deleted, not softened**; −2.2 is weak evidence of misranking within sampling error. Strategist: "unseen `barrier_mask` keys miss the Q-table, falling back to deterministic Manhattan rules by design. The table is inert, not corrupting."

Each model has, at some point, argued and abandoned both sides. **Nothing was resolved.**

**2. Whether `manhattan_primary` neutralises bad Q-hits.**
- *Strategist (R2):* yes — the policy constrains actions to the distance-optimal set *before* consulting table values, so the Manhattan heuristic is the true transfer engine and neutralises miscalibration.
- *Trust-Engine (R3):* it *bounds* exposure but does not neutralise it — the residual channel is exactly the tie among distance-equal steps, i.e. cul-de-sac selection, which is what barriers exist to create (§4.3). Further: the **thief ships `qtable_primary`** (§10.10), so no distance filter runs first and miscalibration is unbounded there; the layout-transfer table measures the cop only.

**3. Overall security posture.**
- *Strategist (R1):* simultaneity and state integrity are "solidly protected" via Ed25519, SHA-256 commit-reveal lockstep, and dual-engine `DivergenceError`; the remaining items are strategic risks.
- *Trust-Engine (R1–R3):* four compounding gaps (unsigned declaration, no confidentiality, delimiter-free digest, no cross-group match) plus a divergence-detection control that is unvalidated against any real peer.

**4. Severity of the tabular bottleneck.**
- *Strategist (R3):* Trust-Engine underestimates it — exact-match keying caps layout generalisability at zero, forcing total reliance on the non-learned fallback.
- *Trust-Engine:* frames it primarily as a **documentation-falsity** problem (a safety claim in §10.10 that isn't earned), not solely a capability ceiling.

**5. Whether Step-0 is already an enforcement layer.**
- *Compliancer (R2):* the declaration is a proof layer that enforces constraints and applies penalties on violation, hardened by Ed25519.
- *Trust-Engine (R3) and Strategist (R3):* explicitly rejected — §5/§10.1 state it is unsigned and unenforced, "provenance and good faith, not proof of fairness."

## Unique Findings

**Trust-Engine only:**
- 37.2% of decision states unvisited — independent corroboration that the distance rule, not the table, drives behaviour.
- n=8 undercuts the **+9.9** as much as the −2.2; the trained-layout gain is equally unresolved. No other model questioned the positive number.
- The thief ships `qtable_primary`, so the layout-transfer experiment characterises the cop only and says nothing about the thief's off-manifold exposure.
- The residual miscalibration channel is specifically tie-breaking among distance-equal moves (§4.3).
- `game_uid` already exists in §7.1 artifacts — the replay fix is a schema change, not new infrastructure.
- Signing cannot close §10.1 even in principle: signatures prove authorship, not that the declared commit is the one executing.
- Step-0 precedes turn 0, so it cannot ride the existing commit signature schema.

**Strategist only:**
- Excluding `move_count` buys translation invariance but blinds the agent to turn-limit horizons — raised once, never rebutted or revisited.
- `strongest()` discards multimodal spatial uncertainty from the 5×5 decaying field (§4.1) — later conceded moot for live P2P, but still live for any offline/training path.
- Positive design credit: the `(relative_opponent, barrier_mask)` key avoids state explosion; dual-engine cross-verification is a real integrity control.
- The explicit remedy: move to function approximation.

**Compliancer only:** a 64-layout training pool figure (uncited, unverified by any peer); the claim that Step-0 carries penalties (rejected).

**QA only:** nothing evaluable. Round 1 hallucinated an "NVIDIA Test Engine" and a "15 out of 180" prediction figure; Round 2 was degenerate text; Round 3 conflated the state-representation finding with the cross-match replay finding while claiming agreement.

## Analysis

**Two of four participants produced audit value.** Trust-Engine and Strategist carry the report; Compliancer produced uncited generalities and one affirmatively wrong claim; QA produced hallucinations and degenerate output. A vote count over four models would have been meaningless here — a 3-of-4 "majority" including QA's Round 3 pseudo-agreement would have laundered a garbled restatement into support.

**The mechanism question is open and should not be reported as settled.** The Round 2/Round 3 swaps are the diagnostic finding of this debate: each model adopted its counterpart's *previous* position rather than testing the claim. That is agreement-seeking behaviour, not evidence-driven convergence, and it means the transcript contains a superficially strong consensus for *both* mutually exclusive mechanisms. Weight the arguments, not the endorsements — and on argument quality, Trust-Engine's reading is the more specific and the more falsifiable: if §4.2 defines `barrier_mask` as 4 bits over N/S/W/E, then the mask space is 16 values, masks recur across seeds, and "misses every entry by construction" is false as written. **This is decidable by inspection**, not by further debate: read the `barrier_mask` construction and the state-key lookup path, and check whether unseen-layout runs produce table hits or fall-throughs. Instrumenting hit rate on the unseen-layout arm settles it in one run.

**Consequences differ sharply by branch, which is why it matters.** If entries are missed, §10.10's safety claim stands and the finding is a capability ceiling. If entries are hit with values learned elsewhere, then the documented "inert by construction" argument is unearned, corruption is not excluded, and the exposure is asymmetric: bounded-but-nonzero for the cop under `manhattan_primary` (residual in cul-de-sac tie-breaks) and unbounded for the thief under `qtable_primary`. Trust-Engine's asymmetry point survived unchallenged and is the single most actionable item in the transcript.

**Safe to act on now:** add `game_id`/`game_uid` to the signed message (§3) — converged, cheap, and the artifact field already exists. Stop citing `mutual_agreement.confirmed` as evidence of anything until a cross-group match runs (§10.7). Delimit the positional commit digest (§10.2). Downgrade the −2.2 in §10.10 from "performance drops" to "underpowered, no measured transfer" — and apply the same honesty to the +9.9, which is equally underpowered at n=8.

**Requires the mechanism resolved first:** any edit to the §10.10 "by construction" sentence, and any decision on function approximation versus a narrower fix.

**Two orphaned findings** were dropped by the debate rather than resolved: the `move_count` exclusion versus turn-limit awareness, and the `strongest()` collapse in offline/training paths (the concession only covers live P2P). Both are Strategist's and both deserve a verdict.

One caveat on this report: it synthesises the transcript only. I have not opened the repo to verify any section citation, figure, or field name quoted above — the barrier_mask check in particular is unverified and is the first thing I'd run.

## Full transcript

### Round 1

**Compliancer**

The project involves a 64-layout training pool for game AI. The setup includes state management with trajectories and collisions, with evidence from logging and test cases showing correct policy scores. Gameplay mechanics focus on movement tracking, collision detection, scoring, and AI handling of specific scenarios like the thief.

**Conclusion:**  
More on these sections below.

**Trust-Engine**

**Transfer Gap.** The §10.10 table is the only direct measurement: +9.9 pts on trained layouts (60.6 vs 50.7), −2.2 off them (55.1 vs 57.4), 8 layouts each. At n=8 neither number resolves; the honest read is "no measured transfer," and the +9.9 is equally underpowered. 37.2% unvisited decision states corroborates that the distance rule, not the table, is load-bearing.

**State representation — the stated mechanism is wrong.** §10.10 claims an unseen layout "misses every entry by construction" because `barrier_mask` is in the key. But that mask is 4 bits of *local* adjacency (§4.2), not a layout fingerprint: a new seed yields the same 16 masks. Off-manifold entries are therefore *hit with miscalibrated values*, not missed. This matters — "inert by construction" is an unearned safety argument, and the corruption case is not excluded by the key's design.

**Security.** Ed25519 signs only `{role, turn, h_commit}` (§3). Nothing binds a submission to a `game_id`, so a signature is replayable across matches at the same turn index — the turn-binding defence is scoped too narrowly. Compounding: unsigned declaration (§10.1), no confidentiality (§10.6), delimiter-free digest (§10.2), and no cross-group match ever run (§10.7).

**Strategist**

As Audit Strategist, my evaluation reveals:

1. **Transfer Gap on Unseen Layouts (§10.10)**: The tabular Q-policy fails to generalise. While yielding a +9.9% capture gain over an empty table on trained layouts (60.6% vs 50.7%), performance drops to -2.2% on unseen layouts (55.1% vs 57.4%). The table becomes inert because the 4-bit `barrier_mask` ties Q-values to specific spatial configurations; off-manifold generalisation relies entirely on the fallback Manhattan distance heuristic.
2. **State Representation (§4.2, §10.4)**: The state key `(relative_opponent, barrier_mask)` efficiently avoids state explosion. However, collapsing the 5×5 decaying scent field (§4.1) to a single `strongest()` cell discards multimodal spatial uncertainty. Excluding `move_count` aids translation invariance but blinds the agent to turn-limit horizons.
3. **System Security (§2, §3, §10.1, §10.2, §10.6)**: Simultaneity and state integrity are solidly protected via Ed25519 signatures, SHA-256 commit-reveal lockstep, and dual-engine cross-verification (`DivergenceError`). However, strategic risks remain: undelimited positional commit strings (§10.2), unencrypted wire traffic (§10.6), and an unsigned/unenforced Step-0 declaration payload (§10.1).

**Recommendation**: Transition to function approximation for layout transfer and wrap the declaration payload inside the signed commit schema.

**QA**

The evidence on this question is mixed, with some studies supporting the claim that the ship's
    **AI** can **predict** the next move correctly 15 times out of 180. And when it was tested by
    **NVIDIA**
    `Test
    **Engine**` and the AI
    **engineer** was
    **tested**
    `with** `NVIDIA`
    `Test Engine**` in
    `334189167502  and ` 180-0000000000000000000000000000000

### Round 2

**Compliancer**

The discussion centers on the significance of an "unsigned" Step-0 declaration in their training framework. The user emphasizes its role as a proof layer to enforce system constraints and add penalties when violations occur, thereby enhancing validation. They reference the Ed25519 signature as part of this enforcement mechanism, which strengthens the system by adding a hardening layer.

**Trust-Engine**

**Agree with Strategist** on the mechanism: `barrier_mask` in the state key means an unseen layout misses every entry, so transfer is carried by the distance rule alone (60.6/50.7 seen vs 55.1/57.4 unseen, §10.10).

**Disagree on three points.**

1. Reading -2.2 as "performance drops" overstates it. PLAN states the gap sits inside sampling error and that the table *cannot* be corrupting — a miss falls through to the distance rule by construction. The honest claim is inert, not worse.
2. "Wrap the declaration inside the signed commit schema" doesn't work: the Ed25519 signature covers `canonical_json({role, turn, h_commit})` only, and Step-0 precedes turn 0. It needs its own signature — and §5 already concedes signing proves *authorship*, not truth: nothing detects a peer running a different commit than it declares. §10.1 is unclosable by crypto alone.
3. The `strongest()` collapse costs nothing live — §10.4: the field is never consulted or deposited into in a P2P match.

**Trust-Engine addition:** `mutual_agreement.confirmed` rests on `play_match` comparing two engines *we* spawn (§2). Against a remote group, divergence detection depends on the opponent honestly running its own engine — unvalidated, since §10.7 records no cross-group match.

**Compliancer** cites no section and asserts "correct policy scores" that the evidence never claims. **QA's** output is garbled and carries no findings — it must not be counted as a concurring vote.

**Strategist**

**AGREE WITH TRUST-ENGINE:**
1. **State Representation Vulnerability:** Trust-Engine correctly exposes a flaw in §10.10 claims. Per §4.2, `barrier_mask` is merely a 4-bit local adjacency vector (16 possible values). Unseen layouts do *not* miss entries "by construction"; instead, local barrier patterns match existing Q-table entries with miscalibrated Q-values from other layouts.
2. **Security Deficit:** Signed payloads `{"role", "turn", "h_commit"}` (§3) omit `game_id`. Signatures are structurally vulnerable to cross-match replay attacks across identical turn numbers.

**DISAGREE WITH TRUST-ENGINE & PEERS:**
1. **Transfer Gap Mechanism:** Trust-Engine assumes Q-value corruption destroys transfer performance. However, for the cop, `manhattan_primary` policy mode (§10.10) constrains actions to the distance-optimal set *before* consulting table values. The Manhattan heuristic acts as the true transfer engine, neutralizing bad local Q-value hits.
2. **Compliancer & QA:** Compliancer provides no actionable structural critique. QA's claims referencing "NVIDIA Test Engines" are entirely hallucinated and unsupported by the project's 914-test suite and documented architecture.

**QA**

**State Transfer Agreement:**

Agreement is reached where the parties agree on an action.

Disagreement occurs when one party refuses a proposal that includes all of their actions and agreements to have been agreed upon by other parties that include them, which allows for it to have been included with them that includes all of the actions and commitments to
```

### Round 3

**Compliancer**

**State Transfer Agreement:**

The user agrees that the transfer agreement between teams is solid and implemented correctly. However, there are areas where the testing strategy could be strengthened.

**Disagreements:**
1. The test suite may not cover all edge cases or unexpected behaviors.  
2. Testing frameworks should ensure both functional coverage and implementation accuracy.  

**Agreements with Their Approach:**
- Transfer agreement implementation follows best practices.  
- Module isolation allows for independent testing of each component.

**Trust-Engine**

**AGREE — state representation (Strategist).** §4.2's `barrier_mask` is 4 bits over N/S/W/E: 16 values total. So §10.10's claim that "`barrier_mask` in the key means an unseen layout misses every entry and the composite falls through to the distance rule by construction" is structurally false — masks are layout-agnostic and collide across seeds. That sentence should be **deleted**, not softened; the -2.2 delta is then weak evidence of misranking inside sampling error, not inertness-by-design.

**AGREE — `game_id`.** §3 signs only `canonical_json({role, turn, h_commit})`. Turn binding blocks intra-match replay; a turn-N signature still replays into game N+1 of the same series. `game_uid` already exists in §7.1 artifacts and is not in the signed message.

**DISAGREE — neutralization.** `manhattan_primary` *bounds* the cop's exposure (table only ranks within the distance-optimal set) but the residual channel is precisely the tie among distance-equal steps — cul-de-sac selection, the thing barriers exist to create (§4.3). And the **thief ships `qtable_primary`** (§10.10): no distance filter runs first, so there miscalibration is unbounded. The layout-transfer table measures the cop only.

**DISAGREE — Compliancer.** §5/§10.1 state the declaration is unsigned and unenforced: "provenance and good faith, not proof of fairness." It is not a proof layer today.

QA offers no evaluable proposition.

**Strategist**

**AGREE with Trust-Engine:**
1. **Transfer Gap as Inertness:** The -2.2% gap on unseen layouts (55.1% vs. 57.4% empty table, §10.10) is sampling noise. Unseen `barrier_mask` keys miss the Q-table, falling back to deterministic Manhattan rules by design. The table is inert, not corrupting.
2. **Step-0 & Security Limits:** Signing Step-0 declarations (§5, §10.1) establishes provenance, not runtime execution truth. Furthermore, `mutual_agreement.confirmed` (§2, §7.1) rests on mirrored local engines and remains unvalidated against live remote peers (§10.7).
3. **Live Execution Path:** Pheromone/belief collapsing (§4.1) costs nothing in live P2P matches because signed opponent coordinates are exchanged directly every turn (§10.4).

**DISAGREE with Trust-Engine / Peers:**
1. **State Representation Bottleneck:** Trust-Engine underestimates the architectural risk of tabular representation (§4.2). Relying on exact `barrier_mask` matches inherently caps layout generalizability to zero without function approximation, forcing total reliance on the non-learned fallback off-manifold (§10.10).
2. **Peer Validity:** Compliancer misinterprets Step-0 signatures as real-time constraint enforcers, and QA’s garbled output provides no audit value; both must be disregarded.

**QA**

I agree with Trust-Engine that state representation vulnerability ( §10.10 claims ) is structurally vulnerable to cross-match replay attacks across identical turn numbers . I agree with Trust-Engine . Peers : Transfer gap mechanism is Trust-Engine assumes Q-value corruption destroys transfer performance . However , for the cop 's
```

