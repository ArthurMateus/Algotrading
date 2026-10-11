"""Pre-run skeptic audit on SYNTHETIC data only (tests/synth.py). Never reads data/, never writes reports/variants*,
reports/oos_runs.jsonl, reports/selected-*, reports/is_selection_*: every run uses a temp reports dir.
Run: uv run python -X utf8 reports/skeptic/preflight_audit.py"""
import dataclasses
import math
import sys
import tempfile
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from algotrade import engine, evaluate, strategy  # noqa: E402
from algotrade import metrics as M  # noqa: E402
from algotrade.broker import CostModel, Order, PaperBroker  # noqa: E402
from algotrade.config import load_config  # noqa: E402
from algotrade.data import Aux, Panel, build_panel  # noqa: E402
from tests.synth import synth_market  # noqa: E402


def aux(index):
    idx = pd.DatetimeIndex(index)
    return Aux(rf_per_bar=pd.Series(0.0001, index=idx), rf_available=True, ptax=pd.Series(5.0, index=idx),
               cdi_daily=pd.Series(0.0004, index=idx), cdi_business_day=pd.Series(idx.dayofweek < 5, index=idx))


def cfg_tmp(m):
    d = Path(tempfile.mkdtemp(prefix=f"skeptic_{m}_"))
    return dataclasses.replace(load_config(m), reports_dir=d, data_dir=d / "data")


def mo_lot(cfg):
    a = cfg.name == "A"
    return ({s: (1.0 if a else 5.0) for s in cfg.instruments}, {s: (0.0 if a else 0.00001) for s in cfg.instruments})


def kw(cfg, panel):
    mo, lot = mo_lot(cfg)
    return dict(cfg=cfg, panel=panel, aux_fn=aux, min_order=mo, lot=lot, git_commit="skeptic")


def shock_after(p, t, seed=1):
    rng = np.random.default_rng(seed)
    sh = pd.DataFrame(rng.uniform(0.5, 2.0, p.close.shape), index=p.close.index, columns=p.close.columns)
    sh.loc[sh.index <= t] = 1.0
    return Panel(open=p.open * sh, close=p.close * sh, valid=p.valid, adjusted=p.adjusted)


def market(m, n):
    cfg = load_config(m)
    bars = synth_market(list(cfg.instruments), "2010-01-01", n, seed=7, daily=(m == "B"))
    return build_panel(bars, "2030-01-01")


def sim(p, cfg, targets, reb, window, mult, band, label):
    mo, lot = mo_lot(cfg)
    return evaluate._simulate(p, cfg, targets, reb, window, mult, band, mo, lot, label)


print("== T1/T2 leakage: IS invariant to post-IS bars; OOS invariant to bars after t ==")
for m, n in (("A", 1400), ("B", 1300)):
    p = market(m, n)
    c1 = cfg_tmp(m)
    a = evaluate.run_is(m, **kw(c1, p))
    sp = a["split"]
    p2 = shock_after(p, pd.Timestamp(sp["is_end"]))
    c2 = cfg_tmp(m)
    b = evaluate.run_is(m, **kw(c2, p2))
    same = (a["is_sharpe"] == b["is_sharpe"] and a["selected"] == b["selected"] and a["wf_sharpe"] == b["wf_sharpe"]
            and (a["dsr"] == b["dsr"] or (math.isnan(a["dsr"]) and math.isnan(b["dsr"]))))
    print(f"[{m}] IS {sp['is_start']}..{sp['is_end']}, OOS {sp['oos_start']}..{sp['oos_end']}; selected "
          f"{a['selected']}; IS sharpes/selection/WF/DSR identical after shocking every post-IS bar: {same}")
    v = evaluate._parse_key(a["selected"])
    win = (sp["oos_start"], sp["oos_end"])
    oidx = p.close.index[p.close.index >= pd.Timestamp(sp["oos_start"])]
    k = oidx[len(oidx) // 2]
    p3 = shock_after(p, k)
    e1 = sim(p, c1, strategy.target_weights(p, v, c1), v.rebalance, win, 1.0, None, v.key)
    e3 = sim(p3, c1, strategy.target_weights(p3, v, c1), v.rebalance, win, 1.0, None, v.key)
    print(f"[{m}] OOS equity up to {k.date()} unchanged when later bars are shocked: "
          f"{e1.equity.loc[:k].equals(e3.equity.loc[:k])}; later equity changed: "
          f"{not e1.equity.loc[k:].equals(e3.equity.loc[k:])}; first OOS fill {e1.fills[0].date if e1.fills else None}"
          f" (OOS bar 0 = {sp['oos_start']}, equity day0 {e1.equity.iloc[0]})")
    bres = sim(p, c1, strategy.benchmark_weights(p)[list(c1.instruments)], "monthly", win, 1.0, 0.0, "benchmark")
    print(f"[{m}] OOS skips strategy {evaluate._skip_counts(e1)} benchmark {evaluate._skip_counts(bres)}")

print("\n== T4 cost hand-check (one $60 round trip, open 100 -> 100) ==")
for m in ("A", "B"):
    cfg = load_config(m)
    for mult in (1.0, 2.0):
        br = PaperBroker(CostModel.from_config(cfg.costs, mult), {s: 0.0 for s in cfg.instruments},
                         {s: 0.0 for s in cfg.instruments})
        s = cfg.instruments[0]
        fb, _ = br.execute([Order(s, "buy", "entry", 0.2, "d0", "d1")], {s: 100.0}, 300.0, {})
        f = fb[0]
        cash = 300.0 + f.cash_delta
        fs, _ = br.execute([Order(s, "sell", "exit", 0.0, "d1", "d2")], {s: 100.0}, cash, {s: f.qty})
        g = fs[0]
        end = cash + g.cash_delta
        print(f"[{m}] x{mult:g}: buy {f.qty:.6f}@{f.price:.4f} com {f.commission:.5f} reg {f.regulatory:.6f}; "
              f"sell @{g.price:.4f} com {g.commission:.5f} reg {g.regulatory:.6f}; round trip "
              f"{300 - end:.5f} USD = {(300 - end) / (f.qty * 100) * 100:.4f}% of notional")

print("\n== T5 cap clamp effect (benchmark, synthetic A, 1100 bars) ==")
p = market("A", 1400)
c = cfg_tmp("A")
win = (str(p.close.index[300].date()), str(p.close.index[-1].date()))
bt = strategy.benchmark_weights(p)[list(c.instruments)]
with_clamp = sim(p, c, bt, "monthly", win, 1.0, 0.0, "benchmark")
orig = engine._clamp_to_gate_cap
engine._clamp_to_gate_cap = lambda gate, broker, orders, *a, **k: orders
try:
    no_clamp = sim(p, c, bt, "monthly", win, 1.0, 0.0, "benchmark")
finally:
    engine._clamp_to_gate_cap = orig
for name, r in (("with clamp", with_clamp), ("without clamp", no_clamp)):
    print(f"{name}: final {r.equity.iloc[-1]:.4f}, Sharpe {M.sharpe(r.returns, None, 252):.4f}, MDD "
          f"{M.max_drawdown(r.equity):.4%}, exposure {M.exposure(r.weights):.5f}, skips {evaluate._skip_counts(r)}")

print("\n== T6 DSR vs an independent implementation ==")
rng = np.random.default_rng(0)
x = pd.Series(rng.standard_t(4, 2000) * 0.01 + 0.0006)
sr = M.per_bar_sharpe(x, None)
sk, ku, n = M.moments(x, None)
trials = list(rng.normal(0.02, 0.01, 11)) + [sr]
Z, g, N = NormalDist().inv_cdf, 0.5772156649015329, 12
sr0 = np.std(trials, ddof=1) * ((1 - g) * Z(1 - 1 / N) + g * Z(1 - 1 / (N * math.e)))
ref = NormalDist().cdf((sr - sr0) * math.sqrt(n - 1) / math.sqrt(1 - sk * sr + (ku - 1) / 4 * sr ** 2))
print(f"DSR code {M.deflated_sharpe(sr, trials, n, sk, ku):.6f} vs reference {ref:.6f}")

print("\n== T7 day-0 zero return inside Sharpe ==")
r = pd.Series([0.0] + list(rng.normal(0.0004, 0.01, 1500)))
print(f"Sharpe with day0 {M.sharpe(r, None, 252):.5f} vs without {M.sharpe(r.iloc[1:], None, 252):.5f}")

print("\n== T8 clamp vs an ideal gate (instrument cap relaxed, clamp off) ==")
from algotrade import risk  # noqa: E402
_init = risk.RiskGate.__init__


def _relaxed(self, *a, **k):
    _init(self, *a, **k)
    self.instrument_cap = 1.0


for m, n in (("A", 1400), ("B", 1300)):
    p = market(m, n)
    c = cfg_tmp(m)
    win = (str(p.close.index[300].date()), str(p.close.index[-1].date()))
    bt = strategy.benchmark_weights(p)[list(c.instruments)]
    base = sim(p, c, bt, "monthly", win, 1.0, 0.0, "benchmark")
    risk.RiskGate.__init__ = _relaxed
    engine._clamp_to_gate_cap = lambda gate, broker, orders, *a, **k: orders
    try:
        ideal = sim(p, c, bt, "monthly", win, 1.0, 0.0, "benchmark")
    finally:
        risk.RiskGate.__init__ = _init
        engine._clamp_to_gate_cap = orig
    ppy = c.periods_per_year
    print(f"[{m}] benchmark clamp: final {base.equity.iloc[-1]:.4f} Sharpe {M.sharpe(base.returns, None, ppy):.5f} "
          f"MDD {M.max_drawdown(base.equity):.5%} | ideal: final {ideal.equity.iloc[-1]:.4f} Sharpe "
          f"{M.sharpe(ideal.returns, None, ppy):.5f} MDD {M.max_drawdown(ideal.equity):.5%} | ideal max weight "
          f"{ideal.weights.max().max():.5f} (1/N={1/len(c.instruments):.5f})")
