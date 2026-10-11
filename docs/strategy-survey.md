# Strategy survey: what a retail solo developer can realistically run

Author: strategy-researcher agent. Date: 2026-10-11. All sources accessed 2026-10-11; numbered list at the end.
Scope: paper/backtest only. This is technical and economic analysis, not financial advice. **Open questions for the
owner:** country of residence (it decides which venues are available, especially crypto derivatives, and how short-term
gains are taxed), capital (assumed: a few thousand USD), and horizon.

## Key findings (ranked by impact)

1. **Speed-based families are closed to us.** *Evidence:* in HFT, differences in relative latency "account for large
   differences" in trading performance, and firms that moved up the latency ranking through colocation upgrades did
   better [9]. Retail Brazilian futures day traders who kept going 300+ days: 97% lost money, 0.4% earned more than a
   bank teller [10]. This rules out market making, cross-exchange arbitrage and fast news trading.
2. **Published edges shrink.** *Evidence:* across 97 predictors, returns were 26% lower out-of-sample and 58% lower
   after publication [1]. A new factor needs t > 3.0, not 2.0 [2]. Anomalies with more than ~50% monthly turnover
   mostly do not survive trading costs [3]. *Opinion:* expect any backtest we produce to overstate live results, and
   prefer slow, low-turnover signals.
3. **What survives is slow risk premia, not alpha.** Trend following, carry (crypto funding) and rebalancing pay you
   to hold risk that other people want to shed. They do not pay you for being clever, and they come with long
   drawdowns.

## Families

**1. Trend following / time-series momentum (TSMOM).** *Edge:* under-reaction followed by delayed over-reaction.
On the other side: hedgers and other non-profit-seeking flows [5][6]. *Evidence:* every one of 58 liquid futures showed
significant TSMOM [5]. Across 1880–2013, simulated returns were 14.9%/yr gross and 11.2%/yr net of 2/20 fees and
estimated costs, at 9.7% volatility (Sharpe 0.77 net). For 2000–2013 the figures were 7.9% net and Sharpe 0.62. The
worst drawdown was −26.3%, taking 45 months from peak to recovery [6]. Performance over 2010–2018 was "dismal" relative
to history because there were few large market moves [7]. One critique says much of the result comes from volatility
scaling rather than the trend signal itself [4] (secondary summary). Crypto shows strong TSMOM too (BTC/ETH/XRP)
[18]. *Decay:* slow, because the edge is behavioural plus hedging pressure. *Capital/latency:* daily bars, minutes of latency
are fine. Diversifying across futures may need more capital than a few thousand USD (contract sizes: insufficient data,
for market-researcher). ETFs or crypto spot work at small size. *Failure modes:* trendless years, whipsaw, crowding.
**Verdict: Yes**, with modest expectations.

**2. Cross-sectional momentum.** *Edge:* the same under-reaction, applied by ranking assets against each other [11].
*Evidence:* momentum is negatively skewed. In July–August 1932 the loser decile returned 232% against 32% for the
winners, and in March–May 2009 it was 163% against 8% [8]. A dynamic, volatility-aware version roughly doubles the
Sharpe [8]. Momentum is among the strongest signals in machine-learning studies too [13]. *Failure modes:* crashes in
rebounds, turnover costs [3], and the cost of shorting for small accounts. **Verdict: Marginal.** A long-only rotation
across ETFs (sectors or countries) is feasible. A stock long/short decile portfolio is not, at small capital.

**3. Mean reversion (short-term reversal).** *Edge:* the price impact of liquidity demand reverses, so the trader is
paid for providing liquidity. *Evidence:* most of the cost drag comes from small caps. Restricted to large caps with a
low-turnover construction, net returns were about 30–50 bp/week [12]. Those are institutional cost estimates, and retail
spreads plus latency are worse. *Failure modes:* "cheap" stocks that keep falling, and costs. **Verdict: Marginal**,
for daily-bar large-cap/ETF versions only. Intraday versions: No (see finding 1).

**4. Statistical arbitrage / pairs.** *Evidence:* up to ~11%/yr excess return over 1962–2002 [14]. Do & Faff confirm a
"continuing downward trend in profitability" but find it still does well in prolonged turbulence [15]. A 2004–2009
replication across the US and Asia found no consistent positive excess returns (thesis, weak source) [14].
*Needs:* cheap shorting and many pairs. *Failure modes:* structural breaks, where the spread never comes back.
**Verdict: Marginal → No** for net profit. It is fine as a learning exercise.

**5. Market making.** *Edge:* earning the spread minus adverse selection. On the other side: impatient takers.
*Evidence:* revenues go to the fastest. New entrants are slower, earn less, and are more likely to exit [9].
**Verdict: No** (latency, and fee tiers that reward volume).

**6. Funding-rate / basis carry (crypto perps vs spot).** *Edge:* leveraged retail longs pay for exposure while
arbitrage capital is scarce [16]. *Evidence:* carry averages "above 10% annually" and can reach "up to 60% p.a.". A high
carry predicts crashes, and the trade is "risky due to spikes in margins and liquidations amid drawdowns" [16]. On
Binance the interest component is 0.01% per 8 h, and funding equals exactly 0.01% while the premium index stays between
−0.04% and +0.06% [17]. That is about 11%/yr if the band holds all year (*my calculation*; real funding varies and can
turn negative). Fees: spot 0.10% maker/taker at VIP 0 [19]. Futures maker is 0.02%, with taker 0.04–0.05% depending on
the Binance page [20]. So entering and exiting both legs costs roughly 0.3% (*my calculation*), about 10 days of
baseline funding. *Decay:* a search snippet reports that extreme funding fell ~90% (BitMEX), but **I could not verify it**
(page 404). *Failure modes:* exchange default (counterparty risk is not compensated in backtests), auto-deleveraging,
negative funding, and legs breaking on liquidation. Venue access depends on country. **Verdict: Marginal**: it is
mechanically simple and works at small size, but the tail risk is in places a backtest cannot see.

**7. Cross-exchange arbitrage.** *Evidence:* the large deviations were across countries, behind capital controls, and
smaller within a country [21]. *Opinion:* the deviations we could reach without moving capital across borders are
taken by low-latency firms, and the ones across borders need fiat rails we probably lack. **Verdict: No.**

**8. Event / news-driven.** *Evidence:* post-earnings drift "non-existent since 2006 for large stocks", and only
recently gone in microcaps [22]. This is disputed: two 2025 papers argue PEAD survives, and a rebuttal attributes the
difference to research design [22]. Fast news trading is a latency game (finding 1). Free point-in-time earnings
data is also hard to get. **Verdict: No** (Marginal for a slow, earnings-based version if clean data exists:
insufficient data).

**9. Volatility strategies.** *Edge:* the variance risk premium, meaning option buyers pay for insurance [23]. *Failure
mode:* XIV lost about 96% on 5 Feb 2018 and was terminated [24]. Buying volatility is the losing side of the same
premium. *Capital:* option margin and contract sizes are restrictive for a few thousand USD, and options access depends
on country. **Verdict: Marginal** for defined-risk short-vol (spreads) in a backtest. **No** for naked short-vol or
long-vol as a standalone.

**10. Machine-learning prediction.** *Evidence:* trees and neural nets "in some cases doubling" the performance of
regression strategies [13]. However, deep-learning profits come from hard-to-arbitrage stocks, shrink once microcaps,
distressed stocks or high-volatility periods are excluded, and "further deteriorate" with realistic costs [25]. Many
features plus a small sample means a high false-discovery risk [2]. **Verdict: No** as a standalone edge. It is Marginal
as a filter on top of a simple, economically motivated signal.

**11. Systematic portfolio rebalancing.** *Evidence:* none of 14 optimised models consistently beat 1/N
out-of-sample. Estimation error needs about 3,000 months of data to overcome with 25 assets [26]. *Edge:* none beyond
the risk premia and diversification. *Opinion:* this is the **benchmark** every candidate must beat after costs and
tax. **Verdict: Yes** (as the baseline, not as alpha).

## Summary table

| # | Family | Edge source | Latency | Min. capital | Decay | Worst-case pattern | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Trend / TSMOM | behavioural + hedgers [5][6] | days | low (ETF/crypto); higher for futures | slow | −26% DD, 45 mo [6]; flat decade [7] | **Yes** |
| 2 | Cross-sect. momentum | under-reaction [11] | days | low long-only | medium [1] | crash rebounds [8] | Marginal |
| 3 | Mean reversion | liquidity provision [12] | days (intraday: No) | low | fast, cost-bound [3] | falling knives | Marginal |
| 4 | Pairs / stat arb | temporary mispricing [14] | days | medium (shorting) | declining [15] | breakups | Marginal→No |
| 5 | Market making | spread | microseconds [9] | high | winner-takes-all | adverse selection | No |
| 6 | Funding/basis carry | scarce arbitrage capital [16] | minutes–hours | low | partly compressed (unverified) | exchange failure, liquidation | Marginal |
| 7 | Cross-exchange arb | segmentation [21] | ms + capital mobility | high | fast | transfer delays, controls | No |
| 8 | Event / news | under-reaction [22] | ms (news) / days (PEAD) | medium | gone/disputed [22] | data gaps | No |
| 9 | Volatility (short) | VRP [23] | days | medium–high | stable premium, fat tail | −96% in a day [24] | Marginal |
| 10 | ML prediction | nonlinear signals [13] | any | any | high, cost-sensitive [25] | overfitting [2] | No |
| 11 | Rebalancing (1/N, risk parity) | risk premia | days | very low | none (no alpha) | market drawdowns | **Yes** (baseline) |

## Ranked shortlist for this owner

1. **Trend following on a small universe of liquid ETFs and/or BTC/ETH spot, daily bars, volatility-scaled.** It has the
   strongest long-horizon evidence [5][6], free data, low turnover, and it works at small capital. Expect years of flat
   or negative returns [7].
2. **Crypto funding-rate carry (long spot + short perp), paper only.** It is simple and measurable from public funding
   histories, with an evidenced premium [16][17]. It depends on country, and its main risk (venue failure) is invisible
   to backtests.
3. **Long-only cross-sectional momentum / ETF rotation** with a buy/hold buffer to cut turnover [3]. It can be combined
   with #1.
4. **1/N or risk-parity rebalancing** as the mandatory benchmark [26].
5. (Research only) **Large-cap/ETF short-term reversal on daily bars** [12]. It is the most likely of the five to die on
   costs.

*How this changes with more capital (Opinion):* above roughly tens of thousands of USD, diversified futures trend
following becomes practical (the exact threshold is insufficient data and depends on contract sizes), defined-risk
option selling becomes feasible, and market-neutral stock momentum or pairs become possible. None of this changes the
"No" verdicts, because those come from latency and data, not capital.

## Sources (all accessed 2026-10-11)

1. McLean & Pontiff (2016), JF 71(1): https://Www.Gwern.net/doc/economics/2016-mclean.pdf ; https://afajof.org/issue/volume-71-issue-1/
2. Harvey, Liu & Zhu (2016), RFS / NBER w20592: https://nber.org/papers/w20592
3. Novy-Marx & Velikov (2016), RFS 29(1): https://ideas.repec.org/a/oup/rfinst/v29y2016i1p104-147..html ; https://www.nber.org/papers/w20721.pdf
4. Kim, Tse & Wald critique of TSMOM (secondary summary only): https://quantpedia.com/deconstructing-the-time-series-momentum-strategy/
5. Moskowitz, Ooi & Pedersen (2012), JFE 104: https://papers.ssrn.com/abstract=2089463 ; https://fairmodel.econ.yale.edu/ec439/jpde.pdf
6. Hurst, Ooi & Pedersen, "A Century of Evidence on Trend-Following Investing" (Fall 2014 AQR version; figures from its performance and drawdown tables): https://www.TrendFollowing.com/whitepaper/Century_Evidence_Trend_Following.pdf ; https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing
7. Babu et al. (2020), "You Can't Always Trend When You Want", JPM (summary only): https://alphaarchitect.com/trend-following-reality-you-need-trends-to-trend-follow/
8. Daniel & Moskowitz, "Momentum Crashes" (JFE 2016; NBER w20439 text, intro): https://www.nber.org/system/files/working_papers/w20439/w20439.pdf
9. Baron, Brogaard, Hagströmer & Kirilenko (2019), JFQA 54(3): https://ideas.repec.org/a/cup/jfinqa/v54y2019i03p993-1024_00.html ; https://erim.eur.nl/research/events/detail/4166
10. Chague, De-Losso & Giovannetti (2020), "Day Trading for a Living?": https://econpapers.repec.org/RePEc:fgv:eesptd:525 ; https://repositorio.fgv.br/items/e87d04fc-4b4c-4a56-ab5a-1c84c1afde1b/full
11. Jegadeesh & Titman (1993), JF 48(1) (abstract only): https://ideas.repec.org/a/bla/jfinan/v48y1993i1p65-91.html
12. de Groot, Huij & Zhou (2012), JBF 36(2): https://ideas.repec.org/a/eee/jbfina/v36y2012i2p371-382.html
13. Gu, Kelly & Xiu (2020), RFS 33: https://www.nber.org/papers/w25398.pdf
14. Gatev, Goetzmann & Rouwenhorst (2006), RFS: https://www.cxoadvisory.com/technical-trading/classic-paper-matched-pairs-trading/ ; replication thesis (weak source): https://thesis.eur.nl/pub/8530/Cummins,%20R.L.%20%28299180%29.pdf
15. Do & Faff (2010), FAJ 66(4): https://ideas.repec.org/a/taf/ufajxx/v66y2010i4p83-95.html
16. Schmeling, Schrimpf & Todorov (2023), "Crypto carry", BIS WP 1087: https://www.bis.org/publ/work1087.pdf
17. Binance, Introduction to Futures Funding Rates: https://www.binance.com/en/support/faq/360033525031
18. Liu & Tsyvinski (2021), RFS 34(6): https://ideas.repec.org/a/oup/rfinst/v34y2021i6p2689-2727..html ; https://papers.ssrn.com/abstract=3226806
19. Binance fee schedule (spot VIP 0): https://www.binance.com/en/fee/schedule
20. Binance Futures fee FAQ and API doc: https://binance.com/en/amp/support/faq/360033544231 ; https://developers.binance.com/docs/derivatives/usds-margined-futures/account/rest-api/User-Commission-Rate
21. Makarov & Schoar (2020), JFE 135(2): https://www.fmg.ac.uk/sites/default/files/publications/DP782.pdf ; https://dspace.mit.edu/handle/1721.1/130495
22. Martineau (2022), "Rest in Peace Post-Earnings Announcement Drift", CFR 11: https://ideas.repec.org/a/now/jnlcfr/104.00000122.html ; dispute brief: https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again
23. Carr & Wu (2009), "Variance Risk Premiums", RFS 22(3): https://ideas.repec.org/a/oup/rfinst/v22y2009i3p1311-1341..html
24. XIV termination, Feb 2018: https://www.etf.com/sections/news/inverse-vix-etn-shuts-down
25. Avramov, Cheng & Metzker (2023), Management Science 69(5): https://ideas.repec.org/a/inm/ormnsc/v69y2023i5p2587-2619.html ; https://papers.ssrn.com/abstract=3450322
26. DeMiguel, Garlappi & Uppal (2009), RFS 22(5): https://ideas.repec.org/a/oup/rfinst/v22y2009i5p1915-1953.html ; https://conference.nber.org/confer/2006/si2006/ap/uppal.pdf

**Not verified:** the BitMEX 2025 funding-rate reports (https://www.bitmex.com/blog/2025q2-derivatives-report, Q3
likewise) returned 404, so their "~90% drop in extreme funding" is excluded as evidence. The Han, Kang & Ryu
crypto-momentum-after-costs result was seen only in search summaries. The Jegadeesh-Titman monthly return figure was
not verified, so no number is quoted.
