# Data quality report (phase 4, step 1)

Author: data-engineer, 2026-10-11. All downloads on 2026-10-11 (UTC) with `uv run algotrade fetch --market all`; keyless
read-only GETs only. Criteria period end: 2026-09-30. Technical findings, not advice.

## 1. Sources actually used (Evidence)

| Data | Source (URL pattern) | Result |
|---|---|---|
| A: ETF daily bars | Yahoo v8 chart `https://query1.finance.yahoo.com/v8/finance/chart/{SYM}?period1=..&period2=..&interval=1d&events=div%2Csplit` | used, total return (OHLC scaled by adjclose/close) |
| A: planned first choice | Stooq `https://stooq.com/q/d/l/?s={sym}.us&i=d` | **blocked**: HTTP 200 but a JavaScript proof-of-work page, not CSV. Not circumvented. SPEC fallback (Yahoo) used. Stooq's adjustment is therefore **unverified**; the code labels anything from Stooq `price_only` and prefers a total-return source |
| B: crypto bars | `https://data.binance.vision/data/spot/monthly/klines/{SYM}/1d/{SYM}-1d-YYYY-MM.zip` (daily zips for a month with no monthly file) | used |
| B: min notional, lot step | `https://data-api.binance.vision/api/v3/exchangeInfo?symbols=["BTCUSDT","ETHUSDT"]` | used: NOTIONAL minNotional = **5.0 USDT** for both (not the 10 fallback); LOT_SIZE stepSize BTC 0.00001, ETH 0.0001 |
| rf | FRED `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3` | used, 1954-01-04..2026-10-08, 800 blank holiday rows, last 4.05 |
| PTAX, CDI | BCB SGS `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{1,12}/dados?formato=json&dataInicial=..&dataFinal=..` (9-year chunks; the API refuses windows over 10 years) | used, 2000-01-03..2026-09-30, 6718 rows each |

## 2. Coverage

| Instrument | Source | Adjusted | First bar | Last bar | Rows |
|---|---|---|---|---|---|
| SPY | yahoo | total_return | 2000-01-03 | 2026-09-30 | 6726 |
| EFA | yahoo | total_return | 2001-08-27 | 2026-09-30 | 6310 |
| IEF | yahoo | total_return | 2002-07-30 | 2026-09-30 | 6082 |
| GLD | yahoo | total_return | 2004-11-18 | 2026-09-30 | 5500 |
| DBC | yahoo | total_return | 2006-02-06 | 2026-09-30 | 5195 |
| BTCUSDT | binance_vision | none | 2017-08-17 | 2026-09-30 | 3332 |
| ETHUSDT | binance_vision | none | 2017-08-17 | 2026-09-30 | 3332 |

Yahoo history was requested from 2000-01-01 (a choice, not a source limit for SPY, which lists from 1993).

**Evaluable start (SPEC section 11.1: first date on which every instrument has >= 252 real bars before it):**
- **A: 2007-02-07** (DBC is the late lister, 2006-02-06). E = 4943 bars to 2026-09-30. 70/30 split by bars: IS 2007-02-07..2020-11-02, OOS 2020-11-03..2026-09-30. Note IS contains 2008 and the OOS does not.
- **B: 2018-04-26.** E = 3080 bars. 60/40 split: IS 2018-04-26..2023-05-17, OOS 2023-05-18..2026-09-30.
(Derived from the cached panel; the backtest-engineer's `make_split` is authoritative.)

## 3. Dividend check (Evidence)

Question: is the ETF source total return? **Yes for Yahoo.** Method: re-requested SPY with `events=div`, and for all 108 dividend events (2000-03-17..2026-09-18) compared the step in `adjclose/close` across the ex-date with `1 - dividend / previous close`. Maximum absolute error 7.2e-07. So the adjustment is exactly the dividends. SPY CAGR 2000-01-03..2026-09-30: price only 6.39%, adjusted 8.28% (about 1.9 points a year of dividends). A fixture check (`tests/test_sources.py`) covers the 2024-12-20 ex-date, where Yahoo reports 1.966 per share. I did not verify that figure against an independent publisher (insufficient data); the internal consistency above is the evidence. Stooq could not be tested (blocked).

## 4. Integrity findings (Evidence; reported, nothing dropped or edited)

- **Duplicates, non-monotonic dates, bad OHLC, non-positive prices, stale runs, zero volume: none** in any series. Crypto: no missing day in 2017-08-17..2026-09-30, both pairs.
- **ETF gaps (12), all genuine market closures, not defects:** 2001-09-17 (after 9/11, 7 calendar days, SPY and EFA only; the others list later), 2007-01-03 (Jan 2 2007 national day of mourning), 2012-10-31 (Hurricane Sandy closures). Cross-ETF check: no day where >= 3 peers have a bar and one does not. Interpretation of the closure causes is from general knowledge, not fetched.
- **Outliers (17, threshold |log return| 0.10 ETF, 0.25 crypto), kept:** ETFs cluster in 2008-09/10 (SPY 2008-10-13 +13.6%, EFA 2008-10-13 +14.7%), 2020-03-12/16, GLD 2008-09-17 and 2026-01-30 (-10.8%). Crypto: BTC 2020-03-12 (-0.503), ETH 2017-09-14 (-0.252), 2020-03-12 (-0.591), 2021-05-19 (-0.325). All fall on known stress days; none looks like a bad tick. The 2026-01-30 GLD move was not cross-checked.
- Yahoo returned no null OHLC rows for the five ETFs in this run.

## 5. Defects and caveats, ranked by impact

1. **Survivorship / hindsight (Opinion):** the five ETFs and BTC/ETH were chosen knowing they survived. Binance's archive lists only currently available pairs; delisted pairs are not available (flagged, not fixable).
2. **Stooq blocked**, so the primary source in the SPEC could not be used or verified. Single-source dependency on Yahoo (an unofficial, undocumented endpoint that can change without notice) for all of A. No second source was used to cross-check prices.
3. **Yahoo adjusted history changes whenever a new dividend is paid**, so A is re-downloaded in full each fetch (cheap). A cache written on different days can differ slightly in early history; the manifest stores `fetched_at` and sha256.
4. **B minimum notional is today's exchangeInfo (5 USDT) applied to all history** (SPEC 11.10); real history differed.
5. **CDI forward fill:** SGS 12 is per Brazilian business day. `Aux.cdi_daily` is forward-filled as the SPEC says, so compounding it over every calendar day (B) overstates CDI by about 365/252. Use the added `Aux.cdi_business_day` mask to compound only on real observations.
6. **DTB3** is a discount-basis yield; used as is (SPEC 11.8).
7. Weekday/volume subtleties of Binance daily bars: the 00:00 UTC day, volume in base asset; USDT is not USD (stablecoin depeg risk is not modeled).
8. FRED hung when a request carried `Accept: */*`, and when the `cosd/coed` query was used; the code sends only a User-Agent and downloads the full file.
9. Tax, country and licensing: unknown, not assessed.

## 6. How to reproduce
`uv run algotrade fetch --market all` (about 4 minutes, mostly polite 0.25 s spacing over ~230 Binance files per pair), `uv run algotrade status`, `uv run python tools/record_fixtures.py` (re-record fixtures). Raw issue lists: `data/bars/{A,B}/issues.json` (git-ignored).
