# Candidates: scored (strategy, market) pairs

Phase 1, author: quant-economist agent, 2026-10-11. Inputs: `docs/strategy-survey.md` (**SS**, cited by family
number "F#" or finding "K#") and `docs/market-survey.md` (**MS**, cited by section "§#"). No new external facts.
Technical and economic analysis, not financial advice. Owner country, capital and horizon are **unknown**.

## 1. Findings ranked by impact

1. **Slow trend following is the only family with both strong evidence and a small-account fit** (SS F1, K3). It
   tops the matrix on US ETFs (3.90) and BTC/ETH spot (3.85). Expect it to lose to buy-and-hold in bull markets.
   Its realistic value is a smaller drawdown, not a higher return (SS F1, [6][7]).
2. **Venue fees decide the crypto variants.** A round trip costs ~0.30% on Binance spot and ~1.70% on Kraken spot
   (§3). At 12 round trips a year that is 3.6% vs 20.4% a year. On perps, a long trend position *pays* funding
   (~11%/yr at the baseline rate, SS F6), so perps only help the short side.
3. **Carry is simple, but its main risk is one no backtest shows** (venue failure, liquidation; SS F6). It is the
   only uncorrelated candidate, and the one most exposed to unverified access facts (§1.2, §7).

## 2. Scored matrix

Scores run 1-5, where 5 is best. For risk of ruin, 5 means low risk; for build effort, 5 means easy.
Weights: edge after costs **25**, robustness **15**, risk of ruin **15**, solo/no-co-location fit **15**, free data
**10**, build effort **10**, capacity **10**.

| Pair | Edge | Robust | Ruin | Fit | Data | Build | Cap. | **Weighted** | Key citations |
|---|---|---|---|---|---|---|---|---|---|
| A. Trend, US ETFs (Alpaca) | 3 | 4 | 4 | 5 | 3 | 4 | 5 | **3.90** | SS F1 [5][6][7]; MS §4, §1.3 (free data only since 2016) |
| B. Trend, BTC/ETH spot (Binance) | 3 | 3 | 4 | 5 | 5 | 4 | 4 | **3.85** | SS F1 [18]; MS §3 (0.10%), §1.3 |
| C. Long-only ETF rotation | 2 | 3 | 4 | 5 | 3 | 4 | 5 | **3.50** | SS F2 [1][3][8]; MS §4 |
| D. Trend, crypto perps L/S | 3 | 3 | 2 | 4 | 5 | 3 | 4 | **3.30** | SS F1, F6 (funding paid when long); MS §2 |
| E. Funding carry, spot + short perp (Binance) | 3 | 2 | 2 | 4 | 4 | 3 | 4 | **3.05** | SS F6 [16][17]; MS §2, §1.2 |
| F. Daily large-cap/ETF reversal | 2 | 2 | 4 | 4 | 3 | 3 | 3 | **2.90** | SS F3 [12][3]; MS §4 |
| G. Trend, CME micros / B3 minis | 3 | 4 | 2 | 3 | 1 | 2 | 3 | **2.70** | SS F1 [5]; MS §6, §7.6 |
| H. Trend, retail FX (OANDA) | 2 | 3 | 2 | 3 | 1 | 3 | 4 | **2.50** | SS F1; MS §5 (all costs unverified) |
| I. Intraday mean reversion, perps | 1 | 1 | 2 | 1 | 5 | 2 | 3 | **1.85** | SS K1, F3 ("Intraday: No"); MS §9 |

Benchmarks (1/N ETFs, buy-and-hold BTC/ETH; SS F11 [26]) are not scored as alpha. Families rated "No" are
excluded (SS F5, F7, F8, F10).
*Sensitivity:* with equal weights, A and B tie at 4.00, C scores 3.71 and E scores 3.14. The order holds.
*Unverified inputs:* E's access score assumes Binance is reachable, which is unverified for the EU (§1.2) and for
Brazil after ~2026-10-30 (§1.2, secondary). Bybit fees (§2) are not used anywhere. A and B rely only on verified
fees (Alpaca §4, Binance §3).

## 3. Asset classes for a small-budget solo developer (Opinion; depends on strategy and country)

1. **US stocks/ETFs**: $0 commission, free global paper account, free daily data, no leverage needed (§4). Weak
   points: live accounts for non-US residents are unconfirmed (§4, §7), and free data is IEX-only from 2016 (§1.3).
2. **Crypto spot (Binance-class venue)**: the best free history and small sizes (§1.3, §3). Weak points: at
   Kraken/Coinbase, fees kill any turnover; the asset is volatile; access depends on country (§3, §7).
3. **Crypto perps**: the lowest fees, shorting and carry (§1.1, SS F6). Weak points: liquidation, venue counterparty
   risk, and the most country blocks (§2, §7).
4. **Futures, including B3 minis**: cheap per contract (§6). Weak points: no free data, and a single contract is
   already leveraged (§7.6). This class is better at $25k+, or for a Brazil resident through B3.
5. **FX**: every cost figure is unverified, there is no free bulk data, and access depends most on country, with
   CVM stop orders against offshore brokers in Brazil (§5).

## 4. Top candidates

General assumptions (all **Opinion**): daily bars, fills at the next bar. Slippage is a pessimistic placeholder
`s = 0.05%` per side, because typical spreads are insufficient data beyond one BTC snapshot (§2). The cash yield
`r` is insufficient data; the owner supplies it.

### Candidate 1: volatility-scaled trend on a small US ETF set (pair A), with rotation C as a pre-registered variant

- **Gross edge (Evidence → Opinion):** Hurst, Ooi & Pedersen's 2000-2013 return is 7.9% net of 2/20 fees (SS F1
  [6]). Undoing the fees gives 7.9/0.8 + 2 ≈ **11.9% gross** (my inversion; the survey does not say whether the
  figure is excess of cash). That figure comes from 58 diversified futures, and a handful of ETFs is less
  diversified. Applying the 58% post-publication haircut (SS K2 [1]) as a stress gives 11.9 × 0.42 ≈ **5.0%**. In
  2010-2018 trend was "dismal" (SS F1 [7]), so treat ~0% as a realistic decade.
- **Costs:** one round trip costs 2s + SEC fee 0.00206% ≈ **0.10%** (§4). At 4 full portfolio turnovers a year,
  costs are 4 × 0.10 ≈ **0.4%/yr**. With IBKR's $1 minimum on a $1,000 order, add 0.1% per side (§4).
- **Net expectancy:** 5.0 − 0.4 ≈ **+4.6%/yr** in the stress case. In a trendless decade it is 0 − 0.4 =
  **−0.4%/yr**.
- **Break-even:** gross > 0.4%/yr at 4 turnovers, which is **> 10 bp per round trip**. Costs are not the binding
  constraint. Beating the benchmark is.
- **Killed by:** trendless years (SS F1 [7]), a −26% drawdown lasting 45 months (SS F1 [6]), too few ETFs to
  diversify, and only 10 years of free data (§1.3), which makes the out-of-sample period short.
- **Baseline to beat:** 1/N monthly-rebalanced buy-and-hold of the same ETFs (SS F11 [26]), compared on Sharpe and
  max drawdown, not just CAGR; plus cash at `r`.

### Candidate 2: volatility-scaled trend on BTC/ETH spot (pair B)

- **Gross edge:** crypto shows strong TSMOM (SS F1 [18]). Its magnitude is **insufficient data** in the surveys.
- **Costs:** one round trip costs 2 × 0.10% fee + 2s = **0.30%** (0.25% with the BNB discount) (§3). At 12 round
  trips/yr that is **3.6%/yr**; at 24 it is **7.2%/yr**. On Kraken a round trip is 2 × 0.80 + 0.10 = 1.70%, or
  **20.4%/yr** at 12 trips.
- **Net expectancy:** G − 3.6%/yr, where G is unknown. This is the number the backtest must estimate.
- **Break-even:** gross > **30 bp per round trip**, i.e. > 3.6%/yr at about one round trip a month.
  On Kraken/Coinbase it needs > 170 bp per round trip, which is not credible. Do not use perps for long exposure:
  the baseline funding of 0.01%/8h ≈ **10.95%/yr** is paid while long (SS F6 [17]).
- **Killed by:** whipsaw in choppy regimes, venue loss or a ban by country (§1.2), survivorship gaps in the archives
  (§3), and an exchange that pays no yield on idle cash (Opinion).
- **Baseline to beat:** buy-and-hold of 50/50 BTC/ETH rebalanced monthly on the same venue, with the same fees.

### Candidate 3: funding carry, long BTC spot + short BTC perp (pair E), paper/measurement only

- **Gross:** at the baseline rate, 0.01%/8h × 3 × 365 ≈ **10.95%/yr** on notional (SS F6 [17]); Hyperliquid's
  0.00125%/h gives the same 10.95% (§2). BIS measures an average "above 10%" (SS F6 [16]). Funding can be negative:
  the Bybit snapshot read −0.00477% (§2).
- **Costs:** entering and exiting both legs costs ≈ 0.30% (SS F6), which takes **10 days** of baseline funding to
  earn back.
- **Net on capital:** a 1x hedge needs ~2× notional in capital (Opinion). At one rotation a year:
  (10.95 − 0.3)/2 ≈ **5.3%/yr**; at four rotations: (10.95 − 1.2)/2 ≈ **4.9%/yr**. If the average is 10%:
  (10 − 1.2)/2 = **4.4%/yr**.
- **Break-even:** average funding F > 0.3% × rotations/yr to stay positive. To beat cash, F > 2r + 0.3k: every
  1 pt of local cash yield raises the hurdle by 2 pts of funding.
- **Killed by:** an exchange default, auto-deleveraging, liquidation of the short leg in a spike, persistent
  negative funding, compression of the premium (unverified, SS F6), and access (Binance EU/BR status unverified,
  §1.2).
- **Baseline to beat:** cash yield `r` in the owner's currency (insufficient data).

## 5. How it changes with country and capital (Opinion)

- **Brazil resident:** A remains available in paper (Alpaca paper is global). Live A is unconfirmed (§4). B and E
  depend on Binance obtaining BCB authorisation by ~2026-10-30 (unverified, §1.2). Hyperliquid is not restricted
  (§7.5), but its tax position cannot be assessed. B3 minis are the native futures route (§6). A high local cash
  yield raises every hurdle, especially E's (F > 2r).
- **US resident:** binance.com, Bybit and Hyperliquid are out (§7.2), so E is effectively unavailable among the
  venues surveyed (Binance.US was not researched). B would run on Kraken/Coinbase fees, so it is viable only at very
  low turnover. A is the clear first choice, and CME micros become feasible with more capital.
- **EU resident:** Binance reportedly halted (unverified, §1.2). Kraken's 0.80% fee pushes B to low turnover.
  Perps access through MiCA venues is unclear (§7.3). Whether US ETFs are accessible to EU retail is insufficient
  data in the surveys.
- **~$1k-5k:** A, B and E all work at small size. Futures (G) are out because one contract is too large (§7.6).
  Prefer Alpaca over IBKR, where the $1 minimum adds ~0.1% per side (§4).
- **~$25k+:** diversified futures trend (G) becomes practical, though the exact threshold is insufficient data
  (SS shortlist). IBKR's minimums become negligible. The PDT change (§1.4) is irrelevant to daily-bar candidates,
  and no score here rests on it.

## 6. Recommendation (Opinion)

Build **one trend engine** (pure, volatility-scaled TSMOM on daily bars) and run it on **Candidate 1 (US ETFs)**
and **Candidate 2 (BTC/ETH spot, Binance fee model)**. Include ETF rotation as a variant declared in advance.
Benchmark against 1/N and buy-and-hold. The code is shared, the data is free, and the costs are verified. Treat
**Candidate 3** as an optional measurement study from public funding history, only if the owner's country gives
access to a venue. Realistic expectation: low single-digit net returns, possibly negative over a decade, and likely
behind buy-and-hold in bull markets. A NO-GO is an acceptable outcome.

## 7. Questions for the owner at GATE 1

1. Country of tax and physical residence?
2. Starting capital (roughly), and is it money you can afford to lose entirely?
3. Time horizon, and how long can you tolerate being under water (the evidence shows up to 45 months, SS F1)?
4. Which candidate(s): 1, 2, both on one engine (recommended), or 3?
5. What cash yield can you get with no risk, in your currency? It sets the hurdle.
6. Is crypto venue/counterparty risk acceptable to you at all?
7. If you are not a US resident: will you check whether you are eligible for a live Alpaca account? (Paper works
   regardless.)
8. How many hours per week can you give this?
