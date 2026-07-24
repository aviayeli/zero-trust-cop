# zero-trust-cop — Project Constitution

This file governs all work in this repository. It OVERRIDES default behavior and must be followed exactly.

## Karpathy's 4 Rules of Vibe Coding

1. **Think Before Coding** — Before writing any code, articulate the problem, the plan, and the expected outcome. No code without a stated intent first.
2. **Simplicity First** — Always choose the simplest solution that satisfies the requirement. Do not add abstractions, layers, or generality the current phase does not need.
3. **Surgical Changes** — Make the smallest possible change to achieve the goal. Do not refactor, rename, or "clean up" code that isn't part of the task at hand.
4. **Goal-Driven Execution** — Every change must trace back to a stated requirement in the current phase's PRD/PLAN/TODO. No speculative or "just in case" code.

## Hard Project Constraints (Dr. Segal's Course)

- **150-line limit**: No Python file may exceed 150 lines of code (including blank lines and comments). Split modules before this limit is reached, not after.
- **Strict TDD**: No implementation code may be written before a failing test exists for it. The order is always: write a failing test → confirm it fails → write the minimal code to pass it → confirm it passes.
- **No hardcoded hyperparameters**: Any tunable value (grid size, move limits, barrier counts, timeouts, scoring weights, thresholds, etc.) must live in `.env` or a config file (e.g. `config/game.json`) and be loaded at runtime — never inlined as a literal in Python source.
- **Document lifecycle**: All work must strictly follow the `docs/` lifecycle in order: `PRD.md` → `PLAN.md` → `TODO.md`. No implementation begins until the PRD is defined, no PLAN is written until the PRD is approved, and no TODO item is executed until it exists in `PLAN.md`. Work outside this lifecycle is out of scope.

## Enforcement

Any proposed change that violates a rule above must be flagged and stopped before proceeding — do not silently work around these constraints.

## Subagent Routing Policy (FinOps)
You must strictly optimize token usage by delegating context-heavy or mechanical tasks to subagents.
- For reading large files, running pytest, or fixing syntax/linting errors, YOU MUST use a fast/cheap subagent (e.g., Haiku).
- Reserve your own reasoning (Sonnet) ONLY for implementing deep architectural logic (e.g., the asyncio.Lock concurrency in Task 3).
