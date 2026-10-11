# Skeptic post-run red team (Phase 5)

Author: overfitting-skeptic, 2026-10-11. Inputs: `reports/backtest-{A,B}-{is,oos}.md`, `is_selection_*.json`,
`variants.md`, `oos_runs.jsonl`, `reports/skeptic-preflight.md`. Every number below is **reported only**. None of
them changes a verdict, re-selects a variant or touches the logged OOS. The scripts call `engine.run` directly on
the cached `data/`. No `fetch` was run, and nothing was written to `variants*`, `oos_runs.jsonl`, `selected-*` or
`is_selection_*`.

- Scripts: `reports/skeptic/postrun_diagnostics.py` (`uv run python -X utf8 reports/skeptic/postrun_diagnostics.py A|B`)
  and `reports/skeptic/postrun_combined.py`.
- Raw outputs: `reports/skeptic/postrun_{A,B}.txt` and `postrun_combined.txt`.
- This is technical analysis, not financial advice.

**Reproduction check (Evidence):** run from the current `src/`, my code gives exactly the logged OOS figures:
- A: Sharpe 0.624, max drawdown 7.50%, underwater 24.6 months, 50 round trips; benchmark 0.874 and 16.25%.
- B: Sharpe 0.423, max drawdown 34.77%, underwater 17.0 months, 18 round trips; benchmark 0.642 and 60.15%.

## Headline

**Both FAILs stand. They are robust in the direction that matters.**
- Criterion 8 (Sharpe ≥ benchmark Sharpe) fails for both markets under every perturbation I tried:
  - T-bill on idle cash;
  - start-date shifts of ±3 and ±6 months;
  - x2 to x4 costs;
  - the GLD outlier removed;
  - every combination of these.
- For A, no variant out of 12 beats the benchmark Sharpe on OOS.
- The **list of failed criteria** is less robust than the verdict. It depends on the pre-registered "idle cash
  earns 0" pessimism:
  - With T-bill cash, A's criterion 3 would pass (16.1 vs 18 months), so A would fail on 8 alone.
  - With T-bill cash, B's criterion 1 would pass by a hair (0.511 vs 0.50), so B would fail on 8 alone.
- B's base Sharpe is also optimistic, because it assumes zero latency at 00:00 UTC. The two biases partly cancel.

## Findings ranked by impact

### F1. Idle-cash pessimism decides which criteria fail, but not the verdict. Severity: MAJOR (interpretation)

Owner: quant-economist (VERDICT wording only). The criteria stay frozen.

**Evidence** (`postrun_diagnostics.py`, §1). Each sleeve's cash share at the prior close earns that day's DTB3
rate per bar.

| | Sharpe (logged) | Sharpe (T-bill cash) | Underwater (T-bill cash) | Benchmark Sharpe (T-bill cash) | Criterion 8 |
|---|---|---|---|---|---|
| A SMA-252-weekly | 0.624 | **0.831** | **16.1 months** (logged 24.6) | 0.874 | FAIL (gap −0.043) |
| B SMA-126-weekly | 0.423 | **0.511** | 16.9 months | 0.643 | FAIL (gap −0.132) |

- Mean cash share: A 41.6%, B 55.3%. Mean T-bill rate: A 3.20%/yr, B 4.47%/yr.
- The benchmark is about 99.8% invested, so the adjustment barely moves it.
- Under T-bill cash, A's maximum drawdown falls from 7.50% to 5.16%.
- **Opinion:** "idle cash earns 0" was pre-registered and the verdicts stand. But the VERDICT should say the
  following plainly:
  - A's 24.6-month underwater period is mostly a cash-drag artefact of 2022-2024 rates. In 2023, A made +1.5%
    and still scored Sharpe −0.70, because the T-bill rate was about 5%.
  - B's criterion 1 failure sits within this modelling choice.
- Method caveat: my adjustment uses close-of-day weights, but fills happen at the next open. That is an
  approximation. A real retail account may also not pay the T-bill rate on cash (insufficient data).

### F2. Criterion 8 is a robust fail for A and a fragile, variant-specific fail for B. Severity: MAJOR

The neighbours were run **post hoc**. They are not usable for selection.

**Evidence** (§2, all 12 grid variants on the OOS window at x1 costs):

**A:**
- OOS Sharpe across the 12 variants: min 0.356, median 0.625, max 0.702.
- **0 of 12** variants reach the benchmark's 0.874.
- With T-bill cash, 4 of 12 variants would pass criterion 8. The selected variant would not (0.831 vs 0.874).
- Spearman rank correlation between IS and OOS Sharpe: 0.51.
- The failure is universal: in 2020-2026 an equal-weight ETF basket beat every trend variant on Sharpe.

**B:**
- OOS Sharpe across the 12 variants: min 0.354, median 0.493, max 0.663.
- **2 of 12** variants pass criterion 8 even at zero cash yield: SMA-126-monthly (0.643, DD 24.9%) and
  SMA-252-weekly (0.663, DD 27.3%). Both are ranked mid-table in IS.
- **Spearman(IS, OOS) = 0.03.** The IS ranking had no predictive power. The IS winner (1.193 IS) is one of the
  worst OOS (0.423).
- **Opinion:** this is the classic selection decay that criterion 6 was meant to catch. The DSR passed
  (0.983), but the 12 trials are highly correlated (preflight m2), so it was generous.
- Picking the passing variants after the fact would be pure data snooping.

### F3. B's base result assumes zero latency. Severity: MAJOR (optimistic direction)

Owner: quant-economist (flag); backtest-engineer (already reported).

**Evidence:**
- The logged close-fill sensitivity gives Sharpe **0.280** vs 0.423 (`backtest-B-oos.md`).
- My attribution residual for B is **+10.1 pp** (§4): the realised returns beat the close-to-close attribution.
  The strategy captures part of the move between the 00:00 UTC signal close and the same-instant open, which a
  real bot cannot do.
- One-day latency plus T-bill cash gives Sharpe **0.369**, maximum drawdown 33.7% (`postrun_combined.txt`). That
  fails criterion 1 again.
- The benchmark is insensitive to latency (0.640 vs 0.642).
- So the T-bill upside in F1 and the latency downside offset each other. B's true Sharpe is plausibly 0.37-0.51.
  Criterion 8 fails at every point in that range.

### F4. The edge is highly concentrated in a few long trends. Severity: MODERATE

**Evidence** (§4, approximate attribution: weight at close t−1 × asset return at t; correlation with actual
returns A 0.998, B 0.985):

**A:**
- The top 5 of 53 holding spells give **91%** of the total contribution. The largest is GLD from 2023-10-17
  (+13.9 pp).
- Without the top 5: Sharpe **−0.81**, CAGR 0.2%.
- Per-instrument contribution: SPY 12.5 pp, DBC 12.9, GLD 11.1, EFA 7.4, IEF −0.7.
- Dropping SPY or DBC alone cuts the Sharpe to about 0.30.

**B:**
- The top 5 of 20 spells give 206% of the net contribution, so the other 15 spells lose money in aggregate.
- Without the top 5: Sharpe −1.13, final equity $203.
- Per-asset contribution: BTC 19.8 pp, ETH 23.5 pp.

**Opinion:** this is normal for trend following (fat right tail). But it means about 5 trends decide the OOS
statistics, so every OOS Sharpe here has a wide error band. That supports treating the FAIL as "no evidence of an
edge over the benchmark", not as a precise measure.

### F5. Start-date and sub-period dependence. Severity: MODERATE

**Evidence** (§3a, end fixed at 2026-09-30):

- **A:** strategy Sharpe ranges 0.387-0.624 and benchmark 0.701-0.989 across shifts of −6 to +6 months.
  Criterion 8 fails at every start.
- **B:** strategy 0.423-0.605, benchmark 0.590-0.801. It also fails at every start.
- Calendar years (§3b): A loses to the benchmark on return in every year and clearly wins on drawdown only in
  2022 (5.4% vs 16.3%). B beats the benchmark only in 2025 (+6.6% vs −5.6%), and in 2026 to date it made −8.1%
  (Sharpe −0.93).

### F6. Costs are not what fails. Severity: LOW

**Evidence** (§5): Sharpe at x1/x2/x3/x4 costs is A 0.624/0.565/0.508/0.450 and B 0.423/0.393/0.362/0.332.
Criterion 5 passes with a wide margin, and higher costs only make criteria 1 and 8 worse.

### F7. Data issues. Severity: LOW (symmetric)

**Evidence** (§7, `postrun_combined.txt`):

- **GLD 2026-01-30 return of −10.27%** in the adjusted close (bars 494.56 → 495.90 → 444.95).
  `data-quality.md` notes it was not cross-checked.
  - The strategy held 13.8% GLD going into that day, and the benchmark held 22.8%.
  - Setting that day's GLD return to 0: strategy Sharpe 0.673, benchmark 0.921. The gap barely changes.
  - Combined with T-bill cash: 0.882 vs 0.922, criterion 8 still FAIL.
  - **Opinion:** a large gold drop at end-January 2026 is plausible, but whether this is the true size is
    insufficient data. Either way, it cannot flip the verdict.
- **Yahoo adjusted prices** (verified for SPY dividends, `data-quality.md` §3) apply to the strategy and the
  benchmark alike, and the pinned `bars_sha256` ensures IS and OOS used the same cache.
- **Other OOS extremes** (SPY +10.5% on 2025-04-09, BTC −14.0% on 2026-02-05, ETH +21.9% on 2025-05-08): the
  strategy held 0% on each of these days.
- **Survivorship and hindsight** (criteria §1) flatter the strategy and the benchmark alike. This does not
  rescue a FAIL.

### F8. The "-dirty" commit on B's OOS run is harmless. Severity: NONE

**Evidence:**
- `git diff 122acf3 3792509 -- src tests config pyproject.toml uv.lock | wc -l` returns **0**.
- `git diff --stat 122acf3 3792509` lists only `reports/backtest-{A,B}-oos.md`, `oos_runs.jsonl`,
  `variants.{jsonl,md}`.
- A's run wrote those tracked files 1 s before B's run, and my re-run from the clean `src/` reproduces B exactly.
- `git log -- reports/variants.jsonl reports/oos_runs.jsonl` shows only the two Phase 5 commits, so N = 12 per
  market holds.

### F9 (minor). The IS benchmark B hit the kill switch

`variants.md`: the IS benchmark B ended at $145.3 with 8 fills and 2 round trips, consistent with the 50% kill
switch firing. Its IS Sharpe (−0.70) is not a buy-and-hold figure. This affects the IS report only, not any
criterion. Owner: backtest-engineer, to note it in the IS report.

## Numbers that cannot be trusted (and why)

1. **A criterion 3, 24.6 months underwater.** It is mostly produced by zero cash yield at 3-5% T-bill rates;
   with T-bill cash it is 16.1 months (F1). The criterion is valid as pre-registered, but it does not show that
   the strategy lost money.
2. **B Sharpe 0.423 (criterion 1).** It is bracketed by 0.369 (one-day latency plus T-bill cash) and 0.511
   (T-bill cash, zero latency). The pass/fail on criterion 1 sits inside this band (F1, F3).
3. **B max drawdown 34.77% "PASS" on criterion 2.** It is 0.23 pp from the 35% limit and becomes 35.22% at x2
   costs and 35.67% at x3. It is a coin-flip pass.
4. **B criterion 3 "PASS", 17.0 months.** It is 1 month from the limit, and 30.6 months under one-day latency
   (logged sensitivity).
5. **Deflated Sharpe ratios 0.936 (A) and 0.983 (B).** They are generous because the trials are highly
   correlated. B's IS-to-OOS rank correlation of 0.03 shows that the IS ranking carried no information (F2).
6. **Walk-forward Sharpe of B, 1.139.** It is an IS figure from a 2019-2023 crypto regime that did not repeat
   (OOS median across the 12 variants is 0.49).
7. **Every OOS Sharpe to ±0.1-0.2.** About 5 trends make the result (F4), and start shifts move the Sharpe by
   up to 0.24 (F5).
8. **A benchmark Sharpe 0.874.** It includes the unverified GLD −10.3% day (F7). Removing that day raises the
   benchmark to 0.921, which widens the gap.

## Bottom line

**Evidence:** neither FAIL is an artefact.
- Criterion 8 fails for both markets under every perturbation and combination tested.
- In A no variant beats the benchmark Sharpe. B's failure persists across start dates, costs and latency.

**Opinion:** the honest summary for the VERDICT has three parts:
- **A:** trend following delivered a lower drawdown (7.5% vs 16.3%) but a lower Sharpe than simply holding the
  five ETFs. The "24.6 months underwater" mostly reflects uninvested cash in a high-rate period.
- **B:** trend following roughly halved the drawdown (34.8% vs 60.2%), at a large cost in Sharpe and return. The
  IS winner ranked near the bottom OOS.
- **Both:** no evidence of a risk-adjusted edge over the passive benchmark, which is what the pre-registration
  tested.
