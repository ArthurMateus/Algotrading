# Backtest B: in-sample (IS)

Generated 2026-10-11T21:16:49Z by `uv run algotrade backtest --market B --split is` (commit `cfc3af3dfba0d12be8ebc3b8e698a06f5a0ef455`). Pre-registered rules: `docs/success-criteria.md` (sha256 `dd3305010517...`). **Evidence** = numbers computed below; **Opinion** is labelled. Technical analysis, not financial advice.

## Split (criteria s.2, SPEC 11.1)

| E start | IS | OOS | bars E / IS / OOS |
|---|---|---|---|
| 2018-04-26 | 2018-04-26..2023-05-17 | 2023-05-18..2026-09-30 | 3080 / 1848 / 1232 |

WF blocks: 1: 2018-04-26..2019-04-29, 2: 2019-04-30..2020-05-03, 3: 2020-05-04..2021-05-07, 4: 2021-05-08..2022-05-12, 5: 2022-05-13..2023-05-17

## Criteria evaluated on IS

| # | Criterion | Value | Threshold | Result |
|---|---|---|---|---|
| 6 | Deflated Sharpe ratio of the selected IS variant | 0.983 | >= 0.90 | PASS |
| 7 | Walk-forward series Sharpe | 1.139 | > 0 | PASS |

Selected variant (highest IS Sharpe; ties: longer lookback, then monthly): **SMA-126-weekly**. Saved to `is_selection_B.json` (read by the OOS run) and `selected-B.json` (read by the paper runner).

Walk-forward choices for blocks 2..5: SMA-126-monthly, SMA-126-weekly, SMA-126-weekly, SMA-126-weekly; WF Sharpe 1.139.
DSR inputs (per bar): SR 0.0624, n_obs 1848, skew 0.079, kurtosis 12.767, N trials 12.

Spread of the 12 IS Sharpes (annualised; 12 finite): min 0.791, median 0.905, max 1.193, stdev 0.148 (sample, ddof=1); deflated Sharpe 0.983. **Opinion:** the trials are highly correlated (2 signals x 3 lookbacks x 2 rebalances on the same assets and dates), so the cross-trial variance behind the DSR's SR0 is small and the DSR can be generous; read it together with this spread. Criterion 6 itself is unchanged.

## All 12 variants on IS (net of x1 costs, start $300 each)

| Variant | Sharpe | Max DD | Underwater (mo) | Round trips | CAGR | Costs $ | Final $ |
|---|---|---|---|---|---|---|---|
| TSMOM-63-weekly | 0.831 | 41.06% | 18.3 | 36 | 25.60% | 21.55 | 949.76 |
| TSMOM-63-monthly | 0.797 | 41.39% | 18.3 | 19 | 25.53% | 13.46 | 947.34 |
| TSMOM-126-weekly | 1.174 | 35.31% | 18.3 | 20 | 37.29% | 21.69 | 1489.75 |
| TSMOM-126-monthly | 0.928 | 33.15% | 18.3 | 11 | 29.04% | 8.96 | 1089.10 |
| TSMOM-252-weekly | 0.891 | 36.65% | 30.0 | 14 | 26.35% | 10.38 | 979.05 |
| TSMOM-252-monthly | 0.791 | 37.50% | 27.9 | 7 | 23.20% | 5.57 | 861.65 |
| SMA-63-weekly | 1.131 | 31.62% | 18.3 | 36 | 35.68% | 27.67 | 1403.73 |
| SMA-63-monthly | 0.807 | 48.30% | 24.2 | 24 | 24.80% | 16.58 | 919.81 |
| **SMA-126-weekly** | 1.193 | 39.01% | 18.3 | 18 | 38.28% | 21.24 | 1545.09 |
| SMA-126-monthly | 1.043 | 40.38% | 18.3 | 12 | 35.76% | 13.46 | 1407.91 |
| SMA-252-weekly | 0.920 | 40.45% | 18.3 | 16 | 27.27% | 12.86 | 1015.41 |
| SMA-252-monthly | 0.891 | 35.95% | 24.2 | 10 | 26.18% | 7.40 | 972.48 |
| benchmark | -0.697 | 57.89% | 60.4 | 2 | -13.36% | 0.75 | 145.28 |

Sharpe: mean(r - rf) / sd(ddof=1) x sqrt(365), rf = DTB3/100/365 per bar.

## Flags

- Minimum notional and lot step are today's exchangeInfo applied to all history (SPEC 11.10, approximation).
- Survivorship/hindsight (Opinion): instruments were chosen today knowing they survived (criteria s.1).

## Rules that were not pre-registered (reported only; they cannot change a verdict)

- Kill switch at 50% of start equity (exit all, sticky; Opinion, SPEC s.5): it fires only after a drawdown of at least 50% from the start equity, which already fails criterion 2 (max drawdown <= 35%), so it cannot change a verdict; it did not fire in these runs.
- Stale-data halt (2 days; Opinion, SPEC): it never binds in a backtest, because a symbol with no bar is skipped as `no_bar` before the risk gate sees it, and every symbol with a bar refreshes its last-bar date at the fill. It cannot change a backtest verdict.
- TSMOM-first final tie-break (after higher Sharpe, longer lookback, monthly): it did not decide this selection (no exact tie across signals), so it changed neither the selection nor the verdict.

## Known pessimism: idle cash

- Idle cash earns 0 (criteria s.3) while the Sharpe subtracts the T-bill rate, so every day in cash scores -rf. The trend strategy sits in cash more than the always-invested benchmark, so this tilts criterion 8 (Sharpe vs benchmark) against the strategy. It is pre-registered and unchanged; its size was not computed (not a criterion).

The OOS window has not been touched by this run.
