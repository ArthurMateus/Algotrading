# Study 2 strategy survey: families not tested in study 1

Author: strategy-researcher agent. Date: 2026-10-11. All sources were accessed on 2026-10-11 and are listed at the
end. This survey builds on `docs/strategy-survey.md` (**SS1**) and does not repeat it. Study 1 tested volatility-scaled
long-only trend on ETFs and on BTC/ETH; both were NO-GO (`reports/VERDICT.md`).

**Owner (from `context.md`):** Brazil resident, ~US$300, paper/backtest only, free data, little weekly time, a short
drawdown tolerance. The hurdle is CDI/Selic (13.75%/yr). This is technical and economic analysis, not financial
advice. **Tax is an open question**: the rules quoted below come from secondary sources and must be confirmed.

## Key findings (ranked by impact)

1. **In Brazil, cash has paid about as much as stocks for 25 years.** *Evidence (my calculation from NEFIN data
   [1], 2001-01-02 to 2026-07-03, gross, no tax):*
   - The NEFIN market portfolio returned 13.06%/yr, against 12.06%/yr for the risk-free rate. Its max drawdown was
     −57.3%.
   - Rm−Rf compounded at 0.89%/yr. It was −6.59%/yr from 2021-07 to 2026-07.

   *Opinion:* any equity strategy for this owner has to beat a ~12%/yr near-riskless return, not zero. That is a
   much higher bar than in the US literature.
2. **Momentum is the one B3 factor with a strong, recent, free-data record.** *Evidence [1]:* NEFIN's WML
   (long-short, gross) returned 15.04%/yr over 2001–2026 (vol 16.8%, max drawdown −46.5%), and 16.93%/yr over
   2017–2026. It is the most promising family here, but:
   - the published series is long-short and gross of costs;
   - the owner can only hold a lumpy long-only version in the fractional market.
3. **The tax rules favour individual stocks over ETFs and short-horizon trading** (secondary sources [8][9]):
   stock sales up to R$20k a month are exempt (swing trade); ETF gains pay 15% with no exemption; day-trade gains
   pay 20%; CDB/Tesouro yields pay a regressive 22.5%→15%; LCI/LCA are exempt. *Opinion:* at $300 the monthly sales stay far below R$20k, so a stock-based rule could be **tax-free**, while CDI
   in a CDB is taxed. That partly offsets finding 1. Confirm with an accountant.
4. **Most other families fail for this owner on capital, shorting or decay, not on theory.** Pairs needs stock
   borrowing. Options come in contract lots. Funding carry is now below the CDI. Reversal and calendar effects have
   weak or fading Brazilian evidence.
5. **Multiple-testing budget and data contamination.** 24 variants are already spent. The NEFIN 2001–2026 history
   was *looked at* for this survey, even if only descriptively. *Opinion:* a study-2 test on B3 momentum should use
   few variants (≤ 6), and should treat a fresh forward paper period or held-back years as the only clean
   out-of-sample data.

## Families

**F1. Cross-sectional momentum on B3 stocks (long-only).**
- *Evidence:* NEFIN WML [1][2]:
  - Construction: eligible stocks have more than 80% of days traded and more than R$500k of daily volume. Each month
    they are sorted into terciles on t−12..t−2 returns, and the terciles are equal-weighted.
  - Results (my calculation): the gross return was positive in every sub-period: 15.2%/yr (2001–08), 12.6%/yr
    (2009–16), 16.9%/yr (2017–26). The longest underwater spell was 52.8 months.
  - Academic studies are mixed: Varga & Brito (2016) find momentum mainly among liquid stocks and unstable across
    sub-periods [3]; Grincho (2018, 1995–2017) finds no significant abnormal returns [3]; a 2020 BBR study
    (2009–2018) finds winners beat BOVA11 but "transaction costs can significantly impact" results [4]; an
    undergraduate monograph (2001–2020) reports 12.9%/yr for top-decile momentum vs 10.4%/yr for the Ibovespa
    (weak: its Sharpe ignores the risk-free rate) [5].
- *Decay:* NEFIN shows no decay in Brazil through 2026 [1]. The general post-publication haircut is −58% (SS1 [1]).
- *Turnover/cost:* this is monthly tercile turnover. Most brokers charge zero brokerage on stocks [10]. The B3
  emolumentos figures disagree across sources (≈0.003%–0.039%) [11]: insufficient data, so check the official table.
  The fractional market has lower liquidity, so spreads are wider [7].
- *Min. capital:* lots are 100 shares, and the fractional market allows 1–99 shares (ticker suffix "F") [7]. With
  ~$300 the owner can hold only a handful of single shares. Whether 5–10 names track a ~30-stock tercile is
  insufficient data, and a study must test it.
- *Data:* NEFIN factors are free CSV [1]. B3's COTAHIST files are free from 1986, include delisted names, but are
  **unadjusted** for splits and dividends [12]. Building an adjusted, survivorship-free panel is real work.
- **Verdict: Maybe (best of this survey).**

**F2. Low volatility / low beta on B3.**
- *Evidence:*
  - A USP monograph (1995–2021) finds the anomaly with beta sorts, but inconclusive with volatility sorts [13].
  - An FGV dissertation (2002–2018) reports low-vol portfolios beat the IBrX-100 [13].
  - A Brazilian five-factor paper finds lower-volatility firms earn higher returns [13].
  - S&P DJI (practitioner, 2020) reports the S&P/B3 Low Volatility index beat its benchmark over 5, 10 and 20 years.
    The page was blocked, so the numbers are unverified [13].
- *Product:* LVOL11 (Nu Asset, launched July 2024, 0.50%/yr fee) already packages a B3 low-vol index. It returned
  40.6% in 2025 against 35.0% for an Ibovespa ETF (third-party data) [14].
- *Turnover:* low (index rebalanced every 4 months [14]).
- *Opinion:* there is little reason to build an algorithm. An ETF exists, but ETFs lose the R$20k exemption [9].
- **Verdict: Maybe** (as a passive comparison or benchmark, not as a bot).

**F3. Value / quality on B3.**
- *Evidence:* NEFIN HML returned 7.35%/yr gross over 2001–2026, with a −61.9% drawdown. It was **−7.05%/yr in
  2009–16** and 12.99%/yr in 2017–26 [1]. Quality on B3 is insufficient data (no study verified).
- *Data:* needs point-in-time fundamentals. The CVM open-data filings were not verified in this survey.
- **Verdict: No** for study 2: the regime dependence is long, the data is heavy, and the factor is annual.

**F4. Short-term reversal (stocks).**
- *Evidence:*
  - A USP dissertation (1999–2012, 1,296 strategies) found **no reversal effect** [15].
  - A PUC-Rio dissertation finds profitability "reduced in the latest years" [15].
  - SS1 F3 already found it cost-bound in the US.
- **Verdict: No.**

**F5. Calendar and dividend effects.**
- *Evidence:*
  - Turn-of-the-month was found in Brazil over 1993–2011 and 1996–2018 [16]. A 2012–2022 study on nine Brazilian
    indices found only an April month effect [16].
  - Ex-dividend and ex-JCP prices deviate from their theoretical drops (378 events, 1996–2002), but no paper we
    found tests a capture strategy net of costs and tax [17].
- *Opinion:* the effects are small, the decay is unknown, and dividend capture realises taxable JCP (15%
  withholding [17]).
- **Verdict: No** (turn-of-the-month at most as a filter, which would cost variants).

**F6. Pairs / statistical arbitrage on B3.**
- *Evidence:*
  - Caldeira & Moura (2013, 2005–2012) report 16.38%/yr excess returns and a Sharpe of 1.34 (abstract only; cost
    treatment unverified) [18].
  - Perlin (2007) finds it "profitable and market neutral", with no cost figures [18].
  - Lending fees were ~6%/yr in 2004 and <3% in 2011 [18].
  - The global evidence shows decay (SS1 F4).
- *Min. capital:* a short leg needs stock borrowing and margin. At $300 that is impractical (Opinion).
- **Verdict: No.**

**F7. Carry / basis.**
- *Crypto funding:*
  - The baseline rate is ≈10.95%/yr. On ~2× capital that leaves ≈4.4–5.3%/yr net (SS1 F6; `docs/candidates.md`
    §4), well below CDI.
  - A secondary source reports the BTC basis fell from 20–25% (2024 peak) to ~10% (mid-2025), and that funding went
    negative in the October 2025 crash [19].
  - BitMEX's "−90% extreme funding" claim is still unverified (404) [19].
  - Brazil VASP rules require exchanges to apply to the BCB by **2026-10-30**. Binance's status is unverified [20].
- *BRL fixed income:* this is the hurdle, not a strategy. LCI/LCA are IR-exempt, and CDB/Tesouro pay 22.5→15% tax
  plus B3 custody of about 0.2%/yr on Tesouro (secondary) [8].
- **Verdict: No** for crypto carry (below CDI, venue risk). **Yes** for CDI products as the baseline.

**F8. Volatility / risk-premium harvesting on B3.**
- *Evidence:* we found no Brazilian net-of-cost covered-call study on BOVA11. A PUC-Rio study used single stocks
  because Ibovespa options are illiquid [21]. The XIV tail is in SS1 F9.
- *Min. capital:* covering a call means holding the underlying in full contract size (exact lot size not verified
  this session), which is far above $300 (Opinion).
- **Verdict: No.**

**F9. Simple allocation rule (CDI + equity mix).**
- *Evidence (my calculation [1], gross, daily rebalancing, NEFIN market rather than an investable ETF):*

  | Mix: 50% market + 50% risk-free | CAGR | vs risk-free alone | Max drawdown | Longest underwater |
  |---|---|---|---|---|
  | 2001–2026 | 13.39%/yr | 12.06%/yr | −31.7% | 15.8 months |
  | 2021-07 to 2026-07 | 9.02%/yr | 12.31%/yr | −10.0% | 14.2 months |
- *Opinion:* this is the honest benchmark for study 2, not an edge. It still breaks the "a couple of weeks"
  drawdown wish.
- **Verdict: Yes (as benchmark).**

**F10. Crypto cross-sectional momentum / reversal.**
- *Evidence:* Han, Kang & Ryu find cross-sectional momentum "weak", and losers rebound (secondary) [22]. Fieberg et
  al. (2024) find momentum costly and short-driven [22].
- **Verdict: No.**

## Summary table

| # | Family | Brazil evidence | Decay | Cost sens. | $300 fit | Free data | Verdict |
|---|---|---|---|---|---|---|---|
| F1 | XS momentum, B3 long-only | NEFIN WML 15%/yr gross [1] | none seen in BR | medium | fractional, lumpy | yes (unadjusted) | **Maybe** |
| F2 | Low vol, B3 | several studies [13] | unknown | low | ETF exists | partly | Maybe (benchmark) |
| F3 | Value/quality | HML regime-dependent [1] | — | low | fractional | heavy | No |
| F4 | ST reversal | none / fading [15] | high | high | ok | yes | No |
| F5 | Calendar/dividend | mixed [16][17] | unknown | high | ok | yes | No |
| F6 | Pairs | old, pre-2013 [18] | yes | high | needs shorting | yes | No |
| F7 | Crypto carry | < CDI | compressed [19] | medium | ok | yes | No |
| F8 | Options/vol | insufficient | — | high | lot size | no | No |
| F9 | CDI+equity mix | NEFIN calc [1] | n/a | very low | yes | yes | Yes (benchmark) |
| F10 | Crypto XS mom/rev | weak [22] | — | high | ok | yes | No |

## Ranked shortlist (Opinion)

1. **Long-only B3 momentum** (top names by 12-1 return, monthly, fractional shares), benchmarked against the 50/50
   CDI mix and BOVA11. It must address the tercile-vs-handful tracking gap, the unadjusted COTAHIST data, and the
   capital.
2. **CDI or a CDI+equity mix (F9)** as the mandatory benchmark, after tax.
3. **Low-vol ETF (LVOL11)** as a second passive benchmark, not something to build.

Everything else is No for $300.

## Sources (all accessed 2026-10-11)

1. NEFIN risk factors page and CSV: https://nefin.com.br/data/risk-factors/ ; https://nefin.com.br/nefindata/risk-factors/nefin_factors.csv. My statistics were computed with `uv run --no-project --with pandas python -I nefin_stats.py nefin_factors.csv` (script in the session scratchpad, not committed). They are gross, with no tax, and longest underwater counted in 21-day months.
2. NEFIN methodology §3, §4.3, §5.4: https://nefin.com.br/nefindata/methodology/nefin_methodology.pdf
3. Varga & Brito (2016), RBFin: https://ideas.repec.org/a/brf/journl/v14y2016i2p269-297.html ; Grincho (2018), NOVA: https://run.unl.pt/bitstreams/851ceff4-fe0a-4ce7-8402-5ccbd8c48079/download (search summaries only)
4. BBR (Jan 2020), momentum portfolios 2009–2018: https://doaj.org/article/63fc7b7aae164ad6b877bb9abc59056a (summary only)
5. Leite (2022), UFU monograph, Table 3: https://repositorio.ufu.br/bitstream/123456789/35341/1/BacktestingDoEfeito.pdf
6. (number not used)
7. Lot and fractional market: https://borainvestir.b3.com.br/glossario/acao-fracionada/ ; https://www.suno.com.br/artigos/lote-padrao/amp/
8. Fixed-income tax and IOF (secondary): https://adrianofreire.com.br/blog/ir-regressivo-renda-fixa-tabela ; https://oespecialista.safra.com.br/tabela-regressiva-ir/
9. Equity tax (R$20k, 15%/20%, MP 1.303 rejected; secondary): https://borainvestir.b3.com.br/noticias/imposto-de-renda/renda-variavel-imposto-de-renda/comprou-ou-vendeu-acoes-veja-como-declarar-swing-trade-day-trade-e-proventos-no-imposto-de-renda/ ; https://www.awaketrader.com/pt/educacao/mp-1303-rejeitada-isencao-20-mil-2026 ; ETF 15% with no exemption: https://investnews.com.br/?p=240940
10. Zero-brokerage brokers: https://www.idinheiro.com.br/investimentos/corretoras/corretoras-corretagem-zero/
11. Emolumentos (conflicting): https://euqueroinvestir.com/educacao-financeira/bolsa-de-valores-aprenda-o-que-sao-emolumentos-e-como-eles-sao-cobrados ; https://blog.toroinvestimentos.com.br/bolsa/emolumentos/
12. COTAHIST via rb3 docs: https://docs.ropensci.org/rb3/
13. Low vol in Brazil: https://bdta.abcd.usp.br/directbitstream/993fc885-4016-4577-82a1-4d02ecfb80d2/Marcio_Luiz_Campos_de_Mor... ; https://periodicos.fgv.br/rbfin/article/view/74602 ; https://www.indexologyblog.com/2020/04/20/low-volatility-response-in-brazil/ (403, unverified)
14. LVOL11 (third-party): https://www.suno.com.br/noticias/?p=657439 ; https://www.etfsbrasil.com.br/comparador/ibob11/lvol11
15. Reversal: https://bdtd.ibict.br/vufind/Record/USP_68b19d72dee0b37a657f62e987e8086f ; https://www.econ.puc-rio.br/uploads/adm/trabalhos/files/Dissertacao_Luis_Larisch.pdf
16. Calendar: https://ideas.repec.org/a/nax/conyad/v60y2015i1p53-86.html ; https://ideas.repec.org/a/idn/journl/v22y2019i2ep213-236.html ; https://www.indianjournalofentrepreneurship.com/index.php/IJF/article/view/173841
17. Ex-dividend/JCP: https://periodicos.ufpe.br/revistas/gestaoorg/article/view/21565
18. Pairs: Caldeira & Moura (2013), RBFin 11(1): https://doaj.org/article/b51aacdd28a8469ca0cc582e7ac1ef47 ; Perlin (2007): https://ideas.repec.org/p/pra/mprapa/8308.html ; Santos & Pessoa (2017): https://racef.fundace.org.br/index.php/racef/article/download/447/pdf_56
19. Funding compression (secondary): https://www.bit.com/knowledge-hub/basis-trade ; BitMEX Q2/Q3 2025 reports (404): https://www.bitmex.com/blog/2025q2-derivatives-report
20. BCB VASP deadline (secondary): https://decrypt.co/375249/brazils-319b-crypto-market-faces-october-licensing-deadline-certik
21. Covered calls (PUC-Rio): https://www.maxwell.vrac.puc-rio.br/75002/75002.PDF (summary only)
22. Crypto XS momentum: https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf ; https://open.icm.edu.pl/handle/123456789/25544 (summaries only)
