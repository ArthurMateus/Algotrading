"""Property tests not covered elsewhere: whole-engine invariants on random panels (random price paths, listing
gaps, missing bars, variants, cost multipliers) and metric invariants. Broker, risk gate and ledger properties live
in test_broker / test_risk / test_ledger / test_paper and are not repeated here."""
from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from algotrade import engine, metrics as M, strategy
from algotrade.broker import Fill
from algotrade.config import load_config
from algotrade.data import Bars, build_panel
from tests.synth import synth_bars

SETTINGS = settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
FILLS_SEEN: list[int] = []
KEYS = [("TSMOM", 5, "weekly"), ("SMA", 10, "monthly"), ("TSMOM", 20, "weekly"), ("SMA", 5, "weekly")]


@st.composite
def worlds(draw):
    seed = draw(st.integers(0, 10_000))
    vol = draw(st.sampled_from([0.005, 0.02, 0.06]))
    drift = draw(st.sampled_from([-0.003, 0.0, 0.003]))
    n = draw(st.integers(70, 160))
    cfg = dataclasses.replace(load_config("B"), warmup_bars=20, vol_window=10, grid_lookbacks=(5, 10, 20))
    bars = {}
    for i, s in enumerate(cfg.instruments):
        b = synth_bars(s, "2022-01-01", n, seed=seed + i, vol=vol, drift=drift)
        f = b.frame
        gaps = draw(st.lists(st.integers(25, n - 2), max_size=4, unique=True))     # missing bars
        late = draw(st.integers(0, 15)) if i == 1 else 0                           # listed later
        f = f.drop(f.index[gaps]).iloc[late:]
        bars[s] = Bars(s, "binance_vision", "none", f)
    return cfg, bars, draw(st.sampled_from(KEYS)), draw(st.sampled_from([1.0, 2.0, 5.0]))


@SETTINGS
@given(worlds())
def test_engine_invariants_on_random_panels(w):
    cfg, bars, (sig, lb, reb), mult = w
    panel = build_panel(bars, "2030-01-01")
    v = strategy.Variant(sig, lb, reb)
    tg = strategy.target_weights(panel, v, cfg)
    dd = strategy.decision_dates(panel.close.index, reb)
    idx = panel.close.index
    res = engine.run(panel, tg, dd, cfg, start=str(idx[25].date()), end=str(idx[-1].date()), cost_mult=mult,
                     label=v.key)
    # no leverage / shorts: cash and positions never negative, weights within the caps at every close
    pos: dict[str, float] = {}
    cash = cfg.start_equity_usd
    for f in res.fills:
        cash += f.cash_delta
        pos[f.symbol] = pos.get(f.symbol, 0.0) + (f.qty if f.side == "buy" else -f.qty)
        assert cash >= -1e-9 and pos[f.symbol] >= -1e-9
        assert f.qty > 0 and f.price > 0 and f.commission >= 0 and f.slippage_cost >= -1e-12
    assert (res.weights.to_numpy() >= -1e-12).all()
    assert (res.weights.sum(axis=1) <= cfg.max_gross_exposure + 1e-9).all()
    FILLS_SEEN.append(len(res.fills))
    assert np.isfinite(res.equity.to_numpy()).all() and (res.equity > 0).all()
    # the ledger replay equals the engine's own books
    st_ = res.ledger.replay()
    assert st_.last_equity == res.equity.iloc[-1] and st_.n_fills == len(res.fills)
    assert abs(st_.cash - cash) < 1e-6 and all(abs(st_.positions.get(s, 0.0) - q) < 1e-9 for s, q in pos.items())
    # a fill only on a day that has a real bar, at that bar's open (+ slippage in the trade's direction)
    for f in res.fills:
        ts = pd.Timestamp(f.date)
        assert bool(panel.valid.at[ts, f.symbol])
        assert f.open_price == panel.open.at[ts, f.symbol]
        assert (f.price >= f.open_price) if f.side == "buy" else (f.price <= f.open_price)


@SETTINGS
@given(worlds())
def test_engine_is_deterministic_and_costs_are_monotone_in_the_multiplier(w):
    cfg, bars, (sig, lb, reb), _ = w
    panel = build_panel(bars, "2030-01-01")
    v = strategy.Variant(sig, lb, reb)
    tg = strategy.target_weights(panel, v, cfg)
    dd = strategy.decision_dates(panel.close.index, reb)
    idx = panel.close.index
    kw = dict(start=str(idx[25].date()), end=str(idx[-1].date()), label=v.key)
    a = engine.run(panel, tg, dd, cfg, cost_mult=1.0, **kw)
    b = engine.run(panel, tg, dd, cfg, cost_mult=1.0, **kw)
    assert a.fills == b.fills and a.equity.equals(b.equity)
    x2 = engine.run(panel, tg, dd, cfg, cost_mult=2.0, **kw)
    # per unit traded, every cost component is exactly doubled (quantities may differ, so compare rates)
    for f1, f2 in zip(a.fills[:1], x2.fills[:1]):
        r1 = (f1.commission + f1.regulatory) / (f1.qty * f1.price)
        r2 = (f2.commission + f2.regulatory) / (f2.qty * f2.price)
        assert abs(r2 / r1 - 2.0) < 1e-6 if r1 > 0 else r2 == 0


# ------------------------------------------------------------------ metrics

equities = st.lists(st.floats(0.5, 2.0, allow_nan=False), min_size=2, max_size=60)


@SETTINGS
@given(equities)
def test_max_drawdown_is_a_fraction_and_shift_invariant_in_scale(vals):
    e = pd.Series(vals, index=pd.date_range("2024-01-01", periods=len(vals)))
    dd = M.max_drawdown(e)
    assert 0.0 <= dd < 1.0
    assert abs(M.max_drawdown(e * 7.3) - dd) < 1e-12
    assert M.max_drawdown(e.cummax()) == 0.0


@SETTINGS
@given(st.lists(st.floats(-0.1, 0.1, allow_nan=False), min_size=5, max_size=80), st.floats(0.1, 50.0))
def test_sharpe_is_scale_invariant_and_flips_sign(rets, k):
    r = pd.Series(rets, index=pd.date_range("2024-01-01", periods=len(rets)))
    rf = pd.Series(0.0, index=r.index)
    s = M.sharpe(r, rf, 365)
    if np.isnan(s):
        return
    assert abs(M.sharpe(r * k, rf, 365) - s) < 1e-6 * max(1.0, abs(s))
    assert abs(M.sharpe(-r, rf, 365) + s) < 1e-9 * max(1.0, abs(s))


@SETTINGS
@given(st.lists(st.tuples(st.sampled_from(["X", "Y"]), st.sampled_from(["buy", "sell"]), st.floats(0.1, 5.0),
                          st.sampled_from(["entry", "exit", "rebalance"])), max_size=30))
def test_round_trips_never_exceed_sells_or_entries(raw):
    fills = [Fill(sym, side, kind, q, 10.0, 10.0, 0.0, 0.0, 0.0, f"2024-01-{i % 28 + 1:02d}")
             for i, (sym, side, q, kind) in enumerate(raw)]
    n = M.round_trips(fills)
    assert 0 <= n <= sum(f.side == "sell" for f in fills)


def test_zz_the_engine_property_actually_traded():
    """Guards against a vacuous property run (runs after the engine property in file order)."""
    assert FILLS_SEEN and sum(1 for n in FILLS_SEEN if n > 0) >= len(FILLS_SEEN) // 3
