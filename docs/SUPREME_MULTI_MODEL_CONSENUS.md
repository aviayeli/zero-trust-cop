# Supreme Multi-Model Consensus Audit

*Generated 2026-08-18 17:48 IDT by `scripts/multi-model-debate.py`.*

> Every previous audit in this repository was ONE model playing four
> specialists. This one is not: each panellist below runs on different
> weights, so a disagreement is evidence rather than a rhetorical device.

**Question.** Our learned Q-tables beat an empty table by +11.3 points on our shipped barrier layout, but on layouts never seen in training they score 55.1% vs the empty table's 57.4% — no better. Given barrier_mask is part of the state key, is our reinforcement learning contributing anything of value for league play against an unknown opponent on an unknown board, or should we ship the distance heuristic alone?

## Panel

| Role | Model | Status |
| :--- | :--- | :--- |
| Compliancer | `ollama/deepseek-r1:1.5b` | READY |
| Trust-Engine | `claude/cli` | READY |
| Strategist | `gemini/gemini-3.6-flash` | READY |
| QA | `ollama/deepseek-r1:8b` | READY |
| Aggregator | `claude/cli` | READY |

## Consensus report

## Consensus

Three claims are affirmed by more than one model with no contradiction in the transcript:

1. **Zero-shot board transfer is structurally impossible, not merely weak.** Because `barrier_mask` is part of the tabular state key, an unseen layout produces keys that were never visited in training. Trust-Engine ("structurally unreachable"), Strategist ("structural lock-in"), and Compliancer (R3, "the state key's dependency on `barrier_mask` limits transferability") all converge here. This is the single load-bearing finding.

2. **RL delivers real, large lift on the matched layout.** Cop 41.5% vs 30.2% (+11.3) vs greedy evader; 36.8% vs 22.0% (+14.8) vs the trained thief; evader survival 78.0% vs 69.8%. Trust-Engine and Strategist both cite these unchallenged. Neither disputes the numbers, only what they license.

3. **The Q-table must not be executed ungated on an unknown board.** Every model that offered an operational verdict — Trust-Engine (R1–R3), Strategist (R2), Compliancer (R3) — lands on the heuristic being the authority when the layout is unfamiliar. They disagree on *why* and on *what mechanism already provides that*, but not on the outcome.

Two further points are agreed by the two substantive voices (Trust-Engine and Strategist), with Compliancer silent:

4. **Compliancer's "40% cop score on a bare board" is a misread.** Both explicitly correct it to 0.0% across all policies.
5. **The real fix is re-keying, not gating** — ego-centric/local barrier features rather than a global mask. Strategist proposed it R1; Trust-Engine endorsed it R1 and again R3 ("real fix: re-key on local barrier features, not a gate").

## Disagreement

**1. Is 55.1% vs 57.4% a regression or noise?**
- **Strategist:** a real regression, "actively degrades," caused by "accidental state key collisions executing bad actions that override the heuristic" (R1, restated R2).
- **Trust-Engine:** noise. At n=400 a ~56% rate carries ~2.5pp standard error, ~3.5pp on the difference; across 20 layouts spanning 10.0–59.0% an aggregate 2.3pp gap is "unreadable." Verdict: *indistinguishable*, not worse. R3 escalates: the collision mechanism is not merely unproven but impossible — with the mask in the key, an unseen layout misses every entry, so the table is **inert, not corrupting**. Adds a process objection: "naming a mechanism for noise and then engineering against it is trust-negative."
- *Unresolved.* Strategist was unavailable in R3 (HTTP 503) and never answered the impossibility argument.

**2. Ship the heuristic alone, or ship a composite?**
- **Strategist R1:** ship the distance heuristic alone; the Q-table "eliminates unnecessary state-lookup overhead" when removed.
- **Strategist R2:** reversed — "do not abandon RL"; ship gated RL with Manhattan fallback. The model changed position between rounds without flagging the change.
- **Trust-Engine (all rounds):** keep the table, but only because the shipped policy is `manhattan-primary` and the table acts as a tiebreak — bounded downside, +11.3 upside where warm. "Ship, don't claim generalization."
- **Compliancer R3:** "unsuitable for league play."

**3. Does an explicit exact-mask gate buy anything?**
- **Strategist:** yes — gate lookups on exact `barrier_mask`, guaranteeing ≥57.4% by construction.
- **Trust-Engine R1:** proposed the same gate. **Trust-Engine R3:** retracted it — "the gate already exists. Exact-mask matching is what the state key does. A gate on it buys zero measurable points." This is a self-correction, and it is the sharpest live disagreement in the transcript.

**4. Are all gains overfit?**
- **Strategist R1:** "entirely overfitted to that specific 14-barrier layout."
- **Trust-Engine R2/R3:** rejects this on one axis — evader survival 78.0% vs 69.8% is against a **cop it never trained against**, and the rise from 2.2% under self-play shows the opponent-pool fix repaired a real defect. That is opponent generalization, categorically distinct from board generalization.

**5. Compliancer's reliability.**
- **Trust-Engine R2:** "items 2–5 are not derivable from the evidence… I'd discount that round entirely." **R3:** "the answer affirms and denies the same claim and cites no number. Unauditable."
- **Strategist R2:** independently flags the same 40%/0.0% contradiction.
- Compliancer never responded to either challenge and did not defend the 99.8% or 40% figures.

## Unique Findings

**Trust-Engine (uncontested by anyone):**
- Statistical power framing — the entire unknown-board comparison sits inside one standard error, so the debate's premise ("no better") is under-evidenced in *both* directions.
- Cross-layout means (37.1%, range 10–59%) are not comparable without stratifying by layout difficulty.
- Bare board = 0.0% for every policy proves capture is barrier-dependent — walls are the mechanism of capture, not an obstacle to it.
- The downside is bounded *by the existing architecture*, not by a proposed safeguard: cold keys degrade to the heuristic because the composite is manhattan-primary.
- Sharpest reframe: nothing in this evidence tests board transfer at all, because the key forbids it. The experiment cannot produce the number being argued over.

**Strategist (uncontested):**
- Two concrete re-keying routes: local ego-centric wall sensors, or hybridizing the heuristic with real-time graph search (BFS/A*).
- Operational lever: if league board seeds are revealed pre-match, 10,000 retraining episodes recovers the +11.3.

**Compliancer:** a "99.8%" Manhattan-vs-empty-table figure appearing nowhere else in the transcript, unverified and uncorroborated; and the 40% bare-board claim, explicitly contradicted by two models. No unique finding survives.

**Quorum defect:** QA was unavailable in all three rounds (localhost:11434 timeout), and Strategist was unavailable in R3. The final round contains one auditable voice plus one self-contradicting one. This report is effectively a two-model debate, and the R3 rebuttals went unanswered.

## Analysis

**Answering your question directly: on an unknown board, the RL contributes nothing — that is a property of your state key, not a training failure. On a known board it contributes a great deal. Both are true simultaneously, and the 55.1/57.4 number is not the thing that decides it.**

The debate's most useful output is Trust-Engine's R3 correction, because it dissolves the question rather than answering it. If `barrier_mask` is genuinely in the key, then on an unseen layout every lookup misses, the table never fires, and your policy *is* the distance heuristic already. Under that reading, "ship the heuristic alone" and "ship the composite" are the same shipped behavior on unknown boards, differing only in a lookup that returns nothing. There is no decision to make, and the proposed gate is a no-op.

That makes Strategist's collision mechanism the one claim worth resolving empirically, and it is cheap to check in your code: a miss can only corrupt a decision if the key is hashed into a fixed-width bucket, if the mask is truncated or defaulted, or if the tiebreak reads a default Q-value rather than testing for key presence. If none of those hold, Strategist's R1 recommendation rests on a mechanism that cannot occur, and the 2.3pp gap is what Trust-Engine says it is — noise at n=400, well inside a ±2.5pp standard error, aggregated over layouts spanning 10% to 59%.

The strongest evidentiary point in the transcript is the one Strategist's "entirely overfitted" verdict misses: the 2.2% → 78.0% evader survival jump against an untrained-against cop. That is generalization along the opponent axis, which is the axis league play actually stresses alongside board novelty. Discarding the RL because it fails board transfer would also discard the one thing demonstrated to transfer.

My recommendation, tracking the transcript rather than splitting it: **ship `manhattan-primary` with the table as tiebreak** — the unknown-board case degrades to 57.4% by construction, and the +11.3 is available whenever the mask matches. Verify the key-miss path is a presence test, not a default-value read; if it is not, fix that rather than adding a gate on top. If league seeds are knowable pre-match, retrain — that is where the real points are. And treat re-keying on local barrier features as the actual roadmap item, since it is the only change that would make the unknown-board number move at all.

Two caveats on this report's own reliability: Strategist never got to answer the impossibility argument, so disagreements 1 and 3 are unresolved rather than settled in Trust-Engine's favor; and with QA dark in all three rounds, no third independent voice ever checked either.

## Full transcript

### Round 1

**Compliancer**

The zero-trust P2P pursuit-evasion project's performance is influenced by several factors, particularly when incorporating heuristics and considering the barrier layout. Here are the key observations:

1. **Heuristic Impact**: Using a Manhattan heuristic against an empty table achieved a 99.8% score, indicating that effectively applying constraints or additional rules can significantly boost performance.

2. **Barrier Layout Effect**: The Q-table with a primary heuristic showed promise even when paired with an empty table, suggesting barriers are crucial but require optimization to maximize benefits.

3. **Self-Play Training Limitations**: While co-evolving strategies improved performance slightly on some metrics, they were less effective than training against another figure, indicating that additional interaction or guidance is needed.

4. **Cop vs. Thief Performance**: Even with a primary heuristic, the cop's score on a bare board was 40%, highlighting the need for better constraint handling to outperform the baseline.

5. **State Key Significance**: The barrier mask, part of the state key, may require more nuanced approaches in how constraints are applied or enforced during interaction.

**Conclusion**: The project benefits from heuristic optimization and effective constraint application. While heuristics alone improve performance on certain metrics, further exploration is needed to address limitations when combined with other strategies.

**Trust-Engine**

**Verdict: keep the RL, but stop calling it a policy — it's a layout-specific lookup table. Do not ship it ungated for unknown boards.**

The evidence is internally consistent, not contradictory. `barrier_mask` is in the state key, so on an unseen layout essentially no key matches what was trained. Generalization isn't weak here — it's structurally unreachable. The 55.1% vs 57.4% isn't "no better," it's slightly *worse*, and that -2.3 is the tell: partial/stale entries are firing and overriding a heuristic that would otherwise score 57.4%.

Where the mask does match, the contribution is large and threefold: +11.3 vs greedy evader (41.5 vs 30.2), +14.8 vs trained thief (36.8 vs 22.0), and +8.2 evader survival (78.0 vs 69.8) against a cop it never trained on. That last one is real transfer, and the 2.2% → 78.0% jump confirms the opponent-pool fix, not overfitting.

Two actions:
1. Gate table lookups on exact-mask (and a minimum visit count); fall through to `manhattan-primary`. That makes the unknown-board case ≥ 57.4% by construction.
2. Barriers are deterministic from a seed — if the league board is knowable pre-match, retrain 10k episodes on it. That's where the +11.3 lives.

Bare board = 0.0% for everyone confirms capture is barrier-dependent; cross-layout means (37.1%, range 10–59) are not comparable without stratifying.

**Strategist**

**No, the current RL adds no value—and actively degrades performance—on unknown boards.**

Because `barrier_mask` is embedded directly in the tabular state key, the Q-table cannot generalize to unseen geometries. On unknown layouts, the learned table achieves **55.1% vs the empty table’s 57.4%**. It underperforms the base heuristic because unvisited state keys yield arbitrary or default Q-values that corrupt decision-making.

While RL delivers real gains on the single *shipped* layout (+11.3 points for Cop at 41.5% vs 30.2%; Evader survival at 78.0% vs 69.8%), these gains are entirely overfitted to that specific 14-barrier layout. Because capture capability is heavily board-dependent (0.0% capture on bare boards vs a 37.1% mean across layouts), exact wall geometry matters, but memorization is not strategy.

### Strategic Recommendation:
1. **Immediate League Play:** **Ship the distance heuristic alone.** It outperforms the Q-table on unseen boards (57.4% vs 55.1%) and eliminates unnecessary state-lookup overhead.
2. **Next Iteration:** To make RL viable for league play, strip `barrier_mask` from the tabular key. Replace global grid memorization with local ego-centric wall sensors or hybridize the distance heuristic with real-time graph search (e.g., BFS/A* shortest path).

**QA**

[unavailable: localhost:11434: timed out]

### Round 2

**Compliancer**

**Agreeing and Disagreeing with the Discussants:**

**Agreed:**
- The Q-tables have potential in structured environments due to their organized state key, but on unknown layouts, they face challenges.

**Disagreed:**
- Verier argues that while the current setup has some overfitting on a specific 14-barrier board, generalizing might require more structure or learning strategies.

**Final Answer:**

Agreed with Strategyist; while Q-tables have merit in structured environments, on unknown boards, they may underperform. Disagreed with Verier regarding potential for better performance through additional structure or learning.

The answer is: The RL contributes to specific board types but could generalize, suggesting a need for more strategy in unknown layouts.

**Trust-Engine**

**Where I agree with Strategist:** the mechanism is right — `barrier_mask` in the key means an unseen layout is a cold key, so no transfer is possible by construction. Ego-centric wall features are the correct next iteration.

**Where I disagree:** "actively degrades" is not supported. At n=400, the standard error on a ~56% rate is ~2.5pts; the 55.1 vs 57.4 gap (~3.5pt SE on the difference) is noise. Against 20 layouts ranging 10.0–59.0%, a 2.3pt aggregate is unreadable. The honest verdict is *indistinguishable*, not *worse*.

Also, Strategist calls all gains layout-overfit, but the evader's 78.0% vs 69.8% is survival against a **cop it never trained against** — that's opponent generalization, and the previous self-play figure of 2.2% shows the pool training fixed a real defect.

**Compliancer:** items 2–5 are not derivable from the evidence, and "the cop's score on a bare board was 40%" contradicts the stated 0.0%. I'd discount that round entirely.

**Verdict:** keep the table *only* because the shipped policy is manhattan-primary — the table is a tiebreak, so cold keys degrade to the heuristic. Bounded downside, +11.3 upside where it's warm. Ship, don't claim generalization.

**Strategist**

**Do not abandon RL, but do not deploy ungated tables on unknown boards.**

**AGREE with Trust-Engine:**
1. **Structural Lock-In:** Because `barrier_mask` is in the state key, zero-shot transfer is structurally impossible. The regression on unseen boards (55.1% vs 57.4%) is caused by accidental state key collisions executing bad actions that override the heuristic.
2. **Value of RL:** On matched layouts, RL provides critical lift (+11.3 vs greedy, +14.8 vs trained thief). The jump in evader survival from 2.2% to 78.0% proves the diverse training pool works.
3. **Action:** Gate Q-table execution on exact `barrier_mask` match. Default to `manhattan-primary` on unknown boards (guaranteeing ≥57.4%). If league board seeds are revealed pre-match, run 10,000 retraining episodes to capture the +11.3 RL boost.

**DISAGREE with Compliancer:**
1. **Misread Evidence:** Compliancer claims a 40% bare-board cop score; evidence explicitly states **0.0%** across all policies, proving captures are entirely barrier-dependent.
2. **Underestimating RL:** Relying on heuristics alone caps performance at 30.2% on structured layouts versus 41.5% with trained RL.

**Verdict:** Ship gated RL with Manhattan fallback. Retrain pre-match if board seeds are known.

**QA**

[unavailable: localhost:11434: timed out]

### Round 3

**Compliancer**

The learned Q-tables demonstrate promising performance when trained against specific opponents but fail to generalize well to unknown boards. The state key's dependency on barrier_mask limits transferability, and the model struggles with unseen configurations due to insufficient adaptation. While effective for known layouts, they lack robust generalization, making them unsuitable for league play where board unpredictability is high.

**Answer:**

Our reinforcement learning approach shows potential in specific setups but lacks the ability to generalize well to unknown boards. The learned Q-tables perform well on matched layouts using the heuristic but fail when faced with completely unknown boards due to insufficient adaptation and limitations in capturing barrier complexities. The model's reliance on state key collisions and lack of overfitting in generalization make it unsuitable for league play, where unpredictability is a challenge.

**Trust-Engine**

**AGREE with Strategist:** don't ship the heuristic alone. On matched layouts the composite scores 41.5% vs 30.2% (+11.3) and 36.8% vs 22.0% vs a trained thief. And Compliancer's bare-board figure is a misread — the evidence says 0.0% for *every* policy.

**DISAGREE with Strategist, twice:**

1. *The collision mechanism isn't real.* With `barrier_mask` in the key, an unseen layout misses every entry — the table is inert, not corrupting. And 55.1% vs 57.4% on 400 trials sits inside ±2.5pp standard error. That's noise, not a regression. Naming a mechanism for noise and then engineering against it is trust-negative.

2. *The gate already exists.* Exact-mask matching is what the state key does. A gate on it buys zero measurable points.

**DISAGREE with Compliancer:** the answer affirms and denies the same claim and cites no number. Unauditable.

**My addition:** the only transferable evidence is the *opponent* axis — 78.0% vs 69.8% survival against a cop never trained against, up from 2.2% under self-play. Nothing here tests board transfer, because the key forbids it.

**Verdict:** ship `manhattan-primary`; unknown board degrades to the heuristic by construction. Known seed → retrain. Real fix: re-key on local barrier features, not a gate.

**Strategist**

[unavailable: HTTP 503: {
  "error": {
    "code": 503,
    "message": "This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.",
    "status": "UNAVAILABLE"
  }
}
]

**QA**

[unavailable: localhost:11434: timed out]

