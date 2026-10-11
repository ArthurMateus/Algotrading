# Backtest A: out-of-sample (OOS)

Generated 2026-10-11T21:17:31Z by `uv run algotrade backtest --market A --split oos` (commit `122acf3ac4a74b5e5e8d0ba6c9113d45c83eb565`). Selected on IS (`is_selection_A.json`, 2026-10-11T21:16:48Z): **SMA-252-weekly**. OOS window 2020-11-03..2026-09-30 (1483 bars), start $300, flat. Technical analysis, not financial advice.

## Verdict: FAIL (NO-GO for market A: criteria 3, 8 failed)

## Pass/fail table (docs/success-criteria.md s.6; net of costs)

| # | Criterion | Period | Value | Threshold | Result |
|---|---|---|---|---|---|
| 1 | Annualised Sharpe (excess of T-bill) | OOS | 0.624 | >= 0.40 | PASS |
| 2 | Max drawdown (daily equity) | OOS | 7.50% | <= 20% | PASS |
| 3 | Longest underwater period (months) | OOS | 24.645 | <= 18 | FAIL |
| 4 | Completed round trips | OOS | 50 | >= 20 | PASS |
| 5 | Doubled costs: Sharpe (excess of T-bill) | OOS | 0.565 | > 0 | PASS |
| 6 | Deflated Sharpe ratio of the selected IS variant | IS | 0.936 | >= 0.90 | PASS |
| 7 | Walk-forward series Sharpe | IS | 0.368 | > 0 | PASS |
| 8 | Beats benchmark: Sharpe >= bench AND max DD <= bench | OOS | Sharpe 0.624 vs 0.874; DD 7.50% vs 16.25% | both | FAIL |

Criteria 5, 7 and 8 have no config keys; their rules are hard-coded from s.6 rows 5, 7, 8 (`evaluate.CRIT5_X2_SHARPE_ABOVE`, `CRIT7_WF_SHARPE_ABOVE`, `evaluate_criteria`).
Criterion 3: longest spell 2022-03-08..2024-03-28 (recovered).

## Runs (Evidence)

| Metric | Strategy x1 | Strategy x2 costs | Benchmark x1 |
|---|---|---|---|
| Sharpe (excess of T-bill) | 0.624 | 0.565 | 0.874 |
| Max drawdown | 7.50% | 7.99% | 16.25% |
| Longest underwater (months) | 24.6 | 24.8 | 20.6 |
| Round trips | 50 | 50 | 0 |
| CAGR | 6.92% | 6.55% | 12.13% |
| Final equity $ | 445.33 | 436.33 | 589.82 |
| Share of days under water | 88.47% | 88.81% | 85.50% |
| Median drawdown length (days) | 5.0 | 5.0 | 6.0 |
| Turnover (x/yr) | 3.31 | 3.31 | 0.40 |
| Exposure (mean gross) | 58.39% | 58.42% | 99.82% |
| Fills | 204 | 204 | 237 |
| Skipped orders | 0 | 0 | 118 |
| Exits below the venue minimum (sold anyway) | 0 | 0 | 0 |

## Cost breakdown (USD, whole OOS window)

| Component | Strategy x1 | Strategy x2 | Benchmark x1 |
|---|---|---|---|
| Commission | 0.00 | 0.00 | 0.00 |
| Regulatory (SEC + TAF) | 0.08 | 0.15 | 0.01 |
| Slippage | 6.99 | 13.83 | 0.97 |
| Funding | 0.00 (spot, none) | 0.00 | 0.00 |
| **Total** | 7.06 | 13.99 | 0.98 |

Skipped orders (x1) by reason: none.
Exits sold in full below the venue minimum (x1): 0 (SPEC 11.3; a real venue may refuse these).


## BRL / CDI flag (criteria s.5; a flag, not pass/fail)

Strategy x1 equity converted to BRL at PTAX: CAGR 5.24% vs compounded CDI 11.11% over the same dates, before tax. **Red flag: does not beat CDI**.

## Flags

- Survivorship/hindsight (Opinion): instruments were chosen today knowing they survived (criteria s.1).

Spread of the 12 IS Sharpes (annualised; 12 finite): min 0.286, median 0.431, max 0.553, stdev 0.083 (sample, ddof=1); deflated Sharpe 0.936. **Opinion:** the trials are highly correlated (2 signals x 3 lookbacks x 2 rebalances on the same assets and dates), so the cross-trial variance behind the DSR's SR0 is small and the DSR can be generous; read it together with this spread. Criterion 6 itself is unchanged.

## Rules that were not pre-registered (reported only; they cannot change a verdict)

- Kill switch at 50% of start equity (exit all, sticky; Opinion, SPEC s.5): it fires only after a drawdown of at least 50% from the start equity, which already fails criterion 2 (max drawdown <= 20%), so it cannot change a verdict; it did not fire in these runs.
- Stale-data halt (5 days; Opinion, SPEC): it never binds in a backtest, because a symbol with no bar is skipped as `no_bar` before the risk gate sees it, and every symbol with a bar refreshes its last-bar date at the fill. It cannot change a backtest verdict.
- TSMOM-first final tie-break (after higher Sharpe, longer lookback, monthly): it did not decide this selection (no exact tie across signals), so it changed neither the selection nor the verdict.

## Known pessimism: idle cash

- Idle cash earns 0 (criteria s.3) while the Sharpe subtracts the T-bill rate, so every day in cash scores -rf. The trend strategy sits in cash more than the always-invested benchmark, so this tilts criterion 8 (Sharpe vs benchmark) against the strategy. It is pre-registered and unchanged; its size was not computed (not a criterion).


IS criteria 6 and 7 come from `is_selection_A.json` (DSR N = 12 distinct variants logged). Sharpe annualised with sqrt(252).
