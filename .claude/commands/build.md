---
description: Phases 2-4 - pre-register success criteria, design (stops at HUMAN GATE 2), then build after approval
argument-hint: "<chosen candidate, or 'approved' after GATE 2>"
---
Run phases 2-4 of the pipeline in `CLAUDE.md`. Owner input: $ARGUMENTS

Read `CLAUDE.md`, `context.md` and `docs/candidates.md` first. Never proceed without the owner's choice of candidate
recorded in `context.md`.

**If `docs/SPEC.md` is not yet approved by the owner (see `context.md`):**
1. Phase 2: launch `quant-economist` to write `docs/success-criteria.md` for the chosen candidate, using the owner's
   capital, horizon and country constraints. Commit it ALONE, in its own commit
   ("Pre-register success criteria for <candidate>"), before any backtest code exists. Record the commit hash in
   `context.md`.
2. Phase 3: launch `architect` to write `docs/SPEC.md`. Commit it.
3. HUMAN GATE 2: summarise the spec and the criteria for the owner, ask for approval, then STOP.

**If the owner has approved (argument `approved`, recorded in `context.md`):**
4. Phase 4: launch `data-engineer` first and wait for it. Then launch `strategy-developer`, `backtest-engineer` and
   `risk-engineer` in parallel (use `isolation: "worktree"` if their modules overlap, then merge), plus `qa-tester`.
5. Run `uv run pytest`; every test, including `tests/test_safety.py`, must pass. Small commits, explicit paths.
6. Update `context.md` and tell the owner the next command is `/validate`.
