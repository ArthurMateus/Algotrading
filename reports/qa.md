# QA report (Phase 4, step 4) - 2026-10-11

Command: `uv run pytest -q` -> **272 passed, 0 failed, 0 xfail, 0 skipped** (about 31 s). The three new files were
run 3 times in a row: 19 passed each time (no flaky test seen; all randomness is seeded or hypothesis-derived).

## Added (Evidence: files in tests/)
| File | Tests | What it proves |
|---|---|---|
| `tests/test_replay.py` | 6 | Same inputs (data regenerated each run) give identical fills, skips, equity, weights, ledger events and Sharpe/max-DD; two independent paper runs give byte-identical ledgers; **backtest vs paper**: `engine.run` over the window and `paper.step` day by day (TSMOM-63-weekly 45 days, SMA-126-monthly 70 days) give the same fills (date, symbol, side, kind, qty, price, open, commission, slippage) and the same per-bar equity to 1e-9; the same after a kill-switch crash (kill fired and exits match). **No divergence found, so no xfail.** |
| `tests/test_e2e.py` | 3 | CLI on synthetic data in temp dirs: status (empty) -> fetch via loopback fake server (monthly kline zips, FRED, BCB, exchangeInfo) -> OOS before IS refused (exit 1, nothing logged) -> `backtest is` (selection files, 13 logged runs, report) -> `backtest oos` (criteria 1-8, report) -> second OOS refused (exit 1, report unchanged, nothing logged) -> `--force` without reason (exit 2) -> re-selection after OOS refused -> `--force --reason` (exit 0, logged with reason, "FORCED OOS RERUN #2" in report) -> status (12/12, 2 OOS runs). Also: backtest/paper with no data or no selection exit 1; bad arguments exit 2. A fixture hashes the real `data/` and `reports/` trees before and after and fails if anything changed. |
| `tests/test_properties.py` | 6 | Whole-engine invariants on random panels (random paths, vol, drift, gaps, late listing, 4 variants, cost x1/2/5): cash and positions never negative, weights >= 0 and gross <= cap, fills only on real bars at that bar's open with slippage in the trade direction, ledger replay == engine books, determinism, doubled cost rate per unit traded; metrics: max drawdown in [0,1) and scale-free, Sharpe scale-invariant and sign-flipping, round trips <= sells. A guard test fails if the engine property never actually traded. Broker/risk/ledger/paper properties already existed and were not duplicated. |

`tests/test_safety.py`: untouched. It scans `src/` and `tools/` with `rglob("*.py")`, so every module in `src/algotrade/`
(14 files) is covered, plus a subprocess test that imports every module via `pkgutil.walk_packages`. Not weakened.
The real `data/`, `reports/variants*`, `oos_runs.jsonl`, `selected-*`, `is_selection_*` were not touched (`reports/` still
holds only `data-quality.md`; the e2e fixture enforces it).

## Failures and flaky tests
None observed.

## Untested or weakly tested paths, ranked by risk (Opinion, with evidence of the gap)
1. **Market A end to end.** E2E, replay and paper-vs-engine run on market B (Binance, daily calendar, no SEC/TAF fees)
   only. Market A (ETF calendar with holidays, SEC/TAF regulatory fees, Yahoo/Stooq sources, `_expected_next` weekday
   logic in paper.py) has unit coverage but no backtest-vs-paper agreement test. Highest residual risk for Phase 5/6.
2. **Real data never exercised.** All tests use synthetic series and a handful of fixtures. Real quirks (outliers,
   zero volume, gaps, Yahoo null rows, Stooq blocking) only show up in Phase 5. The SGS fixture is served for every
   9-year chunk request in e2e, so BCB chunk stitching with distinct data is not tested.
3. **CLI `paper` success path.** `cli paper` is only tested for refusal; the success path needs "today" and a network
   fetch of up to ~450 daily 404 probes against the fake server, so it is covered via `paper.step(..., fetch=False)` only.
   The CLI wiring of `paper_step` -> `format_report` has no test.
4. **Paper catch-up vs engine.** Late decisions after stale gaps and the "decision on the newest bar" rule exist only in
   paper.py; the engine has no counterpart, so the agreement test cannot cover them (paper-only tests cover them).
5. **Windows file lock and fsync** (`paper._lock`, ledger fsync) are exercised in a single process only; a true
   two-process race is untested.
6. **`fetch` partial failure** (one market fails, exit 1, other continues) and the cp1252 console path for non-ASCII
   output are untested; reports are asserted ASCII-only, console prints were not checked for non-ASCII.
7. **`evaluate._git_commit` outside a git repo** (this folder is not a git repo today) works in the e2e run but its
   fallback value is not asserted.
8. e2e uses a scaled-down config (warm-up 30, lookbacks 5/10/20, 12 variants still); the real grid (63/126/252) and
   warm-up 252 are covered only by `test_criteria_config.py` and `test_config.py` (config values), not by a run.
