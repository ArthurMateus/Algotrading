# VERDICT (Phase 7)

Author: quant-economist agent, 2026-10-11. Judged strictly against `docs/success-criteria.md` (pre-registered,
sha256 `dd3305010517...`, unchanged). Technical and economic analysis, **not personal financial advice**. Tax
treatment for a Brazil resident is an open question. **Evidence** = a number from a cited report; **Opinion** is
labelled.

## One-page summary (plain language)

**Verdict: NO-GO for both markets. Neither strategy earned a place for your $300.**

- **What we tested.** One simple rule, "hold an asset only while its price is above its long-run average, and
  hold less of it when it is jumpy", on (A) five US ETFs and (B) Bitcoin + Ethereum. All the rules and the pass
  marks were written down *before* any test was run. We tried 12 versions per market (24 in total) on older data,
  picked the best one, then tested it once on recent data it had never seen.
- **What happened (Evidence).** On the unseen data:
  - **A (ETFs):** $300 became **$445** in ~5.9 years (6.9%/yr). Simply buying and holding the same five ETFs gave
    **$590** (12.1%/yr) (`backtest-A-oos.md`).
  - **B (crypto):** $300 became **$453** in ~3.4 years (13.0%/yr). Simply holding half BTC, half ETH gave
    **$685** (27.8%/yr) (`backtest-B-oos.md`).
- **The good part.** The strategies fell less in bad times: worst fall 7.5% vs 16.3% for A, and 34.8% vs 60.2% for
  B. That is real, but it is **not a free lunch**: they got the smaller falls by sitting in cash and giving up
  more return than they saved in risk. Per unit of risk they were worse than just holding.
- **Against Brazilian CDI (before tax).** Measured in reais, A grew 5.2%/yr vs CDI 11.1%: **CDI won**. B grew
  14.5%/yr vs CDI 13.0%, a small win, but with a 35% fall along the way, and mostly thanks to crypto and the
  dollar rather than the rule (`backtest-*-oos.md`, BRL/CDI flag).
- **Your "a couple of weeks" drawdown wish was not met.** The A strategy spent up to 24.6 months below its
  previous high, and B 17.0 months (`backtest-*-oos.md`, criterion 3).
- **Why this is a good result.** The tryout found, honestly and without risking a cent, **no evidence of an
  edge**. That is a success.
- **What we suggest you consider (Opinion).** With $300 in Brazil, the evidence-backed choices are a plain CDI
  product or plain buy-and-hold, not this bot. If you want to keep exploring, it must be a *new*, separately
  pre-registered study (section 7).

## 1. Verdict per market (Evidence)

Every criterion must pass (criteria §6). The forward paper test (Phase 6) was **not run**, because Phase 5 failed
(CLAUDE.md pipeline).

| # | Criterion | A value | A | B value | B |
|---|---|---|---|---|---|
| 1 | OOS Sharpe ≥ 0.40 / 0.50 | 0.624 | PASS | 0.423 | **FAIL** |
| 2 | Max drawdown ≤ 20% / 35% | 7.50% | PASS | 34.77% | PASS (by 0.23 pp) |
| 3 | Underwater ≤ 18 months | 24.6 | **FAIL** | 17.0 | PASS |
| 4 | Round trips ≥ 20 / 12 | 50 | PASS | 18 | PASS |
| 5 | Doubled-cost Sharpe > 0 | 0.565 | PASS | 0.393 | PASS |
| 6 | Deflated Sharpe ≥ 0.90 | 0.936 | PASS | 0.983 | PASS |
| 7 | Walk-forward Sharpe > 0 | 0.368 | PASS | 1.139 | PASS |
| 8 | Sharpe ≥ benchmark AND DD ≤ benchmark | 0.624 vs 0.874 | **FAIL** | 0.423 vs 0.642 | **FAIL** |

Sources: `backtest-A-oos.md`, `backtest-B-oos.md`; selections in `is_selection_{A,B}.json` (A: SMA-252-weekly,
B: SMA-126-weekly); one OOS run each, not forced (`oos_runs.jsonl`).

- **A (US ETFs): NO-GO.** Fails criteria 3 and 8.
- **B (BTC/ETH spot): NO-GO.** Fails criteria 1 and 8.
- **Overall: NO-GO.** No "GO ONLY IF" is justified: no pre-registered condition was met that could support one.

## 2. Net return after costs, with uncertainty (before tax)

| | A strategy | A benchmark | B strategy | B benchmark |
|---|---|---|---|---|
| OOS window | 2020-11-03..2026-09-30 | same | 2023-05-18..2026-09-30 | same |
| Final equity from $300 | $445.33 | $589.82 | $453.32 | $685.19 |
| CAGR (USD) | 6.92% | 12.13% | 13.03% | 27.77% |
| Costs paid | $7.06 | $0.98 | $11.16 | $2.01 |
| CAGR in BRL vs compounded CDI | 5.24% vs 11.11% (red flag) | insufficient data | 14.47% vs 13.00% (beats) | insufficient data |

Sources: `backtest-A-oos.md`, `backtest-B-oos.md` (Runs, Cost breakdown, BRL/CDI flag). The benchmarks' BRL
figures were not computed.

**Uncertainty.**
- **Evidence:** reasonable modelling changes move the results (`skeptic.md` F1, F3, `postrun_combined.txt`):
  - A CAGR 6.9% (logged) to 8.5% (cash earns T-bill, GLD outlier neutralised); Sharpe 0.62 to 0.88.
  - B CAGR 8.8% (one-day execution delay, `backtest-B-oos.md` latency sensitivity) to 13.0%; Sharpe 0.28 to
    0.51; a plausible central band is 0.37-0.51 (`skeptic.md` F3).
  - Every OOS Sharpe is uncertain by ±0.1-0.2 (`skeptic.md` F4, F5, "cannot be trusted" #7).
- **Opinion (my arithmetic, standard approximation SE ≈ √((1+SR²/2)/years)):** the pure sampling error is larger
  still, about ±0.45 Sharpe for A (5.9 years) and ±0.57 for B (3.4 years). These windows cannot distinguish a
  small edge from none.
- **In dollars (Opinion):** at A's 6.9%/yr, $300 earns ≈ $21/yr; CDI at 13.75% earns ≈ $41/yr before tax
  (criteria §7). B's ≈ $39/yr came with a fall of about a third of the account.

## 3. What the strategies did, and did not, do

- **Did (Evidence):** cut the worst drawdown roughly in half: A 7.50% vs 16.25%, B 34.77% vs 60.15%; exposure
  averaged only 58% (A) and 45% (B) (`backtest-*-oos.md`). Costs were not the problem: Sharpe stays positive even
  at 4x costs (`skeptic.md` F6).
- **Did not (Evidence):** beat passive holding on risk-adjusted terms. For A, **0 of 12** variants reached the
  benchmark Sharpe on OOS (`skeptic.md` F2). Criterion 8 fails for both markets under every perturbation tested:
  T-bill cash, start shifts of ±6 months, 2-4x costs, the GLD outlier removed (`skeptic.md` headline, F5).
- **Did not (Evidence):** keep drawdowns short: 88% (A) and 97% (B) of days under water (`backtest-*-oos.md`).
- **Opinion:** lower drawdown for lower return is a **preference trade-off, not an edge**.

## 4. Main risks (if anyone ran this anyway; Opinion, ranked)

1. **Selection decay.** B's in-sample ranking of the 12 variants had a rank correlation of **0.03** with their
   OOS ranking; the IS winner was among the worst OOS (`skeptic.md` F2). Picking a "better" variant now would be
   data snooping.
2. **Concentration.** Removing the 5 best trends turns A's Sharpe to −0.81 and B's to −1.13 (`skeptic.md` F4).
   A few missed trends erase the result.
3. **Execution.** B's base case assumes trading at the 00:00 UTC open instantly; one day of delay cuts Sharpe from
   0.423 to 0.280 (`backtest-B-oos.md`).
4. **Access and venue.** Live Alpaca for Brazil residents is unconfirmed; Binance's BCB authorisation by
   ~2026-10-30 is unverified (`context.md`, `docs/candidates.md` §5). Venue failure is in no backtest.

## 5. What the evidence does NOT prove

- That trend following **never** works. It shows this rule, on these 5 ETFs and 2 coins, in 2020-2026 and
  2023-2026, did not beat holding. Other decades (e.g. 2008) favoured trend (`backtest-A-is.md`: IS benchmark
  drawdown 34.6% vs ≤ 12.9% for every variant).
- Anything about other markets, other strategies (carry, futures, B3), or other position sizes.
- A precise effect size. OOS windows of 5.9 and 3.4 years carry ±0.1-0.2 Sharpe of model uncertainty and larger
  sampling error (section 2).
- That the in-sample tests were strong evidence. The deflated Sharpe passes (0.936, 0.983) are **generous**:
  the 12 trials are highly correlated (`skeptic-preflight.md` m2; `backtest-*-is.md` spread note), and B's 0.03
  rank correlation confirms the IS ranking carried no information.
- After-tax results (not computed). Survivorship/hindsight in instrument choice flatters both sides (criteria §1).

## 6. Skeptic findings that change the wording, not the verdict

- **Idle cash earning 0 (F1).** With T-bill cash, A's underwater spell would be 16.1 months (criterion 3 passes)
  and B's Sharpe 0.511 (criterion 1 passes). So **which** criteria fail depends on this pre-registered pessimism,
  but **criterion 8 still fails for both** (A 0.831 vs 0.874; B 0.511 vs 0.643). A's "24.6 months under water"
  mostly reflects uninvested cash in a 3-5% rate period, not losses (`skeptic.md` F1).
- **Latency (F3)** offsets the T-bill upside for B: combined Sharpe 0.369, still failing criteria 1 and 8.
- **B's passes on criteria 2 and 3 are marginal**: 34.77% vs 35% (35.22% at x2 costs), and 17.0 vs 18 months
  (30.6 with one-day latency) (`skeptic.md` "cannot be trusted" #3-4).
- **Two B variants pass criterion 8 post hoc** (SMA-126-monthly, SMA-252-weekly). They were not selected, and
  choosing them now is data snooping (`skeptic.md` F2).
- **Unverified GLD −10.3% on 2026-01-30** (`data-quality.md`) widens A's gap if removed (`skeptic.md` F7). The
  B "-dirty" commit is harmless (F8). Security PASS (`security.md`); 272 tests pass (`qa.md`).

## 7. Next steps: options for the owner (Opinion; GATE 3, you decide)

1. **Stop here (the evidence-backed choice).** For a $300 Brazil-resident budget, the tested alternatives that
   won are the passive benchmark (higher risk-adjusted return than the bot) and CDI (beat A in reais, and is
   far less risky than B). Expect nothing more from this engine.
2. **If you value smaller falls over return,** that is your preference, not an edge. A simple mix of CDI and a
   passive holding gives a smaller drawdown with no bot to run. No backtest here measured that mix
   (insufficient data).
3. **Further research only as a new study.** It needs a **new pre-registration**: new criteria, a **new data
   window** (the 2020-2026 / 2023-2026 OOS windows are now spent; the skeptic ran all 12 variants on them), and
   a variant count added on top of the **24 already used**. Never a re-run or re-tune of this one. A candidate is
   **E (funding carry, spot + short perp) as a measurement-only paper study** from public funding history.
   Honest expectations: about 4.4-5.3%/yr on capital at historical funding (`docs/candidates.md` §4, Candidate 3),
   which is **below CDI**; to beat cash, funding must exceed 2 × the cash rate + costs. Its main risks (exchange
   default, liquidation, negative funding) show in no backtest, and Binance's status in Brazil is unverified.
4. **Open questions:** Brazilian tax on offshore ETF/crypto gains and on CDI (needed for any after-tax
   comparison); live venue access for a Brazil resident; whether a real broker pays interest on idle USD cash.

**Verdict line: NO-GO (A: NO-GO, criteria 3 and 8; B: NO-GO, criteria 1 and 8). No evidence of a risk-adjusted
edge over passive holding; for $300 in Brazil, CDI or passive holding is the evidence-backed alternative.**
