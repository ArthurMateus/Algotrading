"""Post-run skeptic diagnostics (Phase 5). REPORTED ONLY: never changes a verdict, never re-selects.
Reads the cached data/ (no fetch) and calls engine.run directly. Writes nothing under reports/ except stdout
redirected by the caller. Never touches reports/variants*, oos_runs.jsonl, selected-*, is_selection_*.
Run: uv run python -X utf8 reports/skeptic/postrun_diagnostics.py A   (or B)"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from algotrade import data, engine, evaluate, strategy  # noqa: E402
from algotrade import metrics as M  # noqa: E402
from algotrade.config import load_config  # noqa: E402

m = sys.argv[1]
cfg = load_config(m)
panel = data.build_panel(data.load_bars(cfg), cfg.end_date)
mo, lot = data.min_order_usd(cfg), data.lot_step(cfg)
split = evaluate.make_split(panel, cfg)
rf = data.load_aux(cfg, panel.close.index).rf_per_bar
ppy = cfg.periods_per_year
sel = evaluate.load_selection(cfg)["selected"]["key"]
SYMS = list(cfg.instruments)
BENCH_T = strategy.benchmark_weights(panel)[SYMS]


def run(key, start, end, mult=1.0, p=panel):
    if key == "benchmark":
        t, reb, band = BENCH_T, "monthly", 0.0
    else:
        v = evaluate._parse_key(key)
        t, reb, band = strategy.target_weights(p, v, cfg), v.rebalance, None
    dd = strategy.decision_dates(p.close.index, reb)
    return engine.run(p, t, dd, cfg, start=start, end=end, cost_mult=mult, band=band, min_order=mo, lot=lot,
                      label=key)


def stats(eq, ret=None):
    ret = eq.pct_change().fillna(0.0) if ret is None else ret
    _, _, uw, _ = M.longest_underwater(eq)
    return dict(sh=M.sharpe(ret, rf, ppy), dd=M.max_drawdown(eq), uw=uw, cagr=M.cagr(eq), fin=float(eq.iloc[-1]))


def fmt(d):
    return f"Sharpe {d['sh']:.3f}  maxDD {d['dd']*100:5.2f}%  UW {d['uw']:5.1f}m  CAGR {d['cagr']*100:6.2f}%  $ {d['fin']:.1f}"


def c8(s, b):
    return "PASS" if (s["sh"] >= b["sh"] and s["dd"] <= b["dd"]) else "FAIL"


def tbill_equity(res):
    """Idle cash earns the T-bill: add (1 - gross weight at prior close) * rf_t to each daily return."""
    cash_share = (1.0 - res.weights.sum(axis=1)).shift(1).fillna(1.0).clip(lower=0.0)
    r = res.returns + cash_share * rf.reindex(res.returns.index).fillna(0.0)
    r.iloc[0] = 0.0
    return (1 + r).cumprod() * float(res.equity.iloc[0]), r


W = (split.oos_start, split.oos_end)
print(f"== Market {m}: selected {sel}; OOS {W[0]}..{W[1]} ({split.n_oos} bars); rf mean annual "
      f"{rf.loc[W[0]:W[1]].mean()*ppy*100:.2f}%")

print("\n== 0. Reproduction of the logged OOS run (must match backtest-{m}-oos.md)")
rs, rb = run(sel, *W), run("benchmark", *W)
S, B = stats(rs.equity), stats(rb.equity)
print(f"strategy : {fmt(S)}  round trips {M.round_trips(rs.fills)}")
print(f"benchmark: {fmt(B)}  -> criterion 8 {c8(S, B)}")

print("\n== 1. Idle cash earns the T-bill (strategy and benchmark)")
es, r_s = tbill_equity(rs)
eb, r_b = tbill_equity(rb)
S1, B1 = stats(es, r_s), stats(eb, r_b)
print(f"strategy : {fmt(S1)}   (mean cash share {(1-rs.weights.sum(axis=1)).mean()*100:.1f}%)")
print(f"benchmark: {fmt(B1)}")
print(f"-> criterion 8 with T-bill cash: {c8(S1, B1)}; crit 1 {S1['sh']:.3f}; crit 3 UW {S1['uw']:.1f}m")
for mult in (2.0,):
    r2 = run(sel, *W, mult=mult)
    e2, rr2 = tbill_equity(r2)
    print(f"x{mult:.0f} costs + T-bill cash: {fmt(stats(e2, rr2))}")

print("\n== 2. All 12 grid variants on OOS (POST-HOC, information only, NOT usable for selection)")
print("IS Sharpe from is_selection; OOS at x1 costs; T-bill-cash Sharpe in last column")
is_sh = evaluate.load_selection(cfg)["is_sharpe"]
rows = []
for v in strategy.grid(cfg):
    r = run(v.key, *W)
    st = stats(r.equity)
    e_t, r_t = tbill_equity(r)
    stt = stats(e_t, r_t)
    rows.append((v.key, is_sh.get(v.key), st, M.round_trips(r.fills), c8(st, B), stt["sh"], c8(stt, B1)))
for k, ish, st, rt, c, tsh, tc in rows:
    star = " <- selected" if k == sel else ""
    print(f"{k:18s} IS {ish:6.3f} | OOS {fmt(st)} RT {rt:3d} c8 {c} | Tbill Sharpe {tsh:.3f} c8 {tc}{star}")
oos_sh = [r[2]["sh"] for r in rows]
print(f"OOS Sharpe across 12: min {min(oos_sh):.3f} median {np.median(oos_sh):.3f} max {max(oos_sh):.3f}; "
      f"variants beating bench Sharpe {B['sh']:.3f}: {sum(s >= B['sh'] for s in oos_sh)}/12")
print(f"Spearman(IS Sharpe, OOS Sharpe) = "
      f"{pd.Series([r[1] for r in rows]).rank().corr(pd.Series(oos_sh).rank()):.2f}")

print("\n== 3a. Start-date shifts (end fixed at OOS end). Negative shifts start inside IS (diagnostic only)")
idx = panel.close.index
for k in (-6, -3, 0, 3, 6):
    t0 = pd.Timestamp(W[0]) + pd.DateOffset(months=k)
    s0 = idx[idx >= t0][0].date().isoformat()
    a, b = stats(run(sel, s0, W[1]).equity), stats(run("benchmark", s0, W[1]).equity)
    print(f"start {s0} ({k:+d}m): strat Sharpe {a['sh']:.3f} DD {a['dd']*100:5.2f}% UW {a['uw']:5.1f}m | "
          f"bench Sharpe {b['sh']:.3f} DD {b['dd']*100:5.2f}% UW {b['uw']:5.1f}m | c8 {c8(a, b)}")

print("\n== 3b. Calendar sub-periods of the logged OOS run (slices of one continuous run)")
for y in sorted(set(rs.equity.index.year)):
    sl = rs.equity.index.year == y
    if sl.sum() < 20:
        continue
    a, b = rs.equity[sl], rb.equity[sl]
    sa, sb = M.sharpe(rs.returns[sl], rf, ppy), M.sharpe(rb.returns[sl], rf, ppy)
    print(f"{y}: strat ret {(a.iloc[-1]/a.iloc[0]-1)*100:6.1f}% Sharpe {sa:6.2f} DD {M.max_drawdown(a)*100:5.1f}% | "
          f"bench ret {(b.iloc[-1]/b.iloc[0]-1)*100:6.1f}% Sharpe {sb:6.2f} DD {M.max_drawdown(b)*100:5.1f}%")

print("\n== 4. Concentration (close-to-close attribution: w[t-1] * asset return[t]; approximate)")
ar = panel.close[SYMS].pct_change().reindex(rs.returns.index).fillna(0.0)
wprev = rs.weights.shift(1).fillna(0.0)
contrib = wprev * ar
resid = rs.returns - contrib.sum(axis=1)
print(f"attribution check: corr(sum contrib, actual return) {np.corrcoef(contrib.sum(axis=1), rs.returns)[0,1]:.4f}; "
      f"sum residual {resid.sum()*100:.2f}% (costs + open-vs-close fill effects)")
print("per instrument: sum of daily contributions (pp) and strategy Sharpe without it (its contribs set to 0)")
for s in SYMS:
    print(f"  {s:8s} {contrib[s].sum()*100:6.2f} pp   Sharpe w/o {M.sharpe(rs.returns - contrib[s], rf, ppy):.3f}"
          f"   exposure {rs.weights[s].mean()*100:.1f}%")
trades = []
for s in SYMS:
    held = (wprev[s] > 1e-9).to_numpy()
    tid = np.cumsum(np.r_[held[0], held[1:] & ~held[:-1]]) * held
    for t in np.unique(tid[tid > 0]):
        msk = tid == t
        trades.append((s, rs.returns.index[msk][0].date(), int(msk.sum()), contrib[s][msk].sum(), msk))
trades.sort(key=lambda x: -x[3])
print(f"trades (holding spells): {len(trades)}; top 5:")
for s, d0, n, c, _ in trades[:5]:
    print(f"  {s:8s} from {d0} {n:4d} bars  {c*100:6.2f} pp")
drop = pd.Series(0.0, index=rs.returns.index)
for s, _, _, _, msk in trades[:5]:
    drop[msk] += contrib[s][msk]
r_drop = rs.returns - drop
e_drop = (1 + r_drop).cumprod() * 300.0
print(f"drop top-5 trades: {fmt(stats(e_drop, r_drop))}")
print(f"share of total contribution from top 5: {sum(t[3] for t in trades[:5]) / contrib.sum().sum()*100:.0f}%")

print("\n== 5. Cost stress beyond x2 (x3, x4)")
for mult in (3.0, 4.0):
    print(f"x{mult:.0f}: {fmt(stats(run(sel, *W, mult=mult).equity))}")

print("\n== 7. Data: largest |daily return| per instrument in OOS, and held weight that day")
for s in SYMS:
    r = panel.close[s].pct_change().loc[W[0]:W[1]]
    d = r.abs().idxmax()
    print(f"  {s:8s} {d.date()} {r[d]*100:6.2f}%  strat weight prior close {wprev[s].get(d, 0)*100:.1f}%  "
          f"bench {rb.weights[s].shift(1).get(d, 0)*100:.1f}%")
if m == "A":
    d = pd.Timestamp("2026-01-30")
    g = panel.close["GLD"]
    print("GLD around 2026-01-30 (adj close, open):")
    print(pd.DataFrame({"close": g, "open": panel.open["GLD"]}).loc["2026-01-26":"2026-02-05"].round(3).to_string())
    # Remove the outlier day: neutralise GLD's return on that day for both runs
    for name, res in (("strategy", rs), ("benchmark", rb)):
        w = res.weights["GLD"].shift(1).fillna(0.0)
        r_fix = res.returns.copy()
        r_fix[d] = r_fix[d] - w[d] * ar.loc[d, "GLD"]
        e_fix = (1 + r_fix).cumprod() * 300.0
        print(f"  {name} with GLD 2026-01-30 return set to 0: {fmt(stats(e_fix, r_fix))}")
