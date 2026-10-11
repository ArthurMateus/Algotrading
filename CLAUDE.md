# CLAUDE.md: rules for working on this repo

A **tryout**: find out, with honest evidence, which kind of algorithmic trading (if any) is realistically viable for
a retail solo developer (Windows, PowerShell, Python via uv, small budget, no co-location, no paid data), build the
smallest credible version, and test it on paper. Getting rich is not the goal; a well-evidenced NO-GO is a success.
**New chat? Read `context.md` first** (current phase, what is waiting on the owner), then this file. The original
brief is `algo-trading-orchestrator-prompt.md` (never edit it).

## Owner
- Windows 11, Brazilian Portuguese locale (Windows errors may come out in Portuguese), PowerShell. Country, tax and
  licensing situation: **unknown, ask, never assume** (the locale is not evidence of residence).
- Give exact copy-paste commands, one per code block, and explain results in plain words.
- GitHub: https://github.com/ArthurMateus/Algotrading (branch `main`, public: never commit secrets, data or personal details).
- Earlier project for style and lessons (read only, never modify): `C:\projects\My stuff\Copytrade Test`.

## Hard rules (every agent, every phase)
1. **PAPER / BACKTEST ONLY.** No real orders, no exchange API keys with trading or withdrawal permission, no signing
   or key-handling code, no live endpoint that moves money. Read-only public market data is fine.
   `tests/test_safety.py` enforces it (forbidden imports, order endpoints, signing, env/secret access in `src/` and
   `tools/`). Going live is a separate decision only the owner can make, in chat, in writing.
2. Never read or print secrets (`.env`, `secrets/`, environment variables).
3. Every claim needs a source (URL + access date, file:line, or query). No invented statistics. Write "insufficient
   data" instead of guessing. Separate **evidence** from **opinion**.
4. Technical and economic analysis, not personalised financial advice. Flag country/tax/licensing as open questions.
5. Success criteria are written and committed BEFORE any backtest (`docs/success-criteria.md`). Never move the
   goalposts after seeing results. Every variant tried is logged (`reports/variants.md`) for multiple-testing
   correction.
6. Stop at every HUMAN GATE, summarise, and wait for the owner's reply.
7. Reports under ~1,500 words, findings ranked by impact, in `docs/` (research, design) or `reports/` (results).

## Pipeline (slash commands in `.claude/commands/`, agents in `.claude/agents/`)
| Phase | Command | Agents | Output | Gate |
|---|---|---|---|---|
| 1 Research | `/research` | strategy-researcher + market-researcher (parallel), then quant-economist | `docs/strategy-survey.md`, `docs/market-survey.md`, `docs/candidates.md` | GATE 1: owner picks a candidate, gives country/capital/horizon |
| 2 Pre-registration | `/build` (step 1) | quant-economist | `docs/success-criteria.md` (committed) | |
| 3 Design | `/build` (step 2) | architect | `docs/SPEC.md` | GATE 2: owner approves spec + criteria |
| 4 Build | `/build` (step 3) | data-engineer, then strategy-developer / backtest-engineer / risk-engineer, qa-tester | `src/`, `tests/` | |
| 5 Validate | `/validate` | backtest as pre-registered; overfitting-skeptic, qa-tester, security-reviewer | `reports/backtest.md`, `reports/skeptic.md`, `reports/variants.md` | |
| 6 Forward paper | `/validate paper` | paper-trading-operator (only if phase 5 passed) | `reports/paper-*.md` | |
| 7 Verdict | `/verdict` | quant-economist | `reports/VERDICT.md` | GATE 3: owner decides |

## Layout
- `src/algotrade/` package (modules defined by `docs/SPEC.md` in phase 3), `tests/`, `tools/` (read-only scripts).
- `data/` downloaded market data and caches (git-ignored). `docs/` research and design. `reports/` results.
- `context.md` current-state handover: update it at the end of every phase.

## How to run
- Install: `uv sync`
- Tests: `uv run pytest` (must pass after every change; `tests/test_safety.py` must never be weakened).

## Conventions
- Pure, deterministic functions for signals; decisions use only data available at decision time, fills at the next
  bar. Costs (fees, spread, slippage, funding) modelled pessimistically.
- Tests fake only the network; never mock our own code. Parsers are tested against recorded real responses.
- Stage paths explicitly (`git add <paths>`), never `git add -A`. Small commits with clear messages.
- Console is cp1252: run Python that prints non-ASCII with `python -X utf8`. Write files read by code as UTF-8.
