# Success criteria (pre-registered)

Phase 2, author: quant-economist agent, 2026-10-11. **No backtest has been run and no strategy code exists.**
Inputs: `context.md` (owner answers, GATE 1), `docs/candidates.md` (**C**), `docs/strategy-survey.md` (**SS**),
`docs/market-survey.md` (**MS**). Technical and economic analysis, not financial advice. Brazilian tax treatment of
these gains is an **open question for the owner**. These rules are frozen once any result exists (CLAUDE.md rule 5).

## 1. Universe, data, period

| | A: US ETFs | B: crypto spot |
|---|---|---|
| Instruments | SPY (US equity), EFA (developed ex-US equity), IEF (7-10y Treasuries), GLD (gold), DBC (broad commodities) | BTCUSDT, ETHUSDT (Binance spot) |
| Why | Five liquid asset classes. Trend needs low-correlated markets (SS F1 [5]). Five is the smallest set that still diversifies, and $300 / 5 = $60 per sleeve | Most liquid pairs and best free history (MS §1.3, §3). Owner accepts crypto risk |
| Source (free, keyless) | Daily OHLC adjusted for splits **and dividends** (total return). Candidates: Stooq CSV, then the Yahoo chart endpoint. Neither is in the surveys, so the data-engineer must verify | `data.binance.vision` daily `1d` klines (MS §3, [S6]) |
| Period | First date on which every ticker has ≥ 252 valid bars after its first bar, to **2026-09-30** | Same rule, to **2026-09-30** |

- The data-engineer verifies each source: adjustment, gaps and start dates. If the available period differs from what
  is expected, the split rule in §2 still applies mechanically. If only price-return data exists for A, the strategy
  and the benchmark both use it, and the report flags it.
- **Survivorship and hindsight (Opinion).** All five ETFs were chosen today, knowing they survived. BTC/ETH are
  chosen *because* they are the top two today, which is a strong hindsight bias. Binance's archive does not say
  whether it includes delisted pairs (MS §3). Venue failure is not in any backtest (SS F6).
- Auxiliary series (keyless, to be verified, not in the surveys): the USD 3-month T-bill (FRED `DTB3`), and from BCB
  SGS the USD/BRL PTAX rate (series 1) and the daily CDI (series 12).

## 2. Split and walk-forward

- The first 252 bars are indicator warm-up only. The rest is the evaluable period E.
- **A:** in-sample (IS) = the first 70% of E's bars; out-of-sample (OOS) = the last 30%.
  **B:** IS = the first 60%; OOS = the last 40%. B's history is shorter, and the OOS period must hold enough trades.
- **Walk-forward inside IS:** split IS into 5 equal consecutive blocks. For k = 2..5, choose the variant with the
  best net Sharpe on blocks 1..k−1 (expanding window), then trade it on block k. The concatenated block 2..5
  returns are the **WF series**.
- **Final selection:** the variant with the highest net Sharpe over the full IS period. Ties go to the longer
  lookback, then monthly rebalancing.
- **OOS is touched once**, in one logged run: the selected variant at base costs, the same variant at doubled costs,
  and the benchmark. No re-selection or retuning is allowed after it.

## 3. Strategy family, grid, variant cap

- **Signal (per asset, long-only, decided on the close of bar t):** either **TSMOM** (long if the L-bar return > 0)
  or **SMA** (long if close > SMA(L)). Otherwise the sleeve is in cash. There is no shorting: B is spot-only and
  shorting is impractical for a $300 account.
- **Sizing (fixed, not tuned; Opinion):** each asset gets a 1/N sleeve. Sleeve weight = min(1, σ*/σ_i), where σ_i
  is the annualised stdev of the last 60 daily log returns (×√252 for A, ×√365 for B). σ* = **12%** for A and
  **40%** for B. No leverage, so gross exposure is ≤ 100%. Idle cash earns 0 (pessimistic).
- **Execution:** fill at the **open of bar t+1**. A's open is adjusted by the same factor as the close. B's daily
  bar closes at 00:00 UTC. A sleeve is traded only if |Δweight| ≥ 2% of equity, except entries and exits, which
  always trade.
- **Simulation scale:** start equity is **$300**. A trade below the minimum order size is skipped (see §4).

| Parameter | Grid |
|---|---|
| Signal | {TSMOM, SMA} |
| Lookback L (bars) | {63, 126, 252} |
| Rebalance | {weekly (first bar of the week), monthly (first bar of the month)} |

**Hard cap: 12 variants per market (24 in total).** Each one is logged in `reports/variants.md`. A bug-fix rerun of
an identical configuration does not count, but any new parameter, value or rule does, and the cap does not allow it.
ETF rotation (C §4) is **excluded** to keep the grid small.

## 4. Cost model

| | A (Alpaca-type, $0 commission) | B (Binance spot, VIP 0) |
|---|---|---|
| Commission | $0 (MS §4, [S13]) | 0.10% per side taker, no BNB discount (MS §3, [S4]) |
| Regulatory fees | Sells: SEC 0.00206% ([S15]) + FINRA TAF $0.000119/share, max $5.95 ([S13b], may be stale) | none |
| Slippage (Opinion, pessimistic) | **0.10% per side** (typical spreads are insufficient data, MS §2) | **0.05% per side** (one-tick BTC spread snapshot, MS §2) |
| Round trip | ≈ 0.20% | ≈ 0.30% (C §4) |
| Minimum order | Fractional shares are **required** at $60 per sleeve. The broker's fractional minimum is insufficient data (MS §8), so use **$1** as a placeholder | Read the public `exchangeInfo` notional filter. If unavailable, use **$10** (Opinion placeholder) |
| Not used | Margin, shorting | Perps (a long position pays ~10.95%/yr funding, SS F6) |

**Stress run:** every fee and slippage figure ×2 (A ≈ 0.40%, B ≈ 0.60% per round trip).

## 5. Benchmarks and the Brazilian hurdle

- **A:** equal-weight buy-and-hold of the 5 ETFs, rebalanced at the first open of each month, with A's costs.
- **B:** 50/50 BTC/ETH, rebalanced monthly, with B's costs.
- Both benchmarks start at $300, cover the same OOS window and follow the same minimum-order rule.
- **Currency approach.**
  1. **Pass/fail is judged in USD.** Sharpe is computed on returns in excess of the USD T-bill. Under covered
     interest parity, a hedged USD position earns the USD rate, so the T-bill is the USD-equivalent of CDI for the
     *edge* question. If `DTB3` is unavailable, raw returns are used and the report flags it.
  2. **Reported "economic viability" flag (BRL):** convert the OOS equity curve to BRL with PTAX, then compare the
     BRL CAGR with compounded CDI over the same dates. The 2026-10-11 reference rate is Selic **13.75%/yr**
     (context.md, advfn link). The comparison is before tax on both sides; the tax rules are open.
- **CDI is a flag, not pass/fail (Opinion).** The BRL comparison is dominated by USD/BRL moves and the
  interest-rate differential, not by the engine. Whatever the result, the owner's real alternative is CDI, and a
  red flag means "the evidence says to keep the money in CDI". **The owner may make it pass/fail at GATE 2, before
  any result exists.**

## 6. Pass/fail thresholds (all net of costs, OOS unless stated)

**Drawdown honesty.** "A couple of weeks" will almost surely **not** be met. Diversified trend following once took
**45 months** from peak to recovery (SS F1 [6]) and went through a "dismal" 2010-2018 (SS F1 [7]). Any strategy that
holds risk spends months under water. The threshold below is realistic, **not** what the owner asked for. **The
owner must explicitly accept this mismatch at GATE 2.**

| # | Criterion | A | B |
|---|---|---|---|
| 1 | Annualised Sharpe (excess of T-bill) | ≥ **0.40** | ≥ **0.50** |
| 2 | Max drawdown (daily equity) | ≤ **20%** | ≤ **35%** |
| 3 | Longest underwater period (an unrecovered one counts to the end of OOS) | ≤ **18 months** | ≤ **18 months** |
| 4 | Completed round trips (flat → long → flat, per asset) | ≥ **20** | ≥ **12** |
| 5 | Doubled costs: excess return > 0 (Sharpe > 0) | required | required |
| 6 | Deflated Sharpe ratio of the selected IS variant (Bailey & López de Prado 2014, SSRN 2460551, method reference, not accessed this phase), with N = variants tried (≤ 12) | ≥ **0.90** | ≥ **0.90** |
| 7 | WF series (IS) Sharpe | > **0** | > **0** |
| 8 | Beats the benchmark: Sharpe ≥ benchmark Sharpe **and** max drawdown ≤ benchmark max drawdown | required | required |

- **Separate verdicts:** each market PASSES only if all 8 criteria hold. Otherwise it FAILS (NO-GO for that market).
  The OOS run happens even after a failure of criterion 6 or 7, and is reported for the record.
- **Reported, not pass/fail:** CAGR, the CDI flag (§5), the share of days under water, median drawdown length,
  turnover, and exposure.
- **Why these numbers (Opinion):** the net Sharpe of trend following was 0.62 over 2000-2013 on 58 futures
  (SS F1 [6]). Five ETFs diversify less, and published edges shrink (SS K2 [1]), so 0.40 is a modest bar. Even
  that is only ~1 standard error over a ~6-year OOS, which is why criteria 6 and 7 back it up. B gets a higher
  Sharpe bar and a looser drawdown bar because crypto shows strong TSMOM (SS F1 [18]) and is much more volatile.

## 7. What $300 means

- A at $300: five $60 sleeves need **fractional shares**. Whether a Brazil resident can get a live account is
  unconfirmed (context.md), and paper is unaffected.
- Expected dollars (Opinion, from C §4): at +4.6%/yr net that is ≈ **$14/yr**. A trendless decade gives ≈ **−$1/yr**.
  The pass thresholds allow drawdowns of **$60 (A)** and **$105 (B)**.
- CDI at 13.75% on the same capital ≈ **$41/yr** before tax (context.md rate, applied to $300; ignores FX).
- Minimum orders and skipped small trims will make the $300 result differ from a scaled-up one, and the report
  shows how much.
- **The value of this tryout at this size is the evidence, not the income.**

## Changelog
- Pre-registered 2026-10-11, before any backtest.
