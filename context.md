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

- Phase 2 (pre-registration): `docs/success-criteria.md` committed alone in 6711929 (2026-10-11), before any code.
- Phase 3 (design): `docs/SPEC.md`, skeleton modules in `src/algotrade/` (bodies raise NotImplementedError),
  `config/{common,A,B}.toml` (common pins the sha256 of the criteria; update it only if the owner changes the
  criteria at GATE 2, before any result exists).

## HUMAN GATE 2: passed 2026-10-11
- Owner replied "approved": SPEC.md and success-criteria.md as written (18-month underwater limit, CDI as a
  reported flag, max drawdown 20% A / 35% B, ETFs SPY EFA IEF GLD DBC, SPEC section 11 interpretations).
- Phase 4 (build): in progress.

## Answered at GATE 1
- Candidate, country, capital, drawdown tolerance: see owner answers below. Tax situation: still open.

## Owner answers (record here, with the date)
- 2026-10-11 GATE 1: build **A + B** (one daily-bar volatility-scaled trend engine on US ETFs and on BTC/ETH spot).
  Country: **Brazil**. Starting capital: **$300**. Drawdown tolerance: "a couple of weeks; preferably not big, but I
  can live with it". Knows the crypto risks. Hours per week and the total time horizon: not given (assume a small
  weekly effort and a 4-week forward paper test unless told otherwise).
- Risk-free hurdle for a Brazil resident: CDI/Selic. Selic was cut to 13.75%/yr at the Copom meeting of
  2026-09-15/16 (https://br.advfn.com/jornal/2026/09/copom-reduz-a-taxa-selic-para-13-75-ao-ano-veja, accessed
  2026-10-11). Fixed-income gains are taxed (regressive table), so the net hurdle is lower; the exact current rule is
  an open question for the owner.
- Alpaca live accounts for Brazil residents: unconfirmed, anecdotally refused
  (https://forum.alpaca.markets/t/how-to-open-account-for-non-us-resident/2500, accessed 2026-10-11). Irrelevant
  for paper/backtest; data should come from keyless free sources.

## Agent models
- [deep] agents use `opus`; [light] agents (data-engineer, qa-tester, security-reviewer, paper-trading-operator) use
  `sonnet`. Change the `model:` line in `.claude/agents/<name>.md` to switch.
