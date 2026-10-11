"""strategy.py: hand-computed signals/vol/weights, the pre-registered grid, decision dates, look-ahead, determinism.

Tests use real config files and synthetic bars (tests/synth.py); nothing of ours is mocked.
"""
from __future__ import annotations

import dataclasses
import math
import statistics

import numpy as np
import pandas as pd
import pytest

from algotrade import strategy as st
from algotrade.config import load_config
from algotrade.data import Panel, build_panel
from synth import synth_market

CFG = {m: load_config(m) for m in ("A", "B")}

PRE_REGISTERED_KEYS = [  # docs/success-criteria.md §3: {TSMOM, SMA} x {63, 126, 252} x {weekly, monthly}
    "TSMOM-63-weekly", "TSMOM-63-monthly", "TSMOM-126-weekly", "TSMOM-126-monthly",
    "TSMOM-252-weekly", "TSMOM-252-monthly",
    "SMA-63-weekly", "SMA-63-monthly", "SMA-126-weekly", "SMA-126-monthly",
    "SMA-252-weekly", "SMA-252-monthly",
]


def s(values, start="2024-01-01"):
    return pd.Series([float(x) for x in values], index=pd.date_range(start, periods=len(values), freq="D",
                                                                       name="date"))


def assert_same(a: pd.Series | pd.DataFrame, b: pd.Series | pd.DataFrame):
    """Bit-identical, NaN == NaN."""
    if isinstance(a, pd.Series):
        pd.testing.assert_series_equal(a, b, check_exact=True)
    else:
        pd.testing.assert_frame_equal(a, b, check_exact=True)


# ---------------------------------------------------------------- panels

def panel_B(n=420, seed=0) -> Panel:
    return build_panel(synth_market(list(CFG["B"].instruments), "2020-01-01", n, seed=seed, daily=True),
                       "2030-01-01")


def panel_A(n=420, seed=10) -> Panel:
    bars = synth_market(list(CFG["A"].instruments), "2020-01-01", n, seed=seed, daily=False)
    # GLD misses three bars, so the union calendar has rows where it is invalid (NaN prices).
    g = bars["GLD"]
    frame = g.frame.drop(g.frame.index[[100, 101, 300]])
    bars["GLD"] = dataclasses.replace(g, frame=frame)
    return build_panel(bars, "2030-01-01")


def truncate(p: Panel, t) -> Panel:
    return Panel(open=p.open.loc[:t], close=p.close.loc[:t], valid=p.valid.loc[:t], adjusted=p.adjusted)


def perturb_after(p: Panel, t, seed=99) -> Panel:
    """Change every close after t (and blank a few bars), leaving rows <= t untouched."""
    rng = np.random.default_rng(seed)
    close, valid = p.close.copy(), p.valid.copy()
    after = close.index > t
    close.loc[after] = close.loc[after] * np.exp(rng.normal(0, 0.3, size=close.loc[after].shape))
    later = close.index[after]
    if len(later) > 5:
        valid.loc[later[[1, 4]], close.columns[0]] = False
    close = close.where(valid)
    return Panel(open=p.open.where(valid), close=close, valid=valid, adjusted=p.adjusted)


# ---------------------------------------------------------------- Variant and grid

def test_variant_key_and_validation():
    assert st.Variant("TSMOM", 252, "monthly").key == "TSMOM-252-monthly"
    assert st.Variant("SMA", 63, "weekly").key == "SMA-63-weekly"
    with pytest.raises(dataclasses.FrozenInstanceError):
        st.Variant("SMA", 63, "weekly").lookback = 5  # type: ignore[misc]
    for bad in [("MACD", 63, "weekly"), ("SMA", 63, "daily"), ("SMA", 0, "weekly"), ("SMA", 6.3, "weekly")]:
        with pytest.raises(ValueError):
            st.Variant(*bad)


@pytest.mark.parametrize("market", ["A", "B"])
def test_grid_is_the_pre_registered_grid(market):
    g = st.grid(CFG[market])
    assert [v.key for v in g] == PRE_REGISTERED_KEYS
    assert len(g) == 12 == CFG[market].variant_cap
    assert st.grid(CFG[market]) == g                     # fixed order, deterministic


def test_grid_refuses_more_than_cap_or_duplicates():
    cfg = CFG["A"]
    with pytest.raises(ValueError):
        st.grid(dataclasses.replace(cfg, grid_lookbacks=(63, 126, 252, 20)))
    with pytest.raises(ValueError):
        st.grid(dataclasses.replace(cfg, grid_lookbacks=(63, 63)))
    with pytest.raises(ValueError):
        st.grid(dataclasses.replace(cfg, grid_signals=("TSMOM", "BREAKOUT")))


# ---------------------------------------------------------------- signals, hand-computed

def test_tsmom_hand_computed():
    out = st.tsmom_signal(s([1, 2, 3, 2, 1, 1.5]), 2)
    # t2: 3/1-1 = 2 > 0; t3: 2/2-1 = 0 (not > 0); t4: 1/3-1 < 0; t5: 1.5/2-1 < 0
    np.testing.assert_array_equal(out.to_numpy(), [np.nan, np.nan, 1.0, 0.0, 0.0, 0.0])
    assert out.dtype == np.float64


def test_sma_hand_computed():
    out = st.sma_signal(s([1, 2, 3, 2, 1, 1.5]), 3)
    # t2: 3 > 2; t3: 2 < 7/3; t4: 1 < 2; t5: 1.5 > 4.5/3 = 1.5? no (tie is flat)
    np.testing.assert_array_equal(out.to_numpy(), [np.nan, np.nan, 1.0, 0.0, 0.0, 0.0])
    out2 = st.sma_signal(s([1, 2, 3, 2, 1, 1.6]), 3)
    assert out2.iloc[-1] == 1.0                            # 1.6 > 4.6/3


def test_sma_constant_series_is_flat_not_rounding_noise():
    out = st.sma_signal(s([0.1] * 300), 252)
    assert out.iloc[251:].eq(0.0).all() and out.iloc[:251].isna().all()


def test_signals_skip_missing_rows_and_count_real_bars():
    x = s([1, 2, np.nan, 3, 2, np.nan, 1])
    t = st.tsmom_signal(x, 2)
    # real bars: 1, 2, 3, 2, 1 -> TSMOM-2 on real bars: nan, nan, 1(3/1), 0(2/2), 0(1/3)
    np.testing.assert_array_equal(t.to_numpy(), [np.nan, np.nan, np.nan, 1.0, 0.0, np.nan, 0.0])
    m = st.sma_signal(x, 2)
    # SMA-2 on real bars: nan, 1(2>1.5), 1(3>2.5), 0(2<2.5), 0(1<1.5)
    np.testing.assert_array_equal(m.to_numpy(), [np.nan, 1.0, np.nan, 1.0, 0.0, np.nan, 0.0])
    assert t.index.equals(x.index) and m.index.equals(x.index)


def test_signals_short_series_all_nan():
    assert st.tsmom_signal(s([1, 2, 3]), 3).isna().all()
    assert st.sma_signal(s([1, 2]), 3).isna().all()
    assert st.tsmom_signal(s([]), 3).empty


# ---------------------------------------------------------------- vol and sleeve weight

def test_realised_vol_hand_computed():
    closes = [100, 110, 99, 108.9, 108.9, 120]
    out = st.realised_vol(s(closes), 3, 252)
    r = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    assert out.iloc[:3].isna().all()                     # needs window + 1 = 4 bars
    for t in range(3, len(closes)):
        expect = statistics.stdev(r[t - 3:t]) * math.sqrt(252)
        assert out.iloc[t] == pytest.approx(expect, rel=1e-12)


def test_realised_vol_known_value():
    # alternating +-a log returns: stdev(ddof=1) of 60 values is a*sqrt(60/59)
    a = 0.01
    closes = np.exp(np.cumsum([0.0] + [a if i % 2 == 0 else -a for i in range(60)])) * 50
    v = st.realised_vol(s(closes), 60, 365)
    assert v.iloc[:60].isna().all()
    assert v.iloc[60] == pytest.approx(a * math.sqrt(60 / 59) * math.sqrt(365), rel=1e-12)


def test_realised_vol_constant_price_is_zero():
    v = st.realised_vol(s([7.0] * 70), 60, 252)
    assert v.iloc[60:].eq(0.0).all()


def test_sleeve_weight_hand_computed():
    w = st.sleeve_weight(s([0.24, 0.06, 0.12, np.nan, 0.0]), 0.12, 5)
    np.testing.assert_allclose(w.to_numpy(), [0.1, 0.2, 0.2, np.nan, 0.2], rtol=0, atol=1e-15)
    w2 = st.sleeve_weight(s([0.80, 0.40, 0.20]), 0.40, 2)   # B: sigma* = 40%, N = 2
    np.testing.assert_allclose(w2.to_numpy(), [0.25, 0.5, 0.5], rtol=0, atol=1e-15)
    assert (w.dropna() <= 1 / 5).all()


# ---------------------------------------------------------------- decision dates

def test_decision_dates_weekly_business_days():
    idx = pd.bdate_range("2024-01-01", "2024-01-31", name="date")      # Mon 1 Jan .. Wed 31 Jan
    d = st.decision_dates(idx, "weekly")
    assert list(d) == [pd.Timestamp(x) for x in ("2024-01-05", "2024-01-12", "2024-01-19", "2024-01-26")]


def test_decision_dates_weekly_with_holiday_friday():
    idx = pd.bdate_range("2024-03-25", "2024-04-12", name="date").drop(pd.Timestamp("2024-03-29"))  # Good Friday
    d = st.decision_dates(idx, "weekly")
    assert list(d) == [pd.Timestamp("2024-03-28"), pd.Timestamp("2024-04-05")]


def test_decision_dates_weekly_daily_calendar_iso_year_boundary():
    idx = pd.date_range("2020-12-25", "2021-01-12", freq="D", name="date")
    d = st.decision_dates(idx, "weekly")
    # ISO weeks start on Monday: 2020-12-28 (W53), 2021-01-04 (W1), 2021-01-11 (W2)
    assert list(d) == [pd.Timestamp(x) for x in ("2020-12-27", "2021-01-03", "2021-01-10")]
    assert all(x.dayofweek == 6 for x in d)


def test_decision_dates_monthly():
    idx = pd.bdate_range("2024-01-15", "2024-04-10", name="date")
    d = st.decision_dates(idx, "monthly")
    # last bars of Jan, Feb, Mar 2024: Wed 31 Jan, Thu 29 Feb, Fri 29 Mar
    assert list(d) == [pd.Timestamp(x) for x in ("2024-01-31", "2024-02-29", "2024-03-29")]
    b = st.decision_dates(pd.date_range("2024-01-01", "2024-03-31", freq="D"), "monthly")
    assert list(b) == [pd.Timestamp("2024-01-31"), pd.Timestamp("2024-02-29")]   # 31 Mar needs the next bar


def test_decision_dates_edges_and_next_bar():
    idx = pd.date_range("2024-01-29", "2024-01-31", freq="D")
    assert len(st.decision_dates(idx, "monthly")) == 0
    d = st.decision_dates(idx, "monthly", next_bar=pd.Timestamp("2024-02-01"))
    assert list(d) == [pd.Timestamp("2024-01-31")]
    assert len(st.decision_dates(idx[:1], "weekly")) == 0
    assert len(st.decision_dates(idx[:0], "weekly")) == 0
    with pytest.raises(ValueError):
        st.decision_dates(idx, "daily")
    with pytest.raises(ValueError):
        st.decision_dates(idx[::-1], "weekly")
    with pytest.raises(ValueError):
        st.decision_dates(idx, "weekly", next_bar=idx[-1])


@pytest.mark.parametrize("rebalance", ["weekly", "monthly"])
def test_decision_dates_truncation_never_changes_past(rebalance):
    idx = panel_A().close.index
    full = st.decision_dates(idx, rebalance)
    for cut in (50, 137, 260, len(idx) - 2):
        part = st.decision_dates(idx[:cut], rebalance)
        assert part.equals(full[full < idx[cut - 1]])
        # with the next bar's date known (paper trading), the truncated answer equals the full one up to idx[cut-1]
        part_nb = st.decision_dates(idx[:cut], rebalance, next_bar=idx[cut])
        assert part_nb.equals(full[full <= idx[cut - 1]])


def test_every_fill_bar_starts_a_new_period():
    idx = panel_B().close.index
    for rb, key in (("weekly", lambda t: tuple(t.isocalendar())[:2]), ("monthly", lambda t: (t.year, t.month))):
        for d in st.decision_dates(idx, rb):
            nxt = idx[idx.get_loc(d) + 1]
            assert key(nxt) != key(d)


# ---------------------------------------------------------------- target and benchmark weights

@pytest.mark.parametrize("market", ["A", "B"])
def test_target_weights_shape_bounds_and_hand_check(market):
    cfg = CFG[market]
    p = panel_A() if market == "A" else panel_B()
    n = len(cfg.instruments)
    for v in st.grid(cfg):
        w = st.target_weights(p, v, cfg)
        assert list(w.columns) == list(cfg.instruments) and w.index.equals(p.close.index)
        vals = w.to_numpy()
        ok = vals[~np.isnan(vals)]
        assert ((ok == 0.0) | ((ok > 0) & (ok <= 1 / n + 1e-15))).all()
        assert w.where(~p.valid[list(cfg.instruments)]).isna().all().all()     # invalid rows -> NaN
    # hand check one cell against the formula on the real bars
    v = st.Variant("TSMOM", 63, "monthly")
    w = st.target_weights(p, v, cfg)
    sym = cfg.instruments[-1]
    c = p.close[sym].dropna()
    t = c.index[300]
    vol = statistics.stdev(np.diff(np.log(c.iloc[240:301].to_numpy()))) * math.sqrt(cfg.periods_per_year)
    long_ = c.iloc[300] / c.iloc[300 - 63] - 1 > 0
    expect = (1 / n) * min(1.0, cfg.sigma_target / vol) if long_ else 0.0
    assert w.loc[t, sym] == pytest.approx(expect, rel=1e-12)


def test_target_weights_warm_up_and_defined_from_bar_252():
    cfg = CFG["B"]
    p = panel_B()
    for v in [*st.grid(cfg), st.Variant("SMA", 20, "weekly")]:   # the off-grid L=20 exercises vol warm-up
        w = st.target_weights(p, v, cfg)
        first_defined = v.lookback if v.signal == "TSMOM" else v.lookback - 1
        sig = (st.tsmom_signal if v.signal == "TSMOM" else st.sma_signal)(p.close["BTCUSDT"], v.lookback)
        col = w["BTCUSDT"]
        assert col.iloc[:min(first_defined, 60)].isna().all()
        assert col.iloc[max(first_defined, 60):].notna().all()
        # flat before the vol is defined is still 0 (definite), long before it would be NaN
        early, early_sig = col.iloc[first_defined:60], sig.iloc[first_defined:60]
        assert (early[early_sig == 0] == 0).all() and early[early_sig == 1].isna().all()
        # SPEC §11.1: E starts at the first bar with >= 252 bars before it (index 252): everything is defined
        assert w.iloc[252:].notna().all().all()


def test_target_weights_gld_gap_counts_real_bars():
    cfg = CFG["A"]
    p = panel_A()
    w = st.target_weights(p, st.Variant("SMA", 63, "weekly"), cfg)
    gld = p.close["GLD"]
    assert w["GLD"][gld.isna()].isna().all()
    expect = st.sma_signal(gld.dropna(), 63)
    got = w["GLD"].dropna()
    assert ((got > 0) == (expect.loc[got.index] == 1.0)).all()


def test_benchmark_weights():
    for p, n in ((panel_A(), 5), (panel_B(), 2)):
        b = st.benchmark_weights(p)
        assert b.index.equals(p.close.index) and list(b.columns) == list(p.close.columns)
        assert (b.to_numpy() == 1.0 / n).all()


# ---------------------------------------------------------------- look-ahead and determinism

@pytest.mark.parametrize("market", ["A", "B"])
def test_no_look_ahead_truncate_or_change_the_future(market):
    cfg = CFG[market]
    p = panel_A() if market == "A" else panel_B()
    idx = p.close.index
    for v in st.grid(cfg):
        full = st.target_weights(p, v, cfg)
        for cut in (70, 200, 330):
            t = idx[cut]
            assert_same(st.target_weights(truncate(p, t), v, cfg), full.loc[:t])
            assert_same(st.target_weights(perturb_after(p, t), v, cfg).loc[:t], full.loc[:t])


def test_no_look_ahead_primitives_appending_bars():
    rng = np.random.default_rng(3)
    base = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, 400)))
    x = s(base)
    longer = s(np.concatenate([base, 100 * np.exp(rng.normal(0, 0.5, 50))]))
    for f in (lambda c: st.tsmom_signal(c, 63), lambda c: st.sma_signal(c, 126),
              lambda c: st.realised_vol(c, 60, 252)):
        assert_same(f(longer).iloc[:400], f(x))


@pytest.mark.parametrize("market", ["A", "B"])
def test_deterministic(market):
    cfg = CFG[market]
    for v in st.grid(cfg):
        a = st.target_weights(panel_A() if market == "A" else panel_B(), v, cfg)
        b = st.target_weights(panel_A() if market == "A" else panel_B(), v, cfg)
        assert_same(a, b)
