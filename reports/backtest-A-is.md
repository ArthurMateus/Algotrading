# Backtest A: in-sample (IS)

Generated 2026-10-11T21:16:48Z by `uv run algotrade backtest --market A --split is` (commit `cfc3af3dfba0d12be8ebc3b8e698a06f5a0ef455`). Pre-registered rules: `docs/success-criteria.md` (sha256 `dd3305010517...`). **Evidence** = numbers computed below; **Opinion** is labelled. Technical analysis, not financial advice.

## Split (criteria s.2, SPEC 11.1)

| E start | IS | OOS | bars E / IS / OOS |
|---|---|---|---|
| 2007-02-07 | 2007-02-07..2020-11-02 | 2020-11-03..2026-09-30 | 4943 / 3460 / 1483 |

WF blocks: 1: 2007-02-07..2009-11-03, 2: 2009-11-04..2012-08-02, 3: 2012-08-03..2015-05-06, 4: 2015-05-07..2018-02-02, 5: 2018-02-05..2020-11-02

## Criteria evaluated on IS

| # | Criterion | Value | Threshold | Result |
|---|---|---|---|---|
| 6 | Deflated Sharpe ratio of the selected IS variant | 0.936 | >= 0.90 | PASS |
| 7 | Walk-forward series Sharpe | 0.368 | > 0 | PASS |

Selected variant (highest IS Sharpe; ties: longer lookback, then monthly): **SMA-252-weekly**. Saved to `is_selection_A.json` (read by the OOS run) and `selected-A.json` (read by the paper runner).

Walk-forward choices for blocks 2..5: TSMOM-126-monthly, TSMOM-252-monthly, TSMOM-252-monthly, TSMOM-126-monthly; WF Sharpe 0.368.
DSR inputs (per bar): SR 0.0348, n_obs 3460, skew -0.596, kurtosis 6.994, N trials 12.

Spread of the 12 IS Sharpes (annualised; 12 finite): min 0.286, median 0.431, max 0.553, stdev 0.083 (sample, ddof=1); deflated Sharpe 0.936. **Opinion:** the trials are highly correlated (2 signals x 3 lookbacks x 2 rebalances on the same assets and dates), so the cross-trial variance behind the DSR's SR0 is small and the DSR can be generous; read it together with this spread. Criterion 6 itself is unchanged.

## All 12 variants on IS (net of x1 costs, start $300 each)

| Variant | Sharpe | Max DD | Underwater (mo) | Round trips | CAGR | Costs $ | Final $ |
|---|---|---|---|---|---|---|---|
| TSMOM-63-weekly | 0.405 | 9.07% | 30.3 | 206 | 2.75% | 26.70 | 435.59 |
| TSMOM-63-monthly | 0.286 | 11.43% | 76.4 | 104 | 2.21% | 13.74 | 405.07 |
| TSMOM-126-weekly | 0.405 | 10.09% | 28.6 | 117 | 2.88% | 16.93 | 443.05 |
| TSMOM-126-monthly | 0.532 | 12.34% | 23.2 | 58 | 3.73% | 9.90 | 496.42 |
| TSMOM-252-weekly | 0.400 | 11.25% | 24.2 | 99 | 2.86% | 13.82 | 441.77 |
| TSMOM-252-monthly | 0.457 | 12.92% | 33.2 | 44 | 3.27% | 7.77 | 466.60 |
| SMA-63-weekly | 0.335 | 10.63% | 38.0 | 251 | 2.32% | 31.58 | 411.19 |
| SMA-63-monthly | 0.376 | 9.80% | 48.4 | 127 | 2.59% | 15.97 | 426.03 |
| SMA-126-weekly | 0.486 | 7.29% | 24.6 | 161 | 3.19% | 21.92 | 461.89 |
| SMA-126-monthly | 0.515 | 8.32% | 68.9 | 81 | 3.45% | 12.11 | 477.90 |
| **SMA-252-weekly** | 0.553 | 6.58% | 37.9 | 103 | 3.61% | 15.19 | 488.32 |
| SMA-252-monthly | 0.496 | 7.30% | 38.4 | 52 | 3.39% | 8.40 | 474.11 |
| benchmark | 0.368 | 34.64% | 38.2 | 0 | 4.56% | 2.04 | 553.42 |

Sharpe: mean(r - rf) / sd(ddof=1) x sqrt(252), rf = DTB3/100/252 per bar.

## Flags

- Survivorship/hindsight (Opinion): instruments were chosen today knowing they survived (criteria s.1).

## Rules that were not pre-registered (reported only; they cannot change a verdict)

- Kill switch at 50% of start equity (exit all, sticky; Opinion, SPEC s.5): it fires only after a drawdown of at least 50% from the start equity, which already fails criterion 2 (max drawdown <= 20%), so it cannot change a verdict; it did not fire in these runs.
- Stale-data halt (5 days; Opinion, SPEC): it never binds in a backtest, because a symbol with no bar is skipped as `no_bar` before the risk gate sees it, and every symbol with a bar refreshes its last-bar date at the fill. It cannot change a backtest verdict.
- TSMOM-first final tie-break (after higher Sharpe, longer lookback, monthly): it did not decide this selection (no exact tie across signals), so it changed neither the selection nor the verdict.

## Known pessimism: idle cash

- Idle cash earns 0 (criteria s.3) while the Sharpe subtracts the T-bill rate, so every day in cash scores -rf. The trend strategy sits in cash more than the always-invested benchmark, so this tilts criterion 8 (Sharpe vs benchmark) against the strategy. It is pre-registered and unchanged; its size was not computed (not a criterion).

The OOS window has not been touched by this run.
