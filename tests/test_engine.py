"""Engine: fill at the next open, band, costs (x1/x2), gate refusals, kill switch, exit retry, no look-ahead,
deterministic replay. Synthetic data only (hand-built panels and tests/synth.py); nothing touches data/ or reports/."""
import dataclasses
import math

import numpy as np
import pandas as pd
import pytest

from algotrade import engine, strategy
from algotrade.config import Costs, load_config
from algotrade.data import Panel, build_panel
from algotrade.ledger import State
from tests.synth import synth_market

COM, SLIP = 0.001, 0.001          # simple hand-checkable costs: 0.1% commission, 0.1% slippage, no SEC/TAF


def cfg_for(symbols, **kw):
    costs = Costs(commission_rate=COM, sec_fee_rate_sell=0.0, taf_per_share_sell=0.0, taf_max_per_trade=0.0,
                  slippage_rate=SLIP, min_order_usd=1.0)
    return dataclasses.replace(load_config("A"), instruments=tuple(symbols), costs=costs, **kw)


def hand_panel(opens: dict, closes: dict, start="2024-01-01", valid: dict | None = None) -> Panel:
    n = len(next(iter(opens.values())))
    idx = pd.date_range(start, periods=n, freq="D", name="date")
    o = pd.DataFrame(opens, index=idx, dtype="float64")
    c = pd.DataFrame(closes, index=idx, dtype="float64")
    v = pd.DataFrame(valid, index=idx, dtype=bool) if valid else (o.notna() & c.notna())
    return Panel(open=o.where(v), close=c.where(v), valid=v, adjusted="total_return")


def targets_of(panel, rows: dict) -> pd.DataFrame:
    """rows: {bar number: {symbol: weight}}; everything else NaN (= hold)."""
    t = pd.DataFrame(np.nan, index=panel.close.index, columns=panel.close.columns)
    for i, w in rows.items():
        for s, x in w.items():
            t.iloc[i, t.columns.get_loc(s)] = x
    return t


def run(panel, tg, cfg, dec_rows=(), **kw):
    idx = panel.close.index
    kw.setdefault("min_order", {s: 1.0 for s in cfg.instruments})
    kw.setdefault("lot", {s: 0.0 for s in cfg.instruments})
    return engine.run(panel, tg, idx[list(dec_rows)], cfg, start=str(idx[0].date()), end=str(idx[-1].date()), **kw)


# ---------------------------------------------------------------- hand-computed single trade

def test_inception_decision_fills_at_next_open_with_costs():
    cfg = cfg_for(["X"])
    p = hand_panel({"X": [9.0, 10.0, 12.0, 12.0]}, {"X": [9.5, 11.0, 12.0, 12.0]})
    res = run(p, targets_of(p, {0: {"X": 0.5}}), cfg)
    assert len(res.fills) == 1
    f = res.fills[0]
    # decided at the close of bar 0 (equity 300), filled at the open of bar 1 (10.0)
    assert f.date == "2024-01-02" and f.side == "buy" and f.kind == "entry"
    assert f.qty == pytest.approx(15.0)                          # 0.5 * 300 / 10
    assert f.price == pytest.approx(10.01)                       # open * (1 + 0.1%)
    assert f.commission == pytest.approx(0.001 * 15 * 10.01)
    assert f.slippage_cost == pytest.approx(15 * 0.01)
    cash = 300 - 15 * 10.01 - 0.001 * 15 * 10.01
    assert res.equity.iloc[0] == 300.0
    assert res.equity.iloc[1] == pytest.approx(cash + 15 * 11.0)  # marked at the bar-1 close
    assert res.equity.iloc[2] == pytest.approx(cash + 15 * 12.0)
    assert res.returns.iloc[0] == 0.0
    assert res.weights["X"].iloc[1] == pytest.approx(15 * 11.0 / res.equity.iloc[1])


def test_price_shock_at_fill_close_does_not_change_the_fill():
    cfg = cfg_for(["X"])
    a = hand_panel({"X": [9.0, 10.0, 12.0]}, {"X": [9.5, 11.0, 12.0]})
    b = hand_panel({"X": [9.0, 10.0, 12.0]}, {"X": [9.5, 50.0, 12.0]})       # shock at the t+1 close
    ra, rb = (run(p, targets_of(p, {0: {"X": 0.5}}), cfg) for p in (a, b))
    assert ra.fills == rb.fills


def test_doubled_costs():
    cfg = cfg_for(["X"])
    p = hand_panel({"X": [9.0, 10.0, 12.0]}, {"X": [9.5, 11.0, 12.0]})
    r1 = run(p, targets_of(p, {0: {"X": 0.5}}), cfg)
    r2 = run(p, targets_of(p, {0: {"X": 0.5}}), cfg, cost_mult=2.0)
    f1, f2 = r1.fills[0], r2.fills[0]
    assert f2.price == pytest.approx(10.02)
    assert f2.commission == pytest.approx(0.002 * f2.qty * 10.02)
    assert f2.slippage_cost == pytest.approx(2 * f1.slippage_cost)
    assert r2.equity.iloc[-1] < r1.equity.iloc[-1]
    assert r2.cost_mult == 2.0


# ---------------------------------------------------------------- band, entries, exits

def _held_weight_at(bar: int):
    cfg = cfg_for(["X"])
    p = hand_panel({"X": [10.0] * 6}, {"X": [10.0, 10.0, 10.5, 10.5, 10.5, 10.5]})
    base = run(p, targets_of(p, {0: {"X": 0.5}}), cfg)
    return cfg, p, float(base.weights["X"].iloc[bar])


@pytest.mark.parametrize("delta, trades", [(0.019, False), (-0.019, False), (0.021, True), (-0.021, True)])
def test_rebalance_band(delta, trades):
    cfg, p, w = _held_weight_at(2)
    res = run(p, targets_of(p, {0: {"X": 0.5}, 2: {"X": w + delta}}), cfg, dec_rows=[2])
    rebal = [f for f in res.fills if f.kind == "rebalance"]
    assert bool(rebal) is trades
    if trades:
        assert rebal[0].date == "2024-01-04" and rebal[0].side == ("buy" if delta > 0 else "sell")


def test_benchmark_band_zero_trades_small_deltas():
    cfg, p, w = _held_weight_at(2)
    res = run(p, targets_of(p, {0: {"X": 0.5}, 2: {"X": w + 0.005}}), cfg, dec_rows=[2], band=0.0)
    assert [f.kind for f in res.fills] == ["entry", "rebalance"]


def test_small_entry_and_exit_always_trade():
    cfg = cfg_for(["X"])
    p = hand_panel({"X": [10.0] * 5}, {"X": [10.0] * 5})
    res = run(p, targets_of(p, {0: {"X": 0.01}, 2: {"X": 0.0}}), cfg, dec_rows=[2])   # both below the 2% band
    assert [(f.kind, f.side) for f in res.fills] == [("entry", "buy"), ("exit", "sell")]
    assert res.fills[1].qty == pytest.approx(res.fills[0].qty)
    assert res.ledger.replay().positions == {}


def test_nan_target_holds_and_last_bar_decision_is_ignored():
    cfg = cfg_for(["X"])
    p = hand_panel({"X": [10.0] * 4}, {"X": [10.0] * 4})
    res = run(p, targets_of(p, {0: {"X": 0.5}, 3: {"X": 0.0}}), cfg, dec_rows=[2, 3])  # row 2 target is NaN
    assert len(res.fills) == 1


def test_exit_below_minimum_is_sold_and_counted():
    cfg = cfg_for(["X"])
    p = hand_panel({"X": [10.0] * 5}, {"X": [10.0] * 5})
    res = run(p, targets_of(p, {0: {"X": 0.01}, 2: {"X": 0.0}}), cfg, dec_rows=[2],
              min_order={"X": 5.0})
    # the entry ($3) is below the $5 minimum and is skipped -> nothing to exit; so enter with 0.02 ($6) instead
    assert not res.fills and res.skips[0].reason == "below_min_order"
    p2 = hand_panel({"X": [10.0, 10.0, 10.0, 5.0, 5.0]}, {"X": [10.0, 10.0, 10.0, 5.0, 5.0]})
    res2 = run(p2, targets_of(p2, {0: {"X": 0.02}, 2: {"X": 0.0}}), cfg, dec_rows=[2], min_order={"X": 5.0})
    assert [f.kind for f in res2.fills] == ["entry", "exit"]
    assert res2.fills[1].below_min and res2.below_min_exits == 1


def test_exit_without_bar_is_retried_at_next_open():
    cfg = cfg_for(["X", "Y"])
    opens = {"X": [10.0] * 6, "Y": [20.0] * 6}
    valid = {"X": [True] * 6, "Y": [True, True, True, False, True, True]}
    p = hand_panel(opens, opens, valid=valid)
    res = run(p, targets_of(p, {0: {"X": 0.2, "Y": 0.2}, 2: {"Y": 0.0}}), cfg, dec_rows=[2])
    assert any(s.symbol == "Y" and s.reason == "no_bar" and s.date == "2024-01-04" for s in res.skips)
    ex = [f for f in res.fills if f.kind == "exit"]
    assert len(ex) == 1 and ex[0].symbol == "Y" and ex[0].date == "2024-01-05"
    # equity on the no-bar day values Y at its last close
    assert not math.isnan(res.equity.iloc[3])


# ---------------------------------------------------------------- risk gate / kill switch

def test_kill_switch_at_close_exits_next_open_and_stops_decisions():
    cfg = cfg_for(["X"])
    px = [10.0, 10.0, 4.0, 4.0, 4.0, 4.0, 4.0]       # the bar-2 close values the position at ~40% of start
    p = hand_panel({"X": px}, {"X": px})
    res = run(p, targets_of(p, {0: {"X": 1.0}, 4: {"X": 1.0}}), cfg, dec_rows=[4])
    assert res.killed_on == "2024-01-03"
    kinds = [(f.date, f.kind, f.side) for f in res.fills]
    assert kinds == [("2024-01-02", "entry", "buy"), ("2024-01-04", "exit", "sell")]
    events = res.ledger.events()
    assert [e["type"] for e in events].count("kill") == 1
    decisions = [e for e in events if e["type"] == "decision"]
    assert [d["reason"] for d in decisions] == ["inception", "kill_switch"]     # no strategy decision after it
    st = res.ledger.replay()
    assert st.killed and st.positions == {}


def test_gate_refuses_a_target_above_the_instrument_cap():
    cfg = cfg_for(["X", "Y"])                         # cap 1/N = 0.5
    p = hand_panel({"X": [10.0] * 4, "Y": [10.0] * 4}, {"X": [10.0] * 4, "Y": [10.0] * 4})
    res = run(p, targets_of(p, {0: {"X": 0.8, "Y": 0.5}}), cfg)
    assert [s.reason for s in res.skips] == ["risk_gate:instrument_cap"] and res.skips[0].symbol == "X"
    assert [f.symbol for f in res.fills] == ["Y"]     # a target of exactly 1/N passes (clamped by batch costs)
    assert res.fills[0].qty * 10.0 == pytest.approx(150.0, rel=5e-3)


def test_gate_never_refuses_on_valid_strategy_and_benchmark_runs():
    cfg = load_config("A")
    p = build_panel(synth_market(list(cfg.instruments), "2015-01-01", 700, daily=False), "2030-01-01")
    mo = {s: 1.0 for s in cfg.instruments}
    lo = {s: 0.0 for s in cfg.instruments}
    s0, s1 = str(p.close.index[300].date()), str(p.close.index[-1].date())
    v = strategy.Variant("TSMOM", 63, "weekly")
    rs = engine.run(p, strategy.target_weights(p, v, cfg), strategy.decision_dates(p.close.index, "weekly"), cfg,
                    start=s0, end=s1, min_order=mo, lot=lo)
    rb = engine.run(p, strategy.benchmark_weights(p), strategy.decision_dates(p.close.index, "monthly"), cfg,
                    start=s0, end=s1, band=0.0, min_order=mo, lot=lo)
    for r in (rs, rb):
        assert r.fills
        assert not [s for s in r.skips if s.reason.startswith("risk_gate")]
        st = State()
        for ev in r.ledger.events():                   # cash never negative, gross never above 100% at a mark
            st.apply(ev)
            assert st.cash >= -1e-9
        assert (r.weights.sum(axis=1) <= 1.0 + 1e-9).all()
    assert rb.weights.sum(axis=1).iloc[30] == pytest.approx(1.0, abs=0.01)   # fully invested benchmark


# ---------------------------------------------------------------- lot steps (B)

def test_lot_step_floors_buys():
    cfg = cfg_for(["X"])
    p = hand_panel({"X": [100.0, 100.0, 100.0]}, {"X": [100.0] * 3})
    res = run(p, targets_of(p, {0: {"X": 0.55}}), cfg, lot={"X": 0.1})
    assert res.fills[0].qty == pytest.approx(1.6)          # 0.55 * 300 / 100 = 1.65 wanted, floored to the step


# ---------------------------------------------------------------- look-ahead and determinism

def _synth_run(panel, cfg, **kw):
    v = strategy.Variant("SMA", 63, "weekly")
    idx = panel.close.index
    return engine.run(panel, strategy.target_weights(panel, v, cfg), strategy.decision_dates(idx, "weekly"), cfg,
                      start=str(idx[260].date()), end=str(idx[-1].date()),
                      min_order={s: 5.0 for s in cfg.instruments}, lot={s: 0.00001 for s in cfg.instruments}, **kw)


def test_no_look_ahead_changing_future_bars_keeps_the_past():
    cfg = load_config("B")
    bars = synth_market(list(cfg.instruments), "2019-01-01", 600, seed=3)
    p = build_panel(bars, "2030-01-01")
    t = p.close.index[450]
    rng = np.random.default_rng(9)
    shock = pd.DataFrame(rng.uniform(0.3, 3.0, p.close.shape), index=p.close.index, columns=p.close.columns)
    shock.loc[shock.index <= t] = 1.0
    p2 = Panel(open=p.open * shock, close=p.close * shock,
               valid=p.valid, adjusted=p.adjusted)
    a, b = _synth_run(p, cfg), _synth_run(p2, cfg)
    pd.testing.assert_series_equal(a.equity.loc[:t], b.equity.loc[:t])
    assert [f for f in a.fills if f.date <= str(t.date())] == [f for f in b.fills if f.date <= str(t.date())]
    assert not a.equity.loc[t:].equals(b.equity.loc[t:])         # the future did change


def test_deterministic_replay():
    cfg = load_config("B")
    p = build_panel(synth_market(list(cfg.instruments), "2019-01-01", 600, seed=5), "2030-01-01")
    a, b = _synth_run(p, cfg), _synth_run(p, cfg)
    assert a.fills == b.fills and a.skips == b.skips
    pd.testing.assert_series_equal(a.equity, b.equity)
    assert a.ledger.events() == b.ledger.events()
    st = a.ledger.replay()                                           # ledger replay == engine state
    assert st.last_equity == a.equity.iloc[-1]
    assert st.n_fills == len(a.fills)
    eq = st.cash + sum(q * p.close[s].dropna().iloc[-1] for s, q in st.positions.items())
    assert eq == pytest.approx(a.equity.iloc[-1], rel=1e-12)


def test_bad_inputs():
    cfg = cfg_for(["X"])
    p = hand_panel({"X": [10.0] * 3}, {"X": [10.0] * 3})
    with pytest.raises(ValueError):
        run(p, targets_of(p, {}), cfg, cost_mult=0.0)
    with pytest.raises(ValueError):
        engine.run(p, targets_of(p, {}), p.close.index[:0], cfg, start="2030-01-01", end="2030-02-01",
                   min_order={}, lot={})
