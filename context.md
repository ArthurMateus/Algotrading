# context.md: where the project stands (2026-10-11)

Start here, then read `CLAUDE.md` (rules, pipeline, layout). Everything is **PAPER / BACKTEST ONLY**
(`tests/test_safety.py` enforces it). The original brief is `algo-trading-orchestrator-prompt.md`.

## Current phase
- Phase 0 (scaffold): done 2026-10-11. git repo, uv project, 12 agents in `.claude/agents/`, commands `/research`,
  `/build`, `/validate`, `/verdict` in `.claude/commands/`, safety test (4 tests, passing).
- Phase 1 (research): done 2026-10-11. `docs/strategy-survey.md`, `docs/market-survey.md`, `docs/candidates.md`.
  Top candidates (opinion of quant-economist): A = volatility-scaled daily trend on US ETFs (Alpaca data/paper),
  B = same engine on BTC/ETH spot (Binance-class fees), E = funding carry spot + short perp as an optional paper
  measurement only if the owner's country gives venue access. Several survey numbers are unverified (marked in the docs).

## Waiting on the owner (HUMAN GATE 1)
- Which candidate to build (or more research). Full gate question list: `docs/candidates.md` section 7.
- Country of residence (decides which venues are accessible, tax, licensing): unknown.
- Starting capital: unknown.
- Time horizon: unknown.

## Owner answers (record here, with the date)
- (none yet)

## Agent models
- [deep] agents use `opus`; [light] agents (data-engineer, qa-tester, security-reviewer, paper-trading-operator) use
  `sonnet`. Change the `model:` line in `.claude/agents/<name>.md` to switch.
