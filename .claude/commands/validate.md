---
description: Phase 5 (validate the backtest exactly as pre-registered, red team) or phase 6 with argument 'paper'
argument-hint: "[paper]"
---
Read `CLAUDE.md`, `context.md` and `docs/success-criteria.md`. Argument: $ARGUMENTS

**Phase 5 (no argument):**
1. Check `docs/success-criteria.md` is unchanged since its pre-registration commit
   (`git log --follow docs/success-criteria.md`). If it changed after any backtest result exists, stop and tell the
   owner.
2. Launch `backtest-engineer` to run the backtest EXACTLY as pre-registered and write `reports/backtest.md`. Every
   run is logged in `reports/variants.md`.
3. In parallel, launch `overfitting-skeptic` (writes `reports/skeptic.md`), `qa-tester` (writes `reports/qa.md`) and
   `security-reviewer` (save its final message to `reports/security.md`; run `git log -p` for it if it asks).
4. For each confirmed flaw, send it to the responsible agent, fix, and re-run. Each re-run adds to the variant count.
5. Write the pass/fail table against each pre-registered threshold in `reports/backtest.md`. Update `context.md`.
   Commit. Tell the owner the result plainly. Phase 6 only starts if phase 5 passed.

**Phase 6 (`paper`):** only if `reports/backtest.md` says phase 5 PASSED. Launch `paper-trading-operator` for the
agreed period (suggest at least 4 weeks; it runs on public data with simulated fills only). Suggest a scheduled task
or a PowerShell loop for daily runs, with exact commands for the owner.
