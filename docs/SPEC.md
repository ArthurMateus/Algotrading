# SPEC: one daily trend engine for A (US ETFs) and B (BTC/ETH spot)

Phase 3, architect, 2026-10-11. Implements `docs/success-criteria.md` (sha256 pinned in `config/common.toml`)
exactly; it changes nothing in it. PAPER / BACKTEST ONLY. Skeletons with signatures exist in `src/algotrade/`.

## 1. Modules, owners, contracts

| Module | Owner | Public API (see skeleton docstrings) |
|---|---|---|
| `config.py` | data-engineer | `load_config(market) -> MarketConfig` (frozen dataclasses), `ConfigError` |
| `sources.py` | data-engineer | `http_get`, `binance_kline_url`, parsers: `parse_binance_klines_zip`, `parse_exchange_info`, `parse_stooq_csv`, `parse_yahoo_chart`, `parse_fred_csv`, `parse_sgs_json` |
| `data.py` | data-engineer | `fetch_market`, `fetch_aux`, `load_bars`, `check_integrity`, `build_panel`, `load_aux`, `min_order_usd`, `lot_step`; `Bars`, `Panel`, `Aux`, `Issue` |
| `cli.py` | data-engineer | `build_parser`, `main` (wires every command in step 1) |
| `strategy.py` | strategy-developer | `Variant`, `grid`, `tsmom_signal`, `sma_signal`, `realised_vol`, `sleeve_weight`, `decision_dates`, `target_weights`, `benchmark_weights` |
| `broker.py` | backtest-engineer | `CostModel`, `Order`, `Fill`, `Skip`, `PaperBroker.execute` |
| `metrics.py` | backtest-engineer | `sharpe`, `per_bar_sharpe`, `max_drawdown`, `longest_underwater`, `round_trips`, `deflated_sharpe`, `cagr`, `turnover`, `exposure`, `underwater_share`, `median_drawdown_length`, `cost_breakdown`, `brl_cdi_flag` |
| `variants.py` | backtest-engineer | `check_cap`, `record_run`, `check_oos`, `record_oos` |
| `engine.py` | backtest-engineer | `run(panel, targets, decisions, cfg, start, end, cost_mult, band) -> RunResult` |
| `evaluate.py` | backtest-engineer | `make_split`, `walk_forward`, `select_variant`, `run_is`, `run_oos`, `status` |
| `risk.py` | risk-engineer | `RiskGate.check(order, qty, view) -> Verdict`, `GateView` |
| `ledger.py` | risk-engineer | `Ledger.append/events/replay`, `State.apply` |
| `paper.py` | risk-engineer | `paper_step(market) -> StepReport` |

**Contracts.**
- *Bars*: DataFrame, `DatetimeIndex` "date" = UTC calendar date (tz-naive midnight), strictly increasing, float64
  `open high low close volume`; `Bars.adjusted` in {`total_return`, `price_only`, `none`}, `Bars.source`.
- *Panel*: date x symbol `open`, `close`, bool `valid` on one calendar (A: union of ETF dates; B: every UTC day).
- *Aux*: `rf_per_bar` (DTB3/100/periods_per_year, forward-filled), `rf_available`, `ptax`, `cdi_daily`.
- *targets*: date x symbol weights in [0, 1/N] decided at close t. *Order* (decided t, fills t+1 open) ->
  *Fill*/*Skip*. *RunResult*: daily close equity, returns, weights, fills, skips, in-memory ledger.
- Every state change is a ledger event (`genesis`, `decision`, `fill`, `skip`, `kill`, `mark`).

## 2. Data layer
Keyless GETs with stdlib `urllib.request` only (fixed User-Agent, timeout, 3 retries with backoff, polite delay). No
auth headers, no environment variables, no keys. Base URLs live in `config/common.toml [urls]` so tests can point
them at a loopback server.
- B: `data.binance.vision/data/spot/monthly/klines/{SYM}/1d/` zips, plus daily zips for the last month (the
  timestamp unit can be ms or us). Min notional and lot step from `data-api.binance.vision/api/v3/exchangeInfo`,
  cached with the date fetched; the $10 fallback is used if unavailable.
- A: Stooq daily CSV first, then the Yahoo v8 chart (OHLC scaled by adjclose/close). The data-engineer must verify
  whether Stooq is dividend-adjusted. If not, use Yahoo. If only price-return exists, the strategy and the benchmark
  both use it and the report flags it (§1 of the criteria).
- FRED `fredgraph.csv?id=DTB3`; BCB SGS series 1 and 12 (JSON, requested in date chunks).
- Cache: **Parquet** (pyarrow) under `data/bars/<market>/` and `data/aux/`, plus `manifest.json` (source,
  adjustment, fetch time, coverage, sha256). `load_*` never touches the network.
- Integrity: gaps vs the calendar, duplicates, monotonicity, OHLC consistency, non-positive prices, return outliers
  (reported, never dropped). The data-engineer writes `reports/data-quality.md`.
- Fixtures: small real responses in `tests/fixtures/` (one kline zip, exchangeInfo, Stooq CSV, Yahoo JSON, FRED CSV,
  SGS JSON), re-recordable with `tools/record_fixtures.py`.

## 3. Strategy (pure)
TSMOM: long if `close[t]/close[t-L]-1 > 0`. SMA: long if `close[t] > SMA_L(t)`. vol = stdev(ddof=1) of the last 60
log returns x sqrt(252 or 365). Weight = (1/N) x min(1, sigma*/vol) if long, else 0. Decision dates are the last
bar before the first bar of each ISO week or month, so fills land on that first bar's open.

## 4. Engine, broker, metrics
- The engine loops bar by bar: at a decision close it classifies orders (entry, exit, or rebalance only if
  |delta w| >= 2%), then at the next open each order goes through `RiskGate.check` and then `PaperBroker.execute`.
  Sells go first, then buys, and cash never goes negative. Equity is marked at the close.
- Costs per criteria §4 (config `[costs]`). Buys fill at open x (1+s), sells at open x (1-s). Commission, SEC and
  TAF are on sells only. Everything is x `cost_mult` (1 or 2).
- Quantities: A fractional; B floored to the lot step. A trade below the minimum notional is skipped. Start: $300.
- Annualisation: 252 (A), 365 (B). Sharpe = mean(r - rf)/sd x sqrt(P). Max drawdown on daily close equity. The
  longest underwater spell is in calendar months, counted to the window end if unrecovered. Round trips are
  flat -> long -> flat per symbol, summed. The DSR formula is in the `metrics.deflated_sharpe` docstring, with
  N = distinct variants logged for the market, using per-bar Sharpe, skew and kurtosis of the selected variant's IS
  returns. Every result also carries CAGR, turnover, exposure, underwater share, median drawdown length, cost
  breakdown, and the BRL/CDI flag (PTAX conversion vs compounded SGS 12).
- `evaluate.run_is`: E start, a 70/30 (A) or 60/40 (B) split, the 12-variant grid each simulated once over IS, WF
  (5 blocks, expanding), selection with tie rules, DSR. Writes `reports/is_selection_<m>.json`.
  `evaluate.run_oos`: reads that file, runs the variant at x1 and x2 and the benchmark (1/N, monthly, no band),
  then writes a criteria 1-8 PASS/FAIL table to `reports/backtest-<m>-oos.md`.
- `variants.py`: every run appends to `reports/variants.jsonl` (source of truth) and `reports/variants.md`. It
  refuses a 13th distinct variant key or any key outside the grid. The OOS run is logged in
  `reports/oos_runs.jsonl`. A second run needs `--force --reason`, and the report flags it.

## 5. Risk gate and ledger
One `RiskGate` for backtest and paper: no shorts, cash covers buy + costs (no leverage), gross <= 100%, weight
after a buy <= 1/N, a stale symbol (no new bar for `stale_after_days`) blocks entries/increases, and a
total-loss kill switch (equity <= 50% of start) is sticky, blocks entries and exits everything. Reducing/closing
sells are never refused. **Opinion:** the 50% kill level cannot change an OOS verdict (a 50% loss already fails criterion 2
in both markets); in IS it only touches a variant that lost half its capital. Ledger: append-only JSONL, flush + fsync per line, replay folds events into `State`,
and a torn last line is ignored and reported. Paper: `data/paper/<m>/ledger.jsonl`, one idempotent step per day.

## 6. Config
`config/common.toml`, `config/A.toml`, `config/B.toml`, loaded with stdlib `tomllib`. Unknown or missing keys
raise `ConfigError`. `[criteria] sha256` pins the criteria file (CRLF normalised to LF).
`tests/test_criteria_config.py` (qa-tester) checks the hash and extracts each pre-registered number from the
criteria text (sigma*, splits, grid, cap, costs, minimums, the 8 thresholds), comparing them with the config.

## 7. CLI (Windows PowerShell, one command each)
`[project.scripts] algotrade = "algotrade.cli:main"` (added by the data-engineer).
- `uv run algotrade fetch --market all`
- `uv run algotrade backtest --market A --split is`
- `uv run algotrade backtest --market A --split oos` (refuses a second time; `--force --reason "..."` is logged)
- `uv run algotrade paper --market B`
- `uv run algotrade status`

Output is plain ASCII (the cp1252 console). Exit codes: 0 ok, 1 refused, 2 bad arguments.

## 8. Dependencies
Runtime: `numpy`, `pandas`, `pyarrow`. Dev: `pytest`, `hypothesis`. Stdlib for HTTP, zip, TOML, JSON, and the
normal distribution (`statistics.NormalDist`). No scipy, no httpx, no trading or signing SDK. Modules import
pandas inside functions or under `TYPE_CHECKING` only where needed. The safety test imports every module.

## 9. Test plan (tests fake only the network; never mock our own code)
| File | Owner | Covers |
|---|---|---|
| `fakes.py`, `synth.py` | data-engineer | loopback HTTP server serving fixtures; deterministic synthetic bars |
| `test_config.py`, `test_sources.py`, `test_data.py` | data-engineer | unknown keys, parsers on fixtures, integrity, cache round trip, no-network load |
| `test_strategy.py` | strategy-developer | hand-computed signals/vol/weights; **look-ahead**: truncating data after t leaves every value <= t unchanged; decision dates |
| `test_broker.py`, `test_metrics.py`, `test_variants.py`, `test_engine.py`, `test_evaluate.py` | backtest-engineer | hand-computed costs (x1, x2), min-order skips, Sharpe/DD/underwater/round trips/DSR on tiny cases, cap and OOS refusal, fill at the t+1 open (a price shock at the t+1 close does not change the t+1 fill), split/WF boundaries |
| `test_risk.py`, `test_ledger.py`, `test_paper.py` | risk-engineer | hypothesis: no order sequence breaches a cap, exits always allowed, kill switch, torn tail, replay == live state, paper idempotence |
| `test_criteria_config.py`, `test_replay.py`, `test_e2e.py` | qa-tester | config vs criteria, deterministic replay (same inputs give identical fills/metrics; the ledger replay equals the engine state), end-to-end IS+OOS on synthetic data, e2e look-ahead (corrupt the future, past fills unchanged) |
| `test_safety.py` | (never weakened) | still passes after every step |

## 10. Build order (no two agents touch the same file)
1. **data-engineer** (alone): pyproject deps + script entry, `config.py`, `sources.py`, `data.py`, `cli.py`,
   `tests/fakes.py`, `tests/synth.py`, fixtures + `tools/record_fixtures.py`, `reports/data-quality.md`.
2. **In parallel:** strategy-developer (`strategy.py`); backtest-engineer (`broker.py`, `metrics.py`,
   `variants.py`); risk-engineer (`risk.py`, `ledger.py`); qa-tester (`test_criteria_config.py`).
3. **In parallel:** backtest-engineer (`engine.py`, `evaluate.py`); risk-engineer (`paper.py`).
4. **qa-tester:** `test_replay.py`, `test_e2e.py`, property tests, `reports/qa.md`.

## 11. Ambiguities resolved (criteria unchanged; owner can overrule at GATE 2)
1. **Warm-up.** The §1 "first date with >= 252 bars" and the §2 "first 252 bars are warm-up" describe the same
   point: E starts at the first date on which every instrument has >= 252 real bars before it. There is no double
   warm-up.
2. **Rebalance timing.** "First bar of the week/month" is the fill bar. The decision is at the previous close.
   Each window (IS, OOS, benchmark) starts flat at $300. The first decision is at the window's first close and fills
   at the next open, the same for strategy and benchmark.
3. **Minimum order vs "exits always trade".** Entries and rebalances below the minimum are skipped. An exit always
   sells the full position, even if it is below the minimum (§3 is the more specific rule). Real Binance can refuse
   such a sell, so these are counted in the report.
4. **Benchmark band.** §5 gives no band, so the benchmark rebalances fully each month (minimum-order rule applies).
5. **Walk-forward** uses slices of one full-IS simulation per variant. It does not restart at each block.
6. **Underwater months** are calendar months (peak + 18 months).
7. **Round trips** are summed over symbols, and only completed ones count.
8. **rf** is DTB3 (discount yield, used as is) / 100 / P per bar, forward-filled. If DTB3 is missing, rf = 0 and
   the report flags it.
9. **N in the DSR** is the number of distinct variants logged for the market (12 if the grid runs once).
10. **Minimum notional for B** uses today's exchangeInfo for the whole history. This is a known approximation,
    flagged.
11. **Kill switch and stale-data days** are Opinion (not pre-registered), chosen so they cannot change a verdict.

## 12. Out of scope
Live trading, real accounts, API keys, signing, order endpoints; perps, funding, shorting, margin; ETF rotation or
any variant outside the 12-per-market grid; intraday data; tax computation; FX hedging; schedulers/services (the
owner runs `paper` by hand or with Windows Task Scheduler later); dashboards, chat bots and notifications; delisted
crypto pairs (not available, flagged).
