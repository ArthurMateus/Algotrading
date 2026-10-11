# Backtest B: out-of-sample (OOS)

Generated 2026-10-11T21:17:32Z by `uv run algotrade backtest --market B --split oos` (commit `122acf3ac4a74b5e5e8d0ba6c9113d45c83eb565-dirty`). Selected on IS (`is_selection_B.json`, 2026-10-11T21:16:49Z): **SMA-126-weekly**. OOS window 2023-05-18..2026-09-30 (1232 bars), start $300, flat. Technical analysis, not financial advice.

## Verdict: FAIL (NO-GO for market B: criteria 1, 8 failed)

## Pass/fail table (docs/success-criteria.md s.6; net of costs)

| # | Criterion | Period | Value | Threshold | Result |
|---|---|---|---|---|---|
| 1 | Annualised Sharpe (excess of T-bill) | OOS | 0.423 | >= 0.50 | FAIL |
| 2 | Max drawdown (daily equity) | OOS | 34.77% | <= 35% | PASS |
| 3 | Longest underwater period (months) | OOS | 17.032 | <= 18 | PASS |
| 4 | Completed round trips | OOS | 18 | >= 12 | PASS |
| 5 | Doubled costs: Sharpe (excess of T-bill) | OOS | 0.393 | > 0 | PASS |
| 6 | Deflated Sharpe ratio of the selected IS variant | IS | 0.983 | >= 0.90 | PASS |
| 7 | Walk-forward series Sharpe | IS | 1.139 | > 0 | PASS |
| 8 | Beats benchmark: Sharpe >= bench AND max DD <= bench | OOS | Sharpe 0.423 vs 0.642; DD 34.77% vs 60.15% | both | FAIL |

Criteria 5, 7 and 8 have no config keys; their rules are hard-coded from s.6 rows 5, 7, 8 (`evaluate.CRIT5_X2_SHARPE_ABOVE`, `CRIT7_WF_SHARPE_ABOVE`, `evaluate_criteria`).
Criterion 3: longest spell 2024-03-11..2025-08-12 (recovered).

## Runs (Evidence)

| Metric | Strategy x1 | Strategy x2 costs | Benchmark x1 |
|---|---|---|---|
| Sharpe (excess of T-bill) | 0.423 | 0.393 | 0.642 |
| Max drawdown | 34.77% | 35.22% | 60.15% |
| Longest underwater (months) | 17.0 | 17.1 | 11.8 |
| Round trips | 18 | 18 | 0 |
| CAGR | 13.03% | 12.13% | 27.77% |
| Final equity $ | 453.32 | 441.24 | 685.19 |
| Share of days under water | 96.67% | 96.75% | 93.91% |
| Median drawdown length (days) | 5.0 | 5.0 | 5.0 |
| Turnover (x/yr) | 5.18 | 5.18 | 0.66 |
| Exposure (mean gross) | 44.72% | 44.73% | 99.86% |
| Fills | 103 | 103 | 59 |
| Skipped orders | 0 | 0 | 23 |
| Exits below the venue minimum (sold anyway) | 0 | 0 | 0 |

## Cost breakdown (USD, whole OOS window)

| Component | Strategy x1 | Strategy x2 | Benchmark x1 |
|---|---|---|---|
| Commission | 7.44 | 14.64 | 1.34 |
| Regulatory (SEC + TAF) | 0.00 | 0.00 | 0.00 |
| Slippage | 3.72 | 7.32 | 0.67 |
| Funding | 0.00 (spot, none) | 0.00 | 0.00 |
| **Total** | 11.16 | 21.96 | 2.01 |

Skipped orders (x1) by reason: none.
Exits sold in full below the venue minimum (x1): 0 (SPEC 11.3; a real venue may refuse these).


## Latency sensitivity (sensitivity, reported only, not a criterion)

Same variant SMA-126-weekly, x1 costs, fills at the next bar's CLOSE instead of its open (about one day of delay after the 00:00 UTC signal): Sharpe 0.280 (vs 0.423 at the open), max drawdown 34.84% (vs 34.77%), final equity $398.20 (vs $453.32). Logged in variants.jsonl as `sensitivity:close-fill:SMA-126-weekly` (kind sensitivity): not a variant, not counted in the cap, never used for selection, and it does not change any verdict above.

## BRL / CDI flag (criteria s.5; a flag, not pass/fail)

Strategy x1 equity converted to BRL at PTAX: CAGR 14.47% vs compounded CDI 13.00% over the same dates, before tax. **Beats CDI**.

## Flags

- Minimum notional and lot step are today's exchangeInfo applied to all history (SPEC 11.10, approximation).
- Survivorship/hindsight (Opinion): instruments were chosen today knowing they survived (criteria s.1).

Spread of the 12 IS Sharpes (annualised; 12 finite): min 0.791, median 0.905, max 1.193, stdev 0.148 (sample, ddof=1); deflated Sharpe 0.983. **Opinion:** the trials are highly correlated (2 signals x 3 lookbacks x 2 rebalances on the same assets and dates), so the cross-trial variance behind the DSR's SR0 is small and the DSR can be generous; read it together with this spread. Criterion 6 itself is unchanged.

## Rules that were not pre-registered (reported only; they cannot change a verdict)

- Kill switch at 50% of start equity (exit all, sticky; Opinion, SPEC s.5): it fires only after a drawdown of at least 50% from the start equity, which already fails criterion 2 (max drawdown <= 35%), so it cannot change a verdict; it did not fire in these runs.
- Stale-data halt (2 days; Opinion, SPEC): it never binds in a backtest, because a symbol with no bar is skipped as `no_bar` before the risk gate sees it, and every symbol with a bar refreshes its last-bar date at the fill. It cannot change a backtest verdict.
- TSMOM-first final tie-break (after higher Sharpe, longer lookback, monthly): it did not decide this selection (no exact tie across signals), so it changed neither the selection nor the verdict.

## Known pessimism: idle cash

- Idle cash earns 0 (criteria s.3) while the Sharpe subtracts the T-bill rate, so every day in cash scores -rf. The trend strategy sits in cash more than the always-invested benchmark, so this tilts criterion 8 (Sharpe vs benchmark) against the strategy. It is pre-registered and unchanged; its size was not computed (not a criterion).


IS criteria 6 and 7 come from `is_selection_B.json` (DSR N = 12 distinct variants logged). Sharpe annualised with sqrt(365).
