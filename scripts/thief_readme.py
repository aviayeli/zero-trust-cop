"""Derive the thief README from the cop README, deterministically.

Rebasing the thief branch conflicts every time, because both branches edit
section 0. So the thief README is REGENERATED from the cop's rather than
merged: same input, same output, no conflict resolution to get wrong.

Every substitution is checked. A silently half-converted README is the real
failure mode here -- it happened once manually, producing two cross-link
blockquotes with one pointing at the wrong repository -- so a rule whose
anchor no longer matches raises instead of being skipped.
"""

import sys
from pathlib import Path

COP = "https://github.com/aviayeli/zero-trust-cop"
THIEF = "https://github.com/aviayeli/zero-trust-thief"

RULES = [
    ("# zero-trust-cop\n", "# zero-trust-thief\n"),
    (
        f"""| **Cop / police** (this repo) | {COP} |
| **Thief / evader** — *cross-link* | **{THIEF}** |

> **Cross-repository link:** the evading half of this pair lives at
> **{THIEF}**.""",
        f"""| **Thief / evader** (this repo) | {THIEF} |
| **Cop / police** — *cross-link* | **{COP}** |

> **Cross-repository link:** the pursuing half of this pair lives at
> **{COP}**.""",
    ),
    (
        "## 3. Reinforcement learning and convergence",
        "## 3. Strategy — the ThiefBrain",
    ),
    (
        "| Strategy (Q-learning, pheromone belief, deception) |"
        " [§3](#3-reinforcement-learning-and-convergence) |",
        "| Strategy — ThiefBrain (deception, bluffing, evasion) |"
        " [§3](#3-strategy--the-thiefbrain) |",
    ),
    (
        "| Performance curves | [§3 — convergence](#empirical-convergence) |",
        "| Performance / learning curves |"
        " [§3 — convergence](#empirical-convergence) |",
    ),
    (
        "capture rate, by 200-game block          seed 20260801",
        "thief SURVIVAL rate (100% − capture)     seed 20260801",
    ),
    (
        """games    0– 200   97.5%      games 1000–1200  100.0%
games  200– 400  100.0%      games 1200–1400  100.0%
games  400– 600  100.0%      games 1400–1600  100.0%
games  600– 800  100.0%      games 1600–1800  100.0%
games  800–1000  100.0%      games 1800–2000   99.5%""",
        """games    0– 200    2.5%      games 1000–1200    0.0%
games  200– 400    0.0%      games 1200–1400    0.0%
games  400– 600    0.0%      games 1400–1600    0.0%
games  600– 800    0.0%      games 1600–1800    0.0%
games  800–1000    0.0%      games 1800–2000    0.5%""",
    ),
]

STRATEGY_BLOCK = """### The deception model — `intent: 'truth' | 'lie'`

The thief is an **evader**: `survival_thief` pays **10** for lasting all 35
turns and `capture_thief` only **5** for being caught. Its bluffing policy is
a **deterministic inversion** — it claims the opposite of what it plays:

```
police  move=MOVE:N  intent='truth'    thief  move=MOVE:N  intent='lie'
```

**The baseline is deliberately weak, and saying why matters more than the
number:** a 100 %-deterministic liar is exactly as predictable as an honest
peer. Once the cop's `BeliefTracker` drives the honesty rate to 0, inverting
the claim recovers the true move perfectly. Only a *mixed* strategy conceals
anything. `STAY` is its own opposite (D4), so a thief that stays tells the
truth that turn — documented, not patched.

Evasion is framed on the **pursuer's relative bearing**, not absolute
squares, so an escape generalises. The trained table holds 391 entries across
144 states, topping out at **4.9999** — converging on `capture_thief` (5)
rather than the survival payoff of 10, which is the table's own record that
this thief is being caught.

### Q-learning setup"""

SURVIVAL_NOTE = """Offline self-play, 2,000 games, seed `20260801`, ε decayed once per game.
Read from the **thief's** side this is a *survival* curve, and it runs the
wrong way: **this thief loses** — it evades 89.5 % of early games and is
caught in essentially all of them once the cop converges."""


def convert(text: str) -> str:
    """Apply every rule, failing loudly on any anchor that no longer matches."""
    rules = RULES + [
        ("### Q-learning setup", STRATEGY_BLOCK),
        (
            "Offline self-play, 2,000 games, seed `20260801`,"
            " ε decayed once per game.",
            SURVIVAL_NOTE,
        ),
    ]
    for index, (old, new) in enumerate(rules):
        if old not in text:
            raise SystemExit(
                f"thief_readme: rule {index} no longer matches the cop README.\n"
                f"  looking for: {old.splitlines()[0][:70]!r}\n"
                "  The cop README changed; update RULES before syncing."
            )
        text = text.replace(old, new, 1)
    return text


def main(argv=None):
    """Rewrite README.md in place as the thief edition."""
    path = Path((argv or sys.argv[1:])[0] if (argv or sys.argv[1:]) else "README.md")
    path.write_text(convert(path.read_text()), encoding="utf-8")
    print(f"thief_readme: converted {path}")


if __name__ == "__main__":
    main()
