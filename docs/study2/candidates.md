# Study 2 candidates: scored (strategy, market) pairs

Phase 1 of study 2, author: quant-economist agent, 2026-10-11. Inputs: `docs/study2/strategy-survey.md` (**S2**, cited
"F#" or "K#" for key finding), `docs/study2/market-survey.md` (**M2**, cited "§#"), study 1's `reports/VERDICT.md`
(**V**) and `docs/candidates.md` (**C1**). No new external facts. Technical and economic analysis, not financial
advice. Owner: Brazil resident, ~US$300 ≈ R$1,500 (M2 header), paper/backtest only. **Tax situation is unknown.** The
tax rules below are mostly secondary sources (M2 §5), so they are open questions, not facts about the owner.

## 1. Findings ranked by impact

1. **We do not expect any candidate to beat net-of-tax CDI with a drawdown the owner can accept.** *Evidence:* CDI
   is 13.65%/yr (M2 §4). Over 2001–2026 the B3 market beat the risk-free rate by only 0.89%/yr, with a −57.3% drawdown,
   and over 2021–2026 it lost 6.59%/yr against it (S2 K1). *Opinion:* the only family with a strong record (B3
   momentum) might clear the hurdle on 25-year averages. It does so with 50-month underwater spells (S2 F1), and the
   owner asked for "a couple of weeks". **Stop is a legitimate, evidence-backed recommendation.**
2. **There is no clean historical out-of-sample period for 2001–2026.** The researcher computed sub-period statistics
   on NEFIN 2001–2026 (S2 K5, F1), so the momentum hypothesis has already been seen on those years. The only unseen
   history is **1995–2000 in COTAHIST** (M2 §2: since 1986, avoid pre-1995). After that comes forward paper trading,
   which is slow (section 4).
3. **Tax and fixed fees, not exchange fees, decide the net result.** B3 costs 0.055% per round trip (M2 §2). Stock
   sales of at most R$20k a month are exempt (secondary, M2 §5), so a stock rule could be tax-free, while CDB yields
   are taxed 22.5→15%. ETFs pay 15% with no exemption. A fixed R$10 per order would cost ≈ 80%/yr at our size
   (section 5).
4. **Crypto and futures are out for this owner** on venue rules, the hurdle, or leverage (M2 §1.2–1.3, §1.6).

## 2. Hurdle and benchmarks

| Baseline | Gross | After tax (Opinion, arithmetic) | Max drawdown |
|---|---|---|---|
| CDI (CDB / Tesouro Selic) | 13.65%/yr (M2 §4) | 13.65 × (1 − 0.225) = **10.58%** if held ≤180 days; × 0.85 = **11.60%** if held >720 days | ≈0 |
| 50% market + 50% risk-free, 2001–2026 | 13.39%/yr (S2 F9) | ≈ 11.7% if the equity half is held as exempt stocks; ≈ 10.6% via a 15%-taxed ETF (additive approximation) | −31.7%, underwater 15.8 months |
| Same mix, 2021-07 to 2026-07 | 9.02%/yr (S2 F9) | ≈ 8% (approximation) | −10.0%, underwater 14.2 months |

- **Hurdle used below:** net CDI of **10.6–11.6%/yr**. LCI/LCA are exempt (S2 F7), but their rate is insufficient
  data and could raise the hurdle.
- **Benchmark:** the 50/50 CDI + equity mix, after tax. A candidate must beat net CDI on return and the mix on
  Sharpe *and* drawdown, as study 1's criterion 8 required (V §1).
- *Evidence:* even the passive mix broke the owner's drawdown wish (S2 F9).

## 3. Scored matrix

Weights are unchanged from study 1 (C1 §2): edge after costs **25**, robustness **15**, risk of ruin **15**, solo
fit **15**, free data **10**, build effort **10**, capacity **10**. Scores run 1–5, where 5 is best (low ruin, easy
build).

| Pair | Edge | Robust | Ruin | Fit | Data | Build | Cap. | **Weighted** | Key citations |
|---|---|---|---|---|---|---|---|---|---|
| 1. Long-only 12-1 momentum, B3 fractional | 3 | 3 | 4 | 4 | 3 | 2 | 4 | **3.30** | S2 F1, K2; M2 §2 (fees, COTAHIST unadjusted) |
| 2. Low-vol stock selection, B3 (own build) | 2 | 2 | 4 | 4 | 3 | 3 | 4 | **3.00** | S2 F2 (mixed; LVOL11 exists) |
| 3. Turn-of-month on BOVA11 | 1 | 1 | 4 | 4 | 4 | 5 | 5 | **3.00** | S2 F5 (2012–22: only an April effect); ETF taxed 15% |
| 4. Value/quality, B3 | 2 | 2 | 4 | 4 | 1 | 2 | 4 | **2.70** | S2 F3 (HML −7.05%/yr 2009–16) |
| 5. Crypto funding carry (measurement) | 1 | 2 | 2 | 3 | 5 | 3 | 4 | **2.50** | S2 F7; M2 §3, §1.3 |
| 6. Short-term reversal, B3 | 1 | 1 | 4 | 3 | 3 | 3 | 3 | **2.35** | S2 F4 (no effect found) |
| 7. Crypto cross-sectional momentum | 1 | 1 | 2 | 3 | 4 | 3 | 3 | **2.15** | S2 F10 |
| 8. Trend on WIN/WDO minis | 2 | 3 | 1 | 2 | 1 | 2 | 1 | **1.80** | M2 §2 (28–33x leverage); V (trend NO-GO) |
| 9. Pairs, B3 | 2 | 1 | 2 | 1 | 3 | 2 | 1 | **1.70** | S2 F6 (needs borrowing) |
| 10. Covered calls, BOVA11 | 1 | 1 | 3 | 1 | 1 | 2 | 1 | **1.40** | S2 F8 |

- *Sensitivity:* with equal weights, turn-of-month scores highest (3.43), then momentum (3.29) and low-vol (3.14).
  Turn-of-month is easy to build but has no edge, so the edge weight decides the order. That is a reason for caution,
  not a contradiction.
- CDI, the 50/50 mix, LVOL11 and BOVA11 are benchmarks, not scored as alpha (S2 F9, F2).

## 4. Multiple testing and out-of-sample data

- **Variant cap (Opinion):** a hard cap of **4 study-2 variants, never more than 6** (S2 K5 suggests ≤6). That makes
  **24 + 4 = 28** trials, at most 30, in the deflated-Sharpe correction. Each extra variant raises the bar. Study 1's
  in-sample rank correlation of 0.03 (V §4) shows that more variants bought nothing.
- **Clean data, options:**
  1. **Held-back 1995–2000 (COTAHIST):** about 6 years that we have not looked at. Caveats (Opinion): it is close to
     the Real plan, it includes the 1997–99 crises, liquidity was thin, and published studies covering 1995 onwards
     exist (S2 F1 [3]), so the data is clean of our own looks but not of the literature. Expected sampling error at
     Sharpe 0.5 (V §2 formula): √(1.125/6) ≈ **±0.43**. That gives a verdict in weeks, after the build.
  2. **Forward paper only:** one rebalance a month. The error is about ±1.0 Sharpe after 1 year and ±0.5 after
     4 years. A statistical answer would take **years**. Forward paper only tests the plumbing and the tracking.
- **Implication:** in-sample 2001–2026, a one-shot out-of-sample run on 1995–2000, then 6–12 months of forward paper
  as an operational check. If 1995–2000 is rejected, study 2 cannot give an answer within a reasonable time.

## 5. Top candidates

General assumptions (all **Opinion**): monthly rebalancing, fills at the next bar, all in BRL (no FX). The B3 fee is
0.0274% per side (M2 §2). Fractional-market spread `s` is **insufficient data** (M2 §2: liquidity "drastically
lower"), so I show `s` = 0.05% and a pessimistic 0.25% per side. `T` is the number of full-book round trips per
year, which is insufficient data; I use 3 and 6. Cost = T × 2 × (0.0274% + s).

### Candidate 1: long-only B3 momentum, 5–10 names, fractional shares

- **Gross edge (Evidence → Opinion):**
  - NEFIN WML, long-short and gross: 15.04%/yr (2001–26) and 16.93%/yr (2017–26). The market returned 13.06%/yr
    (S2 K1, K2).
  - λ, the share of WML a long-only handful captures, is **insufficient data**; the study must estimate it.
  - Total return ≈ market + λ·WML. At λ = 0.5 that is ≈ 20.6%/yr. With study 1's 58% post-publication haircut
    (C1 §4), it is 13.06 + 0.5 × 15.04 × 0.42 ≈ **16.2%**.
  - 2021–26 market ≈ 12.31 − 6.59 ≈ 5.7%/yr (S2 F9, K1; additive approximation).
- **Costs:** 0.46–0.93%/yr at s = 0.05%, and **1.66–3.33%/yr** at s = 0.25% (T = 3–6).
  - Brokerage is zero at most brokers (secondary, M2 §2). One broker charges a R$10 minimum per fractional
    *day-trade* order (M2 §2). If a fee like that applied to swing orders, 10 orders a month would cost R$100, ≈ 80%
    of R$1,500 a year: fatal.
- **Tax:** probably 0%, if this counts as swing trade and monthly sales stay ≤ R$20k (≈R$750 here). This is
  secondary (M2 §5) and must be confirmed.
- **Net vs net CDI (Opinion):**
  - Long run, haircut, worst costs: 16.2 − 3.3 ≈ **12.9% vs 11.6%**, ahead by ≈1.3 pts.
  - On 2021–26 conditions: 5.7 + 0.5 × 16.93 × 0.42 − 3.3 ≈ **6.0% vs 10.6–11.6%**, which loses.
- **Break-even:** λ·WML(net of haircut) > hurdle − market + costs. That is **> ≈1.8%/yr** in a 2001–26-like market,
  but **> ≈9.2%/yr** in a 2021–26-like market.
- **Killed by:**
  - drawdowns: market −57.3%, WML −46.5%, 52.8 months underwater (S2 K1, F1);
  - a handful of names failing to track the tercile (S2 F1);
  - fractional spreads, or any per-order fee;
  - the build cost of adjusting COTAHIST for dividends and splits and keeping delisted names (M2 §2);
  - mixed academic evidence (S2 F1 [3][4]).
- **Baseline:** the 50/50 mix after tax, BOVA11 (taxed 15%), and net CDI.

### Candidate 2: low-vol stock selection on B3 (could be a pre-registered variant of candidate 1's engine)

- **Gross edge:** **insufficient data**. The studies are qualitative and the volatility sort is inconclusive
  (S2 F2). One year of LVOL11 (40.6% vs 35.0%, 2025, third-party) is an anecdote.
- **Costs:** low turnover (the index rebalances every 4 months, S2 F2), so T ≈ 3 gives ≈ 0.5–1.7%/yr. Tax is
  probably 0% as stocks, versus 15% plus a 0.50%/yr fee for LVOL11.
- **Net vs net CDI / break-even:** it needs to beat the market by ≳ 0 pts on 2001–26 numbers, but by ≈ 6–7 pts on
  2021–26 numbers (11.6 − 5.7 + costs). The probability is insufficient data.
- **Killed by:** it adds little over buying LVOL11 (S2 F2); its drawdown is equity-like (Brazilian figure:
  insufficient data); it shares candidate 1's data build.
- **Baseline:** LVOL11 after fee and tax, and the 50/50 mix.

### Candidate 3: crypto funding carry (listed to close it, not to recommend it)

- **Gross:** ≈10.95%/yr on notional, which is **4.4–5.3%/yr on capital** (S2 F7). Offshore tax is 15%/yr (M2 §5,
  secondary).
- **Break-even:** F > 2r + 0.3k (C1 §4). At r = 11.6%, funding must exceed **≈23.5%/yr**. The basis was 20–25% at
  its 2024 peak and ~10% by mid-2025 (S2 F7, secondary).
- **Killed by:** perps have been unavailable to Brazil since 2021, and the CVM proceeding (M2 §1.3); the 2026-10-30
  and 11-06 rules (M2 §1.2); venue default. **Drop.**

## 6. Recommendation (Opinion)

1. **Default: stop.** Hold net CDI or a passive mix. That is the conclusion study 1 also reached (V §7). No candidate
   is *expected* to beat net CDI with acceptable drawdowns, and none can meet "a couple of weeks" underwater.
2. **If the owner wants to continue anyway:** one study of **candidate 1**, with candidate 2 as a declared variant,
   **4 variants maximum**, in-sample 2001–2026, one-shot out-of-sample 1995–2000, then 6–12 months of forward paper.
   The pass criteria must include beating net CDI *after tax* and the 50/50 mix on Sharpe and drawdown. Expect a NO-GO.

## 7. Questions for the owner at GATE 1

1. Stop now, or run one capped study (candidate 1, ≤4 variants)?
2. No equity strategy surveyed recovers within "a couple of weeks"; the evidence shows 15–53 months. Will you accept
   multi-year drawdowns, or does that rule out study 2?
3. Which safe product is your real alternative (CDB, Tesouro Selic, LCI/LCA)? It sets the hurdle.
4. Will you confirm with an accountant or your broker that fractional swing trades are commission-free and that the
   R$20k stock exemption applies to you?
5. Do you accept 1995–2000 as the only held-back out-of-sample period, knowing that forward paper alone would take
   years?
6. How many hours a week can you give, and over what horizon? (Still not given.)
7. Shall we drop crypto entirely for study 2?
