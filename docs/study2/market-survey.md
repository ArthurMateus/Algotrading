# Study 2 market survey: what a Brazil resident with ~US$300 can access

Phase 1 of study 2 (open search). Author: market-researcher agent. **All sources accessed 2026-10-11** (list at the
end, `[T#]`). This file extends `docs/market-survey.md` (study 1, `[S#]` there) and does not repeat it. Labels:
**Evidence** means an official page, a law, a regulator, or a public API response I fetched. **Secondary** means a
broker blog or the press. **Opinion** means my own judgement. This is public information, not tax or financial advice.
Owner: Brazil resident, ~US$300 (= about R$1,497 at the BCB PTAX of 4.9892 on 2026-10-09 [T1]).

## 1. Findings ranked by impact

1. **The hurdle is high: CDI 13.65%/yr, Selic target 13.75% (Evidence [T1]).** Tesouro Selic has no custody fee
   below R$10k [T3]. (Opinion, arithmetic) After the 22.5%-15% regressive tax, CDI nets ~10.6%/yr (≤180 days) to
   ~11.6%/yr (>720 days). Any strategy must beat that after its own tax.
2. **The crypto venue landscape changes within four weeks (Evidence [T4][T5]).** Existing VASPs must file phase 1
   of BCB authorisation by **2026-10-30** (IN BCB 704) to keep operating during review. From **2026-11-06**
   (Res. BCB 589) banks and payment firms may not "carry out or enable" crypto operations with **unauthorised**
   providers (exceptions not detailed). Binance's filing: **unverified**; the only BCB approval found is the 2025
   Sim;paul broker purchase, not a VASP authorisation [T6]. (Opinion) PIX funding of offshore exchanges may get harder.
3. **Crypto perps are not a clean option.** (Secondary) Binance cut Brazilian derivatives access in 2021 citing the
   CVM [T7]; the CVM reopened a proceeding on it [T8]. Free funding history is excellent (section 3), so a
   **measurement-only** carry study remains possible.
4. **Tax punishes turnover (section 5).** Day trade pays 20% with no exemption; ETFs/BDRs 15% with no exemption.
   The stock (R$20k) and crypto (R$35k) exemptions count **monthly sales, not profit**: (Opinion, arithmetic)
   R$1,500 turned over ~13 times a month breaks R$20k, ~23 times breaks R$35k.
5. **B3 spot is cheap and has good free data.** Exchange fees 0.0274%/side regular, 0.0230% day trade [T11];
   brokers commonly charge zero commission (Secondary [T12]); Yahoo `.SA` daily data is keyless [T13].
   (Opinion) B3 equities/ETFs via the fractional market are the most accessible market for this owner.
6. **B3 mini futures are far too large.** One WIN ≈ R$41.8k notional, one WDO ≈ R$49.9k. (Opinion) Paper only;
   live, one adverse 1% move costs a quarter to a third of the account.

## 2. B3 equities, ETFs and mini futures

**Fractional market.** (Secondary) Round lot usually 100 shares; 1-99 shares trade as ticker + "F" (PETR4F)
[T14]; fractional volume is "drastically lower", mostly individuals [T15]. Spreads/depth: **insufficient data**.
(Opinion) Fine for daily/weekly strategies on liquid names; intraday fractional trading is unmeasured.

**B3 fees (Evidence, official tariff page, no validity date shown, PIS/COFINS included) [T11].** Rates are per side,
on traded value, for monthly ADTV up to R$3M.

| | Negotiation (emolumentos) | CCP (liquidação) | Per side | Round trip |
|---|---|---|---|---|
| Regular (swing) | 0.00500% | 0.02240% | 0.0274% | 0.055% |
| Day trade (ADTV ≤ R$0.2M) | 0.00500% | 0.01800% | 0.0230% | 0.046% |

Commissions: "zeroed at most brokers" (Secondary [T12]), but one broker lists a R$10 minimum per fractional
day-trade order [T16].

**Free historical data.**
- **COTAHIST** (Evidence [T17]): official, since 1986, yearly zip of fixed-width 245-byte records, **not adjusted**
  for dividends/splits/bonuses. (Opinion) It covers whatever traded, so delisted tickers should be present: good
  against survivorship. Avoid pre-1995 data (pre-Real) [T18].
- **Yahoo `.SA`** (Evidence, my fetch [T13]): keyless daily OHLC + `adjclose`; PETR4 from 2000-01-03, BOVA11 from
  2008-11-28, one null close each. (Opinion) Delisted tickers missing (survivorship risk); adjustment method
  undocumented, cross-check against COTAHIST.
- **brapi.dev**: `adjustedClose` field; warns against adding dividends on top (Secondary [T19]). Key needed: unverified.

**Paper trading.** No official B3 retail simulator found. TradingView paper trading covers B3 tickers (Secondary
[T20]); Toro's free Profit includes a simulator (marketing [T21]). (Opinion) Use our own simulator, as in study 1.

**Mini futures** (Evidence plus Secondary):

| | WIN (mini Ibovespa) | WDO (mini dollar) |
|---|---|---|
| Size | R$0.20 × index points, tick 5 points (= R$1) [S29][T22] | US$10,000, R$10/point, tick 0.5 point = R$5 [T23] |
| Notional now | 209,067 × 0.20 ≈ R$41.8k (Ibovespa via Yahoo [T13]) | 10,000 × 4.9892 ≈ R$49.9k [T1] |
| Day-trade margin | Set by the broker [T22]; minimum R$155 (B3's Bora Investir, 2026-03-10 [T24]) | R$140 from 2026-02-02 (Secondary, citing OC 059/2025 [T23]) |
| Overnight margin | Set by B3 [T22]; amount: insufficient data | Insufficient data |
| Exchange fee per contract | Insufficient data (B3 page returned error 500). One broker lists R$12.50/contract day trade [T16] | Insufficient data |

- (Opinion) $300 covers the margin but not the risk: about 28x (WIN) and 33x (WDO) notional leverage on R$1.5k.
- Free data for continuous futures: insufficient data (COTAHIST covers the spot market only, per its page [T17]).

## 3. Crypto for a Brazil resident

- **Regulation:** framework in force from 2026-02-02; incumbents' authorisation may take up to 3 years (Res. BCB
  548/26, Secondary [T25]); self-custody transfers ≥ US$10k reported to Coaf since 2026-10-01 [T4]; algorithmic
  stablecoins banned (Secondary [T26]).
- **Local exchange fees (Secondary, brapi.dev Jan-2026; official pages returned 403):**

  | Exchange | Maker | Taker |
  |---|---|---|
  | Mercado Bitcoin | 0.30% | 0.70% |
  | Foxbit | 0.25% | 0.50% |
  | NovaDAX | 0.20% | 0.50% |
  | Bitso | 0.10% | 0.10% |
  | Binance | 0.10% | 0.10% |

  PIX deposits are free at all of them [T27]. The Mercado Bitcoin round trip is 1.4% at taker rates (unverified).
- **Perps/funding:** Binance derivatives have been off for Brazil since 2021, though the 2021 press says the English
  site still allowed access [T7]. Hyperliquid's terms do not list Brazil [S3]. Legality and tax treatment of using
  them: **open question**.
- **Free funding history (Evidence, my fetches [T28][T29][T30]):**
  - Binance bulk archive: monthly `fundingRate` zips, BTCUSDT 2020-01 to 2026-09;
  - Hyperliquid `fundingHistory`: data from 2023-05-12;
  - OKX `funding-rate-history`: keyless.

## 4. Fixed-income baseline (the hurdle)

- **Rates (Evidence [T1]):** Selic 13.75%; CDI 13.65%/yr (2026-10-08). Next Copom 2026-11-03/04 (Secondary [T2]).
- **Tesouro Selic [T3]:** custody 0.20%/yr only above R$10k; no longer semi-annual (charging moment: sources conflict).
- **CDB (Secondary [T31]):** FGC up to R$250k per CPF per institution; IOF 96%→0% on redemptions within 30 days.
- **Tax table (Lei 11.033/2004 art. 1, still in force after MP 1.303 lapsed [T10][T31]):**

  | Holding period | Income tax |
  |---|---|
  | ≤ 180 days | 22.5% |
  | 181 to 360 days | 20% |
  | 361 to 720 days | 17.5% |
  | > 720 days | 15% |

## 5. Brazilian tax rules (public information, not advice)

| Asset | Rule | Source quality |
|---|---|---|
| Stocks, swing trade | 15% of monthly net gain; exempt if total **stock sales** in the month ≤ R$20k (all-or-nothing) | Secondary [T32][T33]; legal text not fetched |
| Stocks/ETFs, day trade | 20%, no exemption; broker withholds 1% of daily profit | Secondary [T32] |
| ETFs, BDRs, options | 15%, **no** R$20k exemption | Secondary [T32][T34] |
| FIIs | 20% on sale gains; distributions exempt under conditions | Secondary [T32][T33] |
| Crypto, Brazilian venue | Exempt if monthly **sales** ≤ R$35k; above that, 15% to 22.5% progressive | Secondary citing IN RFB 1.585/2015 and Lei 7.713/88 [T10] |
| Offshore (Lei 14.754/2023) | 15% flat, assessed **annually** (from 2024), no deductions; losses offset only against offshore income, carried forward | Secondary law-firm notes [T9][T35]; planalto.gov.br unreachable |
| Crypto on a foreign exchange | Treated as offshore (IN RFB 2.180/2024): 15% a year, no R$35k exemption | Secondary [T36]; **unverified** |

**Recent changes.** **MP 1.303/2025** (flat 17.5%, end of the R$35k crypto exemption) **lapsed** on 2025-10-08
[T10]; pages describing it as law are stale. **Lei 15.270/2025**: 10% withholding on dividends > R$50k/month per
company from 2026 (Secondary [T37]; irrelevant at our size). **DeCripto** reporting (IN RFB 2.291): unverified
[T38]. **IOF** on transfers to one's own account abroad: 1.1% (Secondary [T39]).

**What makes high turnover worse (Opinion):** day trade loses the exemption and pays 20%; turnover breaks the
sales-based exemptions even on small profits; ETFs/BDRs are never exempt; every month with gains needs a DARF
(admin cost); offshore gains are taxed yearly with no exemption.

## 6. US assets from Brazil (brief)

- **BDRs:** most are unsponsored and open to any investor; sponsored Level I has conditions (sources conflict)
  [T34][T40]. Taxed like ETFs (15%, no exemption).
- **Brokers:** IBKR says its B3 access is *not* available to Brazil residents [T41]; general IBKR accounts for
  Brazil residents: Secondary says yes [T39], unverified. Avenue and Nomad serve Brazilians (Secondary [T39]).

## 7. Comparison table

| Venue / market | Access for a Brazil resident | All-in round trip (cost) | Free data | Minimum capital |
|---|---|---|---|---|
| B3 stocks/ETFs, fractional | Yes, any local broker | ≈0.055% B3 + spread (insufficient data) + R$0 commission (Secondary) | Yahoo `.SA` daily (adjusted, survivor); COTAHIST since 1986 (raw, with delisted) | 1 share (e.g. one BOVA11) |
| B3 mini futures WIN/WDO | Yes | B3 fee insufficient data; one broker R$12.50/contract | Insufficient data | Margin R$140-155, but notional R$42-50k |
| Tesouro Selic / CDB | Yes | ≈0 below R$10k; tax 22.5% to 15% of gains | BCB SGS API (CDI/Selic) [T1] | ~R$100s (insufficient data) |
| Crypto spot, local (MB, Foxbit, Bitso) | Yes, subject to the 2026-10-30 / 11-06 rules | 0.2% (Bitso) to 1.4% (MB taker), unverified | Exchange-specific (insufficient data) | Small |
| Crypto spot, Binance | Operating; VASP filing unverified | 0.2% [S4] + BRL conversion | Excellent bulk archive [S6] | Small |
| Crypto perps (Binance/Hyperliquid) | Doubtful (Binance withdrew in 2021; legality open) | 0.09-0.10% taker [S1][S5] + funding | Excellent funding history [T28-30] | Small |
| BDRs | Yes (most) | ≈0.055% B3 + wider spread | Yahoo `.SA` (unverified per ticker) | 1 BDR |
| US broker (Avenue/Nomad/IBKR) | Likely, unverified | 1.1% IOF + FX spread each way, plus commission | Yahoo/Alpaca (study 1) | Small |

## Sources (all accessed 2026-10-11)
- T1 BCB SGS API, series 432/4389/1: https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json (and .4389, .1)
- T2 Copom 2026-09: https://atlaspublico.com.br/bcb/noticias/copom-reduz-selic-para-13-75pct-ao-ano-em-decisao-unanime-87748 ; https://renovainvest.com.br/?p=106745
- T3 Tesouro custody: https://borainvestir.b3.com.br/tipos-de-investimentos/renda-fixa/tesouro-direto/taxa-de-custodia-do-tesouro-direto-deixa-de-ser-cobrada-semestralmente/ ; https://blog.toroinvestimentos.com.br/renda-fixa/taxa-semestral-tesouro-direto/
- T4 Capital Aberto, 2026-10-07: https://capitalaberto.com.br/regulacao/2026/10/prazo-do-bc-aperta-cerco-sobre-ativos-virtuais
- T5 Res. BCB 589: https://okai.com.br/documento/2026-09-23/resolucao-bcb-n-589
- T6 Binance/Sim;paul (2025-01-02): https://www.iprofesional.com/tecnologia/420043-brasil-otorga-a-binance-su-21-autorizacion-regulatoria-global
- T7 Binance futures suspended in Brazil (2021): https://www.bloomberglinea.com.br/2021/08/20/binance-suspende-negociacoes-de-contratos-futuros-no-brasil/
- T8 CVM reopens Binance proceeding: https://www.infomoney.com.br/onde-investir/cvm-volta-atras-e-reabre-processo-contra-binance-por-suposta-oferta-irregular-no-brasil/
- T9 Lei 14.754 summaries: https://www.demarest.com.br/wp-content/uploads/2023/12/DEMAREST_Client-Alert_13-12-2023_Tributacao_de_ativos_no_exterior_e_fundos_de_investimento_v2.pdf ; https://assets.ey.com/content/dam/ey-sites/ey-com/pt_br/topics/tax-alert/ey-tax-alert-11-01-24.pdf
- T10 MP 1.303 lapse (2025-10-17): https://www.contabeis.com.br/artigos/73399/a-queda-da-mp-1303-2025-o-que-muda-na-tributacao-de-investimentos-e-criptoativos/
- T11 B3 equity tariffs: https://www.b3.com.br/pt_br/produtos-e-servicos/tarifas/listados-a-vista-e-derivativos/renda-variavel/tarifas-de-acoes-e-fundos-de-investimento/a-vista/
- T12 Commission zero (secondary): https://www.richify.ai/br/glossary/b3
- T13 Yahoo chart API: https://query1.finance.yahoo.com/v8/finance/chart/PETR4.SA?period1=0&interval=1d (also BOVA11.SA, ^BVSP)
- T14 Fractional lots: https://www.serasa.com.br/blog/como-comprar-fracoes-de-acoes/ ; https://acionista.com.br/mercado-a-vista-na-bolsa-de-valores-o-que-e-e-como-funciona/
- T15 Fractional liquidity (academic): https://racef.fundace.org.br/index.php/racef/article/download/1246/pdf
- T16 Monte Bravo costs: https://www.montebravo.com.br/wp-content/uploads/2025/02/Custos_Monte_Bravo.pdf
- T17 B3 COTAHIST: https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/mercado-a-vista/cotacoes-historicas/ ; layout https://www.b3.com.br:443/data/files/33/67/B9/50/D84057102C784E47AC094EA8/SeriesHistoricas_Layout.pdf
- T18 rb3 manual: https://packages.ropensci.org/rb3/doc/manual.html
- T19 brapi historical: https://brapi.dev/blog/dados-historicos-b3-python-pandas-api
- T20 TradingView paper on B3: https://www.tabnews.com.br/vadiandonarede/simulando-investimentos-em-acoes-brasileiras-commodities-e-criptomoeda
- T21 Toro Profit: https://blog.toroinvestimentos.com.br/trading/nelogica-profit/
- T22 B3 Ibovespa futures: https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/mercado-de-acoes/futuro-de-ibovespa.htm
- T23 WDO: https://www.infomoney.com.br/?p=3190452 ; https://blog.toroinvestimentos.com.br/?p=16762
- T24 Bora Investir WIN (2026-03-10): https://borainvestir.b3.com.br/tipos-de-investimentos/renda-variavel/derivativos/o-que-e-mini-indice-win-e-por-que-ele-atrai-quem-esta-comecando-no-day-trade/
- T25 Res. BCB 548/26 "up to 3 years": web-search snippet only (query "Binance autorização Banco Central Brasil VASP prazo outubro 2026"), primary text not fetched: unverified
- T26 Res. 520 summaries: https://www.bmalaw.com.br/conteudo/institucional/informativos-e-newsletters/banco-central-regulamenta-o-uso-de-ativos-virtuais-e-o-funcionamento-e-a-autorizacao-das-sociedades-prestadoras-de-servicos-de-ativos-virtuais/pdf
- T27 Brazilian exchange fees: https://brapi.dev/blog/exchanges-criptomoedas-brasil-comparativo-2026
- T28 Binance funding archive: https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/monthly/fundingRate/BTCUSDT/
- T29 Hyperliquid info `fundingHistory`: POST https://api.hyperliquid.xyz/info
- T30 OKX: https://www.okx.com/api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP
- T31 CDB tax/IOF/FGC: https://www.infinitepay.io/blog/tabela-ir-cdb ; https://renovainvest.com.br/?p=14905
- T32 Stocks tax: https://euqueroinvestir.com/educacao-financeira/como-declarar-renda-variavel-no-ir ; https://www.contabeis.com.br/artigos/6931/tributacao-operacao-de-day-trade-e-swing-trade-bolsa-de-valores-na-pessoa-fisica/
- T33 XP day trade tax: https://conteudos.xpi.com.br/guia-de-investimentos/relatorios/day-trade-no-imposto-de-renda/
- T34 BDRs: https://gorila.com.br/blog/bdrs/
- T35 Offshore losses: https://www.hondatar.com.br/lei-14-754-2023-alteracoes-do-imposto-de-renda-tributacao-de-trusts-e-investimentos-no-exterior/
- T36 Crypto abroad: https://www.bmalaw.com.br/conteudo/direito-tributario/bma-review/bma-review-dia-do-estagiario/bma-review-especial-estag-a-nova-forma-de-tributacao-e-a-ampla-possibilidade-de-compensacoes-de-prejuizos-de-aplicacoes-financeiras-no-exterior-inclusive-para-ativos-virtuais/pdf ; https://www.adrianofreire.com.br/blog/como-declarar-criptomoedas-ir-2026
- T37 Lei 15.270: https://jornalcontabil.com.br/noticia/lei-15-270-define-regras-para-taxacao-de-lucros-e-dividendos-a-partir-de-2026/
- T38 DeCripto: https://plisio.net/pt/tax/brazil-crypto-tax
- T39 IBKR/Avenue/Nomad, IOF: https://www.awaketrader.com/pt/educacao/interactive-brokers-brasil-2026-como-abrir-conta ; https://www.idinheiro.com.br/investimentos/corretoras/corretoras-para-investir-no-exterior/
- T40 BDR levels: https://blog.inter.co/bdr-o-que-e/
- T41 IBKR B3 access: https://www.interactivebrokers.com/en/index.php?f=78855
