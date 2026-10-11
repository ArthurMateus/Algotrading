import dataclasses

import numpy as np
import pandas as pd
import pytest

from algotrade import data, sources
from algotrade.config import load_config
from algotrade.data import Bars, DataError, check_integrity
from tests.fakes import FakeServer, fixture
from tests.synth import synth_bars, synth_frame, synth_market


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(sources, "POLITE_DELAY", 0.0)
    monkeypatch.setattr(sources, "BACKOFF_BASE", 0.0)


def kinds(issues):
    return sorted({i.kind for i in issues})


# ------------------------------------------------------------------ integrity

def test_clean_synthetic_series_has_no_issues():
    assert check_integrity(synth_bars("X", n=300, vol=0.01), daily_calendar=True) == []
    assert check_integrity(synth_bars("Y", n=300, daily=False, vol=0.01), daily_calendar=False) == []


def test_gap_duplicate_and_order_detected():
    b = synth_bars("X", n=100, vol=0.01)
    f = b.frame.drop(b.frame.index[10:13])                       # 3 missing days
    issues = check_integrity(Bars("X", "binance_vision", "none", f), daily_calendar=True)
    gap = [i for i in issues if i.kind == "gap"]
    assert len(gap) == 1 and "3 missing" in gap[0].detail and gap[0].date == b.frame.index[10].date().isoformat()

    dup = pd.concat([b.frame, b.frame.iloc[[5]]])
    issues = check_integrity(Bars("X", "binance_vision", "none", dup), daily_calendar=True)
    assert {"duplicate", "non_monotonic"} <= set(kinds(issues))


def test_etf_calendar_tolerates_holiday_weekends_but_flags_long_gaps():
    f = synth_frame("2024-01-01", 120, daily=False, vol=0.005)
    ok = check_integrity(Bars("X", "yahoo", "total_return", f.drop(f.index[20])), daily_calendar=False)   # 1 missing weekday
    assert "gap" not in kinds(ok)
    bad = check_integrity(Bars("X", "yahoo", "total_return", f.drop(f.index[20:26])), daily_calendar=False)
    assert "gap" in kinds(bad)


def test_bad_ohlc_nonpositive_outlier_stale_zero_volume():
    f = synth_frame("2024-01-01", 60, vol=0.005)
    f.iloc[5, f.columns.get_loc("high")] = f.iloc[5]["low"] * 0.5      # high < low
    f.iloc[9, f.columns.get_loc("close")] = f.iloc[9]["high"] * 1.1    # close above high
    f.iloc[12, f.columns.get_loc("open")] = -1.0                       # non-positive
    f.iloc[30:36, f.columns.get_loc("close")] = f.iloc[30]["close"]    # stale run
    f.iloc[40:, f.columns.get_loc("close")] *= 3                       # one 3x jump (outlier)
    f.iloc[41, f.columns.get_loc("volume")] = 0.0
    issues = check_integrity(Bars("X", "binance_vision", "none", f), daily_calendar=True)
    k = kinds(issues)
    assert {"bad_ohlc", "outlier", "stale"} <= set(k)
    assert sum(1 for i in issues if i.kind == "bad_ohlc" and i.date == f.index[5].date().isoformat()) == 1
    assert any(i.kind == "bad_ohlc" and "non-positive" in i.detail for i in issues)
    assert any(i.kind == "outlier" and i.date == f.index[40].date().isoformat() for i in issues)
    assert any("zero volume" in i.detail for i in issues)


def test_integrity_reports_but_never_mutates():
    b = synth_bars("X", n=50)
    before = b.frame.copy()
    check_integrity(b, daily_calendar=True)
    pd.testing.assert_frame_equal(b.frame, before)


# ------------------------------------------------------------------ panel

def test_panel_crypto_calendar_and_valid_flags():
    bars = synth_market(["BTCUSDT", "ETHUSDT"], start="2024-01-01", n=60)
    bars["ETHUSDT"] = Bars("ETHUSDT", "binance_vision", "none", bars["ETHUSDT"].frame.iloc[10:])    # lists later
    p = data.build_panel(bars, "2024-02-15")
    assert p.close.index[0] == pd.Timestamp("2024-01-01") and p.close.index[-1] == pd.Timestamp("2024-02-15")
    assert p.close.index.is_unique and (p.close.index.to_series().diff().dropna() == pd.Timedelta(days=1)).all()
    assert not p.valid.loc["2024-01-05", "ETHUSDT"] and np.isnan(p.close.loc["2024-01-05", "ETHUSDT"])
    assert p.valid.loc["2024-01-20", "ETHUSDT"]
    assert p.adjusted == "none"


def test_panel_etf_union_calendar_and_truncation():
    bars = synth_market(["SPY", "GLD"], start="2024-01-01", n=80, daily=False)
    f = bars["GLD"].frame.drop(bars["GLD"].frame.index[7])              # GLD misses one session SPY has
    bars["GLD"] = Bars("GLD", "yahoo", "total_return", f)
    p = data.build_panel(bars, "2024-03-01")
    assert p.close.index.max() <= pd.Timestamp("2024-03-01")
    missing = bars["SPY"].frame.index[7]
    assert not p.valid.loc[missing, "GLD"] and p.valid.loc[missing, "SPY"]
    assert p.adjusted == "total_return"
    bars["GLD"] = Bars("GLD", "stooq", "price_only", f)
    assert data.build_panel(bars, "2024-03-01").adjusted == "price_only"


# ------------------------------------------------------------------ cache round trip, loopback fetch

def _cfg(market, tmp_path, srv, **kw):
    cfg = load_config(market)
    urls = {k: srv.url for k in cfg.urls}
    return dataclasses.replace(cfg, data_dir=tmp_path / "data", urls=urls, **kw)


def test_fetch_binance_from_monthly_zip_then_incremental_then_load_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "BINANCE_FIRST_MONTH", "2024-12")
    zip25 = fixture("binance_BTCUSDT-1d-2025-01.zip")
    routes = {"/data/spot/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-2025-01.zip": (200, zip25)}
    with FakeServer(routes) as srv:
        cfg = _cfg("B", tmp_path, srv, instruments=("BTCUSDT",), end_date="2025-01-31")
        issues = data.fetch_market(cfg)
        assert issues == []                              # Dec 2024 is "before listing" for this fake: no data, no noise
        b = data.load_bars(cfg)["BTCUSDT"]
        assert len(b.frame) == 31 and b.source == "binance_vision" and b.adjusted == "none"
        assert b.frame.index.is_unique and b.frame.index.is_monotonic_increasing
        assert b.frame.loc["2025-01-01", "close"] == 94591.79
        man = (tmp_path / "data" / "bars" / "B" / "manifest.json").read_text()
        assert "sha256" in man and "fetched_at" in man
        # extend the window: February is not served -> existing rows kept, missing files noted, no crash
        cfg2 = dataclasses.replace(cfg, end_date="2025-02-05")
        issues2 = data.fetch_market(cfg2)
        assert len(data.load_bars(cfg2)["BTCUSDT"].frame) == 31
        assert any(i.kind == "source" for i in issues2)
    # network is gone now: load_bars must not need it
    assert len(data.load_bars(cfg)["BTCUSDT"].frame) == 31


def test_fetch_binance_daily_files_when_monthly_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "BINANCE_FIRST_MONTH", "2026-09")
    routes = {"/data/spot/daily/klines/ETHUSDT/1d/ETHUSDT-1d-2026-09-30.zip": (200, fixture("binance_ETHUSDT-1d-2026-09-30.zip"))}
    with FakeServer(routes) as srv:
        cfg = _cfg("B", tmp_path, srv, instruments=("ETHUSDT",))
        issues = data.fetch_market(cfg)
        b = data.load_bars(cfg)["ETHUSDT"]
        assert list(b.frame.index) == [pd.Timestamp("2026-09-30")]
        assert issues == []                      # nothing found before 09-30, so no gap is claimed


def test_fetch_stock_falls_back_from_blocked_stooq_to_yahoo(tmp_path):
    routes = {"/q/d/l/": (200, fixture("stooq_SPY_response.html")),
              "/v8/finance/chart/SPY": (200, fixture("yahoo_SPY_2024-12.json"))}
    with FakeServer(routes) as srv:
        cfg = _cfg("A", tmp_path, srv, instruments=("SPY",), end_date="2025-01-09")
        issues = data.fetch_market(cfg)
        b = data.load_bars(cfg)["SPY"]
        assert b.source == "yahoo" and b.adjusted == "total_return" and len(b.frame) == 20
        assert any(i.kind == "source" and "stooq" in i.detail for i in issues)
        assert sum(1 for h in srv.hits if h.startswith("/q/d/l/")) == 1
        assert not any(h for h in srv.hits if "Authorization" in h)


def test_fetch_stock_truncates_at_end_date(tmp_path):
    with FakeServer({"/v8/finance/chart/SPY": (200, fixture("yahoo_SPY_2024-12.json"))}) as srv:
        cfg = _cfg("A", tmp_path, srv, instruments=("SPY",), sources=("yahoo",), end_date="2024-12-31")
        data.fetch_market(cfg)
        assert data.load_bars(cfg)["SPY"].frame.index[-1] == pd.Timestamp("2024-12-31")


def test_fetch_stock_all_sources_fail(tmp_path):
    with FakeServer({}) as srv:
        cfg = _cfg("A", tmp_path, srv, instruments=("SPY",))
        with pytest.raises(DataError, match="every source failed"):
            data.fetch_market(cfg)


def test_load_bars_without_cache_raises_and_never_fetches(tmp_path):
    with FakeServer({}) as srv:
        cfg = _cfg("A", tmp_path, srv)
        with pytest.raises(DataError, match="no cached bars"):
            data.load_bars(cfg)
        assert srv.hits == []


def test_fetch_aux_load_aux_and_exchange_info(tmp_path):
    routes = {"/graph/fredgraph.csv": (200, fixture("fred_DTB3.csv")),
              "/dados/serie/bcdata.sgs.1/": (200, fixture("sgs_1.json")),
              "/dados/serie/bcdata.sgs.12/": (200, fixture("sgs_12.json")),
              "/api/v3/exchangeInfo": (200, fixture("binance_exchangeInfo.json"))}
    with FakeServer(routes) as srv:
        cfg = _cfg("B", tmp_path, srv, end_date="2026-09-30")
        assert data.fetch_aux(cfg) == []
    assert data.min_order_usd(cfg) == {"BTCUSDT": 5.0, "ETHUSDT": 5.0}
    assert data.lot_step(cfg)["BTCUSDT"] == 0.00001
    idx = pd.date_range("2026-08-29", "2026-09-12", freq="D")
    aux = data.load_aux(cfg, idx)
    assert aux.rf_available
    assert aux.rf_per_bar.loc["2026-08-31"] == pytest.approx(3.78 / 100 / 365)
    assert aux.rf_per_bar.loc["2026-08-30"] == pytest.approx(3.74 / 100 / 365)     # Sunday: forward-filled from Friday
    assert aux.rf_per_bar.loc["2026-08-29"] == pytest.approx(3.74 / 100 / 365)
    assert aux.ptax.loc["2026-09-05"] == aux.ptax.loc["2026-09-04"] == 5.1253      # weekend forward fill
    assert aux.cdi_daily.loc["2026-09-01"] == pytest.approx(0.0005166)
    assert aux.cdi_business_day.loc["2026-09-01"] and not aux.cdi_business_day.loc["2026-09-05"]
    assert np.isnan(aux.ptax.loc["2026-08-29"])                                     # never filled backward


def test_aux_missing_degrades_as_specified(tmp_path):
    with FakeServer({}) as srv:
        cfg = _cfg("A", tmp_path, srv)
        issues = data.fetch_aux(cfg, end_date="2001-01-31")
        assert {i.symbol for i in issues} >= {"DTB3", "SGS1", "SGS12"}
        aux = data.load_aux(cfg, pd.date_range("2020-01-01", periods=5))
        assert not aux.rf_available and (aux.rf_per_bar == 0).all()


def test_min_order_fallback_when_no_exchange_info(tmp_path):
    with FakeServer({}) as srv:
        a, b = _cfg("A", tmp_path, srv), _cfg("B", tmp_path, srv)
        assert data.min_order_usd(b) == {"BTCUSDT": 10.0, "ETHUSDT": 10.0}
        assert data.lot_step(b) == {"BTCUSDT": 0.0, "ETHUSDT": 0.0}
        assert data.min_order_usd(a)["SPY"] == 1.0 and set(data.lot_step(a).values()) == {0.0}
