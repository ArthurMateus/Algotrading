# Market survey: venues and markets for a small-budget solo developer

Phase 1 (research), author: market-researcher agent. **All numbers accessed 2026-10-11** unless stated; sources are
`[S#]` in the list at the end. **Evidence** = read from an official page, API response or regulator. **Opinion** = my
judgement. "Unverified" = secondary source only. Not financial advice. The owner's country is unknown (see section 7).

## 1. Findings ranked by impact

1. **Fees dominate at small size, and the gap between venues is about 10x.** (Evidence) Lowest-tier taker fees:
   Hyperliquid perps 0.045% [S1], Binance USDⓈ-M perps 0.05% [S5], Kraken futures 0.05% [S10], Bybit perps 0.055%
   (unverified, Bybit pages timed out) [S8]; versus spot: Binance 0.10% [S4], Bybit 0.10% (unverified) [S8], Kraken
   Pro 0.80% [S10], Coinbase Advanced reportedly 0.90% (unverified) [S12]. US stocks/ETFs at Alpaca: $0 commission
   plus the sell-side regulatory fees [S13][S15]. (Opinion) Any crypto strategy that turns over often must use perps
   or Binance-class spot. Kraken/Coinbase spot only works for low-turnover rebalancing.
2. **Access depends on country more than on anything else.** (Evidence) Hyperliquid's interface excludes US and
   Ontario persons [S3]; Bybit lists the US as restricted [S9]; Binance reportedly stopped serving EU residents
   after the MiCA transition ended on 2026-07-01 (unverified, press only) [S7]. Brazil requires crypto service
   providers to apply for Central Bank authorisation; the reported deadline is about 2026-10-30, so the venue list
   may change within weeks (unverified, secondary) [S28].
3. **Free historical data is good for crypto, weak elsewhere.** (Evidence) Binance's public bulk archive (spot,
   USD-M, COIN-M: klines from 1s, trades, aggTrades; daily/monthly files) [S6], Kraken's full-history OHLCVT and
   trade CSVs "from the beginning of each market" [S11], Bybit's public file server [S27]. Hyperliquid candles are
   limited to "the most recent 5000 candles" [S2b]; deeper data is in requester-pays S3 buckets and "data may be
   missing" [S2d]. US equities: Alpaca's free plan has data "Since 2016" but IEX-only real-time, and the latest 15
   minutes of history are restricted [S14]. FX/futures: insufficient data on free bulk sources.
4. **The US pattern-day-trader rule is gone, but slowly.** (Evidence) FINRA Rule 4210 amendments replacing the PDT
   designation and the $25,000 minimum took effect 2026-06-04, with broker phase-in until 2027-10-20 [S16]. Each
   broker may still enforce the old rule during phase-in.
5. **Paper trading is free on most venues, with caveats.** (Evidence) Alpaca paper: "Anyone globally", $100k,
   fills ignore slippage, queue position and size against NBBO [S17]. IBKR paper needs an approved (not
   necessarily funded) live account; real-time data needs $500 funding [S20]. Binance futures testnet
   `demo-fapi.binance.com` [S5b]. Hyperliquid testnet faucet requires a prior mainnet deposit [S2c]. (Opinion) We
   should paper-trade on our own simulator fed by public data, not on venue testnets, which have unrealistic books.

## 2. Crypto perpetuals

| | Hyperliquid | Binance USDⓈ-M | Bybit linear |
|---|---|---|---|
| Maker / taker (lowest tier) | 0.015% / 0.045% [S1] | 0.02% / 0.05% [S5]; BNB pays 10% off [S5] | 0.02% / 0.055% (unverified) [S8] |
| Funding | Hourly; F = premium + clamp(rate - premium, ±0.05%); fixed interest 0.00125%/h; cap 4%/h [S2] | Insufficient data on interval (varies per symbol, check `/fapi/v1/fundingInfo`) | Insufficient data |
| BTC top-of-book snapshot | Insufficient data (needs POST) | bid 83,841.7 / ask 83,841.8 (2026-10-11 16:31 UTC) [S22] | bid 83,829.5 / ask 83,829.6; funding -0.00477%; 24h turnover $1.43bn [S23] |
| Free history | 5,000 candles via API [S2b]; `fundingHistory` by startTime [S2e]; S3 requester-pays [S2d] | Bulk klines/trades/aggTrades [S6]; funding history max 1,000 rows/request, 500 weight/5 min/IP [S5c] | Public file server (`trading/`, `premium_index/`, `spot/`...) [S27] |
| Public API limit | REST 1,200 weight/min/IP; 10 WS connections; 1,000 subscriptions [S2a] | Weight limits published in `exchangeInfo` [S5b] | 600 requests per 5 s per IP [S8b] |
| Testnet | Yes, faucet needs mainnet deposit [S2c] | Yes, `demo-fapi.binance.com` [S5b] | Insufficient data |
| Access | Excludes US and Ontario persons [S3] | EU reportedly halted (unverified) [S7]; US not served by binance.com (unverified) [S7b] | US restricted [S9]; UK unclear |

(Evidence) BTC spreads on the three snapshots were one tick (0.1 USD, about 0.01 bp). This is a single snapshot of
the most liquid pair, not a typical value for alts: insufficient data for "typical spreads" beyond BTC.

## 3. Crypto spot

| | Binance | Coinbase Advanced | Kraken Pro |
|---|---|---|---|
| Maker / taker (lowest tier) | 0.100% / 0.100%; 0.075% with BNB [S4] | 0.50% / 0.90% (unverified, Sept-2026 press; official page 403) [S12] | 0.40% / 0.80% (redesign 2026-07) [S10]; stablecoin/FX pairs 0.20%/0.20% [S10] |
| BTC snapshot | n/a | bid 83,790.94 / ask 83,790.95 [S24] | Not fetched |
| Free history | Bulk archive [S6] | Insufficient data | Full-history OHLCVT + trades CSV, through 2026-06-30 plus quarterly updates; gaps not zero-filled [S11] |

(Evidence) Delisted symbols: Binance's archive does not say whether delisted pairs are included [S6]; Kraken's covers
"each of our currency pairs" without clarifying delisted ones [S11]. This is a survivorship-bias risk to check in
phase 4.

## 4. US equities / ETFs

- **Alpaca** (Evidence): $0 commission for self-directed API accounts [S13]; SEC fee $20.60 per $1M of sales since
  2026-04-04 [S15]; FINRA TAF $0.000119/share on sells, max $5.95 (from a 2020 forum post, may be stale) [S13b].
  Free data: IEX feed, 200 historical calls/min, 30 WS symbols; paid plan $99/month [S14]. Borrow fees in paper
  are "Coming Soon" (not simulated) [S17]. Non-US residents: eligibility by tax/physical residence, not every
  jurisdiction supported; Brazil residence status not confirmed [S18].
- **Interactive Brokers** (Evidence via official search snippets; direct pages returned 403): IBKR Pro Fixed USD
  0.005/share, min USD 1.00, max 1% of trade value; Tiered 0.0005 to 0.0035/share [S19]. Free non-consolidated
  Cboe One + IEX real-time stream; paper starts at USD 1,000,000 [S20].
- (Opinion) For a few thousand USD, the $1.00 IBKR minimum per order is about 0.1% on a $1,000 order, which is
  comparable to Binance spot. Alpaca is cheaper per trade, but free data is IEX-only.

## 5. FX (retail)

- **OANDA**: official pages were unreachable (DNS failure). Third-party: about $5 per 100k commission on the raw
  account, EUR/USD average spread 0.94 to 1.40 pips, 50:1 US leverage (all unverified) [S21]. Candle API max 5,000
  per request (unverified, client-library docs) [S21b].
- (Evidence, 2018) EU retail CFD leverage caps: 30:1 majors, 2:1 crypto [S25]. Brazil: CVM has issued stop orders
  against unregistered offshore FX brokers soliciting Brazilian residents [S26].
- (Opinion) FX is the weakest fit: spread costs are opaque, there is no free bulk tick history from the broker that
  we could verify, and access is the most country-dependent.

## 6. Futures

- **CME micro via IBKR** (Evidence, IBKR snippet, "pricing as of 2025-02-24"): MES USD 0.25/contract up to 1,000
  contracts/month, plus exchange and regulatory fees [S19b]. MES multiplier and tick: not verified (CME page timed
  out). Free history: insufficient data (IBKR paper gives 10-minute delayed US futures data unless subscribed) [S20].
- **B3 mini contracts (Brazil)** (Evidence): Mini Ibovespa (WIN) point value BRL 0.20, tick 5 points [S29]. Mini
  dollar (WDO) BRL 10/point (unverified, broker blog) [S30]. Day-trade margins of BRL 100 (WIN) / BRL 150 (WDO) at
  one broker (unverified) [S30]. B3 fees (emolumentos) and free historical data: insufficient data.

## 7. Depends on country (open questions for the owner)

1. **Where are you resident (tax and physical)?** This decides everything below.
2. **US resident:** Hyperliquid [S3] and Bybit [S9] are excluded; binance.com unavailable (use Binance.US, not
   researched) [S7b]. Alpaca/IBKR/CME micros are natively available; PDT phase-out depends on the broker [S16].
3. **EU resident:** Is Binance still serving your country after 2026-07-01 (reported halt) [S7]? MiCA-licensed
   venues (Kraken, Coinbase, Bybit EU) are likely options: fee tiers may differ by entity. CFD leverage caps apply
   [S25].
4. **UK resident:** Binance cannot onboard new UK retail (unverified) [S7b]; Bybit UK status is unclear [S9];
   Hyperliquid: the official restricted list names only the US and Ontario [S3], but third parties disagree.
5. **Brazilian resident:** Will your crypto venue obtain BCB authorisation by the ~2026-10-30 deadline [S28]? Can
   a Brazil resident open a live Alpaca account (contact support) [S18]? Is offshore FX allowed for you [S26]?
   B3 mini contracts (WIN/WDO) through a local broker are the native futures option [S29]. Hyperliquid is not on its
   restricted list for Brazil [S3], but a self-custody DEX has tax/reporting implications we cannot assess.
6. **Capital:** a few thousand USD means: perps with 1x leverage are fine on all three; one MES contract and B3 mini
   contracts are leveraged instruments, so position size cannot be scaled down below one contract.

## 8. Comparison table

| Market | Cheapest venue found (taker) | Free history | Paper/testnet | Min size | Main access risk |
|---|---|---|---|---|---|
| Crypto perps | Hyperliquid 0.045% [S1] | Good (Binance/Bybit bulk) | Yes | Small | US/Ontario/EU blocks |
| Crypto spot | Binance 0.10% [S4] | Very good (Binance, Kraken) | Testnets | Small | Binance in EU/UK/BR |
| US stocks/ETFs | Alpaca $0 + reg fees [S13] | Daily/minute since 2016 (IEX limits) [S14] | Alpaca paper, global [S17] | 1 share / fractional (insufficient data) | Non-US live accounts |
| FX | Insufficient data | Insufficient data | Demo accounts (unverified) | Insufficient data | Very country-dependent |
| Futures | CME micro $0.25/contract at IBKR [S19b]; B3 minis | Insufficient data | IBKR paper (delayed) | 1 contract | Leverage per contract |

## 9. Ranked view per strategy family (Opinion)

- **Trend (daily/4h):** 1) crypto perps (Binance/Bybit bulk history, low fees, long/short); 2) US ETFs on Alpaca
   (free daily data, zero commission); 3) futures micros (cost OK, but data and 1-contract size are hurdles).
- **Mean reversion (intraday):** 1) crypto perps (lowest fees, maker rebates not available at tier 0); 2) US
   stocks on Alpaca (needs SIP-quality data, which is paid [S14]). Spot on Kraken/Coinbase is ruled out by fees.
- **Carry / funding:** 1) Hyperliquid vs Binance/Bybit perps funding (hourly funding, documented formula [S2]);
   requires holding a hedge on spot or on a second venue, so fees on both legs and access to two venues matter.
- **Market making:** not realistic. No co-location, tier-0 makers pay 0.015 to 0.02% rather than earn rebates
   [S1][S5], and BTC spreads are already one tick [S22][S23]. Only long-tail pairs are left, where adverse
   selection is high (insufficient data to quantify).
- **Rebalancing (weekly/monthly):** 1) US ETFs (Alpaca/IBKR); 2) crypto spot on any venue, including Kraken, as
   turnover is low.

## Numbers I could not verify
Bybit fees (pages timed out), Coinbase Advanced lowest tier (403), OANDA anything (DNS failure), IBKR pages (403;
snippets only), CME MES contract specs (timeout), FINRA TAF current rate, Binance/Bybit funding interval, Binance
EU/UK/US status (press only), Brazil BCB deadline (secondary), typical spreads beyond one BTC snapshot, B3 fees.

## Sources (all accessed 2026-10-11)
- S1 Hyperliquid fees: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees
- S2 Hyperliquid funding: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding
- S2a Rate limits: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits
- S2b Info endpoint (candleSnapshot): https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint
- S2c Testnet faucet: https://hyperliquid.gitbook.io/hyperliquid-docs/onboarding/testnet-faucet
- S2d Historical data: https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data
- S2e Perpetuals info: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals
- S3 Hyperliquid Terms of Use (via search snippet, section 1.6): https://app.hyperliquid.xyz/terms
- S4 Binance spot fees: https://www.binance.com/en/fee/schedule
- S5 Binance futures fee article: https://www.binance.com/en/support/articles/360033544231
- S5b Binance USDⓈ-M general info: https://developers.binance.com/docs/derivatives/usds-margined-futures/general-info
- S5c Funding rate history: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History
- S6 Binance public data: https://github.com/binance/binance-public-data
- S7 Binance EU (press): https://www.hl.co.uk/shares/stock-market-news/company--news/binance-to-stop-serving-eu-customers-after-failing-to-get-licence-report ; https://decrypt.co/371990/binance-withdraws-mica-license-application-greece-eu-users-limbo
- S7b Binance US/UK (secondary): https://investingintheweb.com/blog/binance-countries ; https://coindesk.com/binance-exchange-to-block-crypto-trading-for-u-s-customers
- S8 Bybit fees (search snippets): https://www.bybit.com/en/help-center/article/Bybit-Fees-You-Need-to-Know ; https://www.bybit.com/en/help-center/article/Bybit-Spot-Fees-Explained
- S8b Bybit rate limits: https://bybit-exchange.github.io/docs/v5/rate-limit
- S9 Bybit restricted countries (search snippet): https://www.bybit.com/en/help-center/article/Service-Restricted-Countries
- S10 Kraken fee schedule: https://www.kraken.com/en-us/features/fee-schedule ; https://support.kraken.com/hc/en-us/articles/201893638
- S11 Kraken OHLCVT: https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data
- S12 Coinbase (press): https://www.diariobitcoin.com/exchanges/coinbase-reduce-sus-comisiones-de-advanced-y-baja-el-umbral-inicial-a-usd-10-000/
- S13 Alpaca commissions: https://alpaca.markets/support/commission-clearing-fees
- S13b Alpaca fees post: https://forum.alpaca.markets/t/pricing-and-fees/2309/
- S14 Alpaca market data plans: https://docs.alpaca.markets/docs/about-market-data-api
- S15 SEC fee advisory: https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2
- S16 FINRA Regulatory Notice 26-10: https://www.finra.org/rules-guidance/notices/26-10
- S17 Alpaca paper trading: https://docs.alpaca.markets/docs/paper-trading
- S18 Alpaca eligibility: https://alpaca.markets/support/requirements-alpaca-brokerage-account
- S19 IBKR stock commissions (snippet): https://www.interactivebrokers.com.au/en/pricing/commissions-home.php ; https://www.interactivebrokers.com/en/index.php?f=55459
- S19b IBKR futures commissions (snippet): https://www.interactivebrokers.com/en/trading/micro-futures-comparison.php ; https://www.interactivebrokers.com.sg/en/pricing/commissions-futures.php
- S20 IBKR paper/delayed data: https://www.interactivebrokers.com/en/trading/papertrader-delayed-data.php ; https://www.interactivebrokers.com/en/pricing/market-data-pricing.php
- S21 OANDA (third-party): https://www.compareforexbrokers.com/us/oanda-review/
- S21b OANDA candles (client docs): https://oanda-api-v20.readthedocs.io/en/latest/contrib/factories/instrumentscandlesfactory.html
- S22 Binance bookTicker: https://fapi.binance.com/fapi/v1/ticker/bookTicker?symbol=BTCUSDT
- S23 Bybit ticker: https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT
- S24 Coinbase ticker: https://api.exchange.coinbase.com/products/BTC-USD/ticker
- S25 ESMA CFD measures (2018): https://www.mccannfitzgerald.com/knowledge/derivatives/esma-adopts-product-intervention-measures-for-binary-options-and-cfds
- S26 CVM vs offshore FX: https://www.financemagnates.com/forex/brokers/exclusive-pepperstone-responds-to-brazils-cvm-stop-order/
- S27 Bybit public data: https://public.bybit.com/
- S28 Brazil VASP authorisation: https://decrypt.co/375249/brazils-319b-crypto-market-faces-october-licensing-deadline-certik ; https://international.anbima.com.br/news/brazil-s-central-bank-unveils-new-regulatory-framework-for-cryptoassets
- S29 B3 Mini Ibovespa: https://www.b3.com.br/en_us/products-and-services/trading/equities/mini-ibovespa-futures.htm
- S30 B3 minis (broker blogs): https://web.xpi.com.br/clear/documentos/e-book-minicontratos ; https://www.mobills.com.br/blog/investimentos/minicontratos/
