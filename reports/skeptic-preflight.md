# Skeptic pre-flight audit (before Phase 5)

Author: overfitting-skeptic, 2026-10-11. A code audit done **before** any real backtest. No backtest was run on
`data/`. Nothing was written to `reports/variants*`, `oos_runs.jsonl`, `selected-*` or `is_selection_*`. Every
simulation used **synthetic** bars from `tests/synth.py` and a temporary reports directory. The script is
`reports/skeptic/preflight_audit.py`, run with `uv run python -X utf8 reports/skeptic/preflight_audit.py`.
`uv run pytest -q`: 272 passed. This is technical analysis, not financial advice.

## Verdict

**No BLOCKER in the code.** I found no look-ahead, leakage, cost or metric bug that would invalidate the OOS
result. There are four MAJOR process gaps. Each is cheap to close, and I recommend closing them **before** the
one-time OOS runs, because they decide whether an outsider can trust that OOS was touched once and with the
pre-registered rules.

## MAJOR

**M1. The OOS lock and the "no IS after OOS" rule both rest on a single deletable file.** Owner: backtest-engineer
(code), orchestrator (process).
- **Evidence:** `check_oos` and `oos_runs` read only `reports/oos_runs.jsonl` (variants.py:136-150), and
  `run_is` refuses only when that file has rows (evaluate.py:347).
- `variants.jsonl` also records the OOS rows (`split: "oos"`, evaluate.py:494-496), but neither guard reads it.
- `reports/` is not git-ignored, yet nothing makes anyone commit these files. Today the repo holds no
  `variants.*`, `is_selection_*` or `oos_runs.jsonl` (`git status`). So deleting `oos_runs.jsonl` re-opens both
  OOS and IS re-selection, and leaves no trace.
- **Fix:**
  - (a) Make `check_oos` and `run_is` also refuse when `variants.jsonl` has any `split == "oos"` row for the market.
  - (b) Commit, as a procedure, `is_selection_<m>.json`, `selected-<m>.json`, `variants.jsonl/.md` and
    `backtest-<m>-is.md` **before** running OOS. Commit `oos_runs.jsonl` and the OOS report right after.
  - (c) Store the commit of the IS selection in `oos_runs.jsonl`.

**M2. The pre-registered grid and parameters are not enforced at runtime.** Owner: backtest-engineer.
- **Evidence:** `run_is` calls `check_cap(rd, market, keys, keys, cap)` (evaluate.py:359). It passes the same list
  as both `keys` and `allowed`, so the "outside the grid" check (variants.py:110-112) can never fire.
- `verify_criteria` checks only the hash of the criteria file (config.py:185-189). It never checks that
  `config/*.toml` (grid, sigma*, costs, splits, thresholds) still matches the criteria. Only pytest checks that
  (`tests/test_criteria_config.py`).
- So an edited `common.toml` (for example lookbacks {50, 100, 200}) run before the real grid would be accepted
  as "12 variants". The cap would stop it only afterwards.
- **Fix:**
  - (a) Derive `allowed` from a fixed copy of the §3 grid, or run the `test_criteria_config` extraction inside
    `run_is` and `run_oos`.
  - (b) Store the sha256 of `config/common.toml` and `config/<m>.toml` in `is_selection_<m>.json`, and refuse OOS
    if either differs.
  - (c) Procedure: run `uv run pytest` right before each IS and OOS command, and record the result.

**M3. OOS checks that the split dates are the same, not that the data is the same.** Owner: backtest-engineer.
- **Evidence:** `run_oos` compares only `split.to_dict()` (evaluate.py:474-477).
- Yahoo rewrites adjusted history with every new dividend (data-quality §5.3). A re-fetch between IS and OOS gives
  the same dates but different prices, and the check passes.
- The selection file is also not checked for internal consistency: `selected` is never re-checked against the
  argmax of `is_sharpe` (evaluate.py:301-312), so a hand-edited selection would be used.
- **Fix:** store the bars `manifest.json` sha256 (and the exchangeInfo file for B) in the selection, and refuse on
  a mismatch. Re-derive `select_variant(is_sharpe)` at OOS time and refuse if it disagrees. Procedure: **do not run
  `fetch` between IS and OOS.**

**M4. The SPEC build step 4 (qa-tester) looks incomplete.** Owner: qa-tester.
- **Evidence:** SPEC §9 and §10 list `tests/test_e2e.py`: end-to-end IS+OOS, and the e2e look-ahead test ("corrupt
  the future, past fills unchanged"). That file does not exist. `tests/test_replay.py` is untracked (`git status`:
  `?? tests/test_replay.py`). `reports/qa.md` appeared while I was working.
- My synthetic script covers the e2e look-ahead case ad hoc (see C1), but the regression test should exist and be
  committed before Phase 5.

## MINOR

- **m1. B fills assume zero latency (Opinion).** Owner: quant-economist / skeptic in Phase 5 (reported, not
  pass/fail).
  - A Binance `1d` bar closes at 00:00 UTC. The fill is the next bar's open, which is the same instant
    (data-quality §5.7; SPEC §3). It is not look-ahead, but it assumes the signal is computed and the order sent
    with no delay. The 0.05% slippage may not cover fast days.
  - Recommendation: a Phase 5 sensitivity check (for example fill at open × (1 ± extra slippage)), reported and
    never used to re-select.
- **m2. The deflated Sharpe ratio may be lenient (Opinion).** Owner: quant-economist (flag only).
  - **Evidence:** the formula matches Bailey and López de Prado exactly. My independent re-implementation gives
    0.922142 vs 0.922142 from the code (T6). N = 12 distinct logged variants (evaluate.py:384) and the moments
    are population moments (metrics.py:300-310), both as in the SPEC.
  - However, SR0 uses the variance across 12 highly correlated variants (2 signals × 3 lookbacks × 2 rebalances on
    the same assets). That variance is small, which makes SR0 small and the DSR generous.
  - Report the DSR together with the spread of the 12 IS Sharpes. The criteria themselves stay unchanged.
- **m3. The day-0 return is included in the Sharpe.** Owner: backtest-engineer (document only).
  - `returns = pct_change().fillna(0)` (engine.py:536) counts one zero-return day per window, and it also enters
    the DSR's `n_obs`.
  - Impact: Sharpe 0.42907 vs 0.42921 on 1,500 synthetic bars (T7). Negligible, and it applies equally to the
    strategy and the benchmark.
- **m4. TAF is charged per adjusted share.** Owner: backtest-engineer (document only).
  - Yahoo total-return prices are lower than the real prices in early history, so share counts are inflated and
    the TAF is slightly higher (pessimistic). The TAF is capped and tiny ($0.0013 per $60 sell at x1, T4).
  - The SEC fee and slippage are on notional, which is unaffected.
- **m5. Rules that were not pre-registered.** Owner: architect (already flagged as SPEC 11.11).
  - Kill switch: equity ≤ 50% exits everything and is sticky. It cannot change an OOS verdict, because a 50%
    drawdown already fails criterion 2.
  - Stale-data halt: in the backtest it **never binds**. `last_bar_date` is set at the fill bar's open for every
    symbol that has a bar (engine.py:478-480), and a symbol without a bar is skipped as `no_bar` before the gate
    sees it (engine.py:366-368).
  - Final TSMOM-first tie-break (evaluate.py:116-120): it applies only to an exact float tie across signals, which
    in practice happens only when both values are NaN. Harmless, but list all three in the Phase 5 report as
    non-pre-registered rules.
- **m6. Idle cash earns 0 while the Sharpe subtracts the T-bill.** Owner: none (pre-registered in §3). This
  penalises the strategy (more time in cash) relative to the benchmark in criterion 8. State it in the report as a
  known pessimism.

## Cleared (checked, no defect; Evidence)

- **C1. Look-ahead and leakage, end to end.** Every check below was run with the real configs (252 warm-up, full
  12-variant grid) on synthetic A and B data (T1/T2):
  - Shocking every bar **after the IS end** leaves the 12 IS Sharpes, the selection, the walk-forward Sharpe and the
    DSR identical (`True` for A and for B).
  - Shocking every bar after OOS date k leaves the OOS equity up to k identical, while the later equity changes.
  - Signals and vol use only real bars ≤ t (strategy.py:89-136; `math.fsum` windows end at t).
  - Fills happen at the t+1 open (engine.py:484-492). Orders are classified with close-t weights
    (engine.py:522), and equity is marked at the close (engine.py:495-498).
- **C2. Split and warm-up.**
  - E starts after 252 real bars strictly before it (`cumsum().shift(1)`, evaluate.py:92-96). IS is the first
    `floor(f·n)` bars (evaluate.py:100-107).
  - OOS warm-up uses only pre-OOS bars, which is legitimate because they are known at that time.
  - Every window starts flat at $300. The first decision is at OOS bar 0 and the first fill at bar 1's open
    (A: OOS starts 2014-01-17, first fill 2014-01-20; equity on day 0 = 300.0).
  - A decision on the window's last bar is dropped (engine.py:505), so IS never fills inside OOS.
- **C3. Walk-forward.** Block k is chosen on blocks 1..k−1 only (evaluate.py:139-145).
- **C4. Decision dates.** `decision_dates` reads only bar **dates** (strategy.py:167-195). It uses the date of bar
  t+1 but never a price. Unscheduled closures (Sandy 2012) can shift a date, not leak information. `next_bar` is
  `None` in backtests (evaluate.py:257).
- **C5. Union calendar.** Prices are reindexed with no forward fill (data.py:428-431). A symbol with no bar is
  valued at its last close (engine.py:495-498). A NaN target means "hold" (engine.py:515). Data-quality §4 reports
  no single-ETF missing day inside E.
- **C6. Yahoo adjustment (dividend factor depends on future dividends).** It does not leak into signals:
  - The future factor multiplies every earlier price by the same constant, and close[t]/close[t−L],
    close > SMA and the stdev of log returns are all scale-invariant.
  - Order sizes come from weight × equity, not from the price level.
  - The open uses the same day's factor (sources.py:225-228). On the ex-date the open is already ex-dividend, so
    the series is consistent.
- **C7. Costs vs criteria §4** (T4, a $60 round trip at an open of 100):
  - A, 0.2022% at x1 and 0.4043% at x2: slippage 0.10% per side, SEC + TAF on sells only.
  - B, 0.3000% at x1 and 0.6000% at x2: 0.10% commission + 0.05% slippage per side.
  - x2 doubles every figure, including the TAF cap (broker.py:43-57, risk.py:107-113).
  - The strategy and the benchmark use the same broker, minimum order and lot step (evaluate.py:489-492).
- **C8. Cap clamp (`engine._clamp_to_gate_cap`).** It trims only buys whose target is within 1/N, by at most the
  costs of the batch. Targets above 1/N still reach the gate, which refuses them (engine.py:335-340;
  `test_gate_refuses_a_target_above_the_instrument_cap`).
  - Against a gate with no cap at all, the synthetic benchmark changes by about 1e-5 Sharpe: A 0.59083 vs
    0.59082, B −0.07006 vs −0.07006 (T8).
  - Without the clamp, A's benchmark has 11 `instrument_cap` refusals (T5), so the clamp is needed.
  - It hides no violation and does not favour either side.
- **C9. Metrics and criteria logic.**
  - Sharpe = mean(r − rf)/sd·√P with P = 252 or 365 (metrics.py:284-297). Max drawdown uses daily close equity.
  - Underwater months are calendar months, counted to the end if unrecovered (metrics.py:343-373). Round trips are
    flat → long → flat, open positions excluded (metrics.py:376-392).
  - Criterion 5 is strict > 0 at x2. Criterion 7 is strict > 0. Criterion 8 is Sharpe ≥ **and** max drawdown ≤,
    against the x1 benchmark (evaluate.py:152-185).
- **C10. Selection rule.** Highest IS Sharpe, then longer lookback, then monthly, as in criteria §2
  (evaluate.py:116-128).

## Numbers that cannot be trusted yet

None exist: no real result has been produced. After Phase 5, any OOS number obtained without M1–M3 closed (or
without the procedural commits) can be audited for one-shot integrity **only through git history**. B's numbers
carry m1's zero-latency assumption.
