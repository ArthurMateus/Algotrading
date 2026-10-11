"""Metrics on tiny hand-computed cases (Sharpe, drawdown, underwater months, round trips, DSR, extras, CDI flag)."""
import math

import numpy as np
import pandas as pd
import pytest

from algotrade import metrics as M
from algotrade.broker import Fill


def S(values, start="2024-01-01", freq="D"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq=freq), dtype="float64")


def SD(pairs):
    return pd.Series([v for _, v in pairs], index=pd.DatetimeIndex([d for d, _ in pairs]), dtype="float64")


def fill(sym, side, kind, qty, price=10.0, com=0.0, reg=0.0, slip=0.0):
    return Fill(sym, side, kind, qty, price, price, com, reg, slip, "2024-01-01")


# ---------------------------------------------------------------- Sharpe

def test_sharpe_hand_case():
    r = S([0.01, 0.02, 0.03])                       # mean 0.02, sd(ddof=1) 0.01 -> 2 per bar
    zero = S([0.0, 0.0, 0.0])
    assert M.per_bar_sharpe(r, zero) == pytest.approx(2.0)
    assert M.sharpe(r, zero, 252) == pytest.approx(2.0 * math.sqrt(252))
    assert M.sharpe(r, zero, 365) == pytest.approx(2.0 * math.sqrt(365))


def test_sharpe_in_excess_of_rf():
    r = S([0.01, 0.02, 0.03])
    rf = S([0.005] * 3)                             # mean excess 0.015, sd 0.01
    assert M.per_bar_sharpe(r, rf) == pytest.approx(1.5)


def test_sharpe_rf_aligned_on_returns_index():
    r = S([0.01, 0.02, 0.03], start="2024-01-02")
    rf = S([0.005] * 10, start="2023-12-30")
    assert M.per_bar_sharpe(r, rf) == pytest.approx(1.5)


def test_sharpe_constant_is_nan():
    assert math.isnan(M.sharpe(S([0.01] * 5), S([0.0] * 5), 252))
    assert math.isnan(M.sharpe(S([0.01]), S([0.0]), 252))


def test_moments_symmetric():
    sk, ku, n = M.moments(S([-1.0, 0.0, 1.0]))
    # population: m2 = 2/3, m3 = 0, m4 = 2/3 -> kurtosis = (2/3) / (4/9) = 1.5
    assert (sk, n) == (0.0, 3) and ku == pytest.approx(1.5)


# ---------------------------------------------------------------- drawdown / underwater

def test_max_drawdown():
    assert M.max_drawdown(S([100, 120, 90, 130, 65])) == pytest.approx(0.5)   # 130 -> 65
    assert M.max_drawdown(S([100, 110, 120])) == 0.0


def test_calendar_months():
    t = pd.Timestamp
    assert M.calendar_months(t("2020-01-15"), t("2021-07-15")) == 18.0
    assert M.calendar_months(t("2020-01-15"), t("2020-01-15")) == 0.0
    # Jan 31 + 1 month = Feb 29 (2020); Mar 15 is 15 of the 31 days to Mar 31 (Jan 31 + 2 months)
    assert M.calendar_months(t("2020-01-31"), t("2020-03-15")) == pytest.approx(1 + 15 / 31)


def test_longest_underwater_recovered():
    eq = SD([("2020-01-01", 90), ("2020-01-31", 100), ("2020-02-10", 95), ("2020-03-15", 100),
             ("2020-03-20", 101), ("2020-03-25", 100.5), ("2020-04-01", 102)])
    peak, end, months, rec = M.longest_underwater(eq)
    assert (peak, end, rec) == ("2020-01-31", "2020-03-15", True)
    assert months == pytest.approx(1 + 15 / 31)


def test_longest_underwater_unrecovered_runs_to_window_end():
    eq = SD([("2020-01-01", 100), ("2020-01-15", 120), ("2020-06-01", 80), ("2021-07-15", 110)])
    assert M.longest_underwater(eq) == ("2020-01-15", "2021-07-15", 18.0, False)   # exactly 18 -> passes <= 18
    eq2 = SD([("2020-01-15", 120), ("2021-07-16", 110)])
    _, _, months, _ = M.longest_underwater(eq2)
    assert months > 18.0


def test_longest_underwater_never_underwater():
    assert M.longest_underwater(S([1, 2, 3])) == ("2024-01-01", "2024-01-01", 0.0, True)


def test_underwater_share_and_median_length():
    eq = S([100, 90, 95, 100, 99, 101, 100, 99, 98, 97])
    # under water on days 2,3,5 and 7..10 -> 7 of 10
    assert M.underwater_share(eq) == pytest.approx(0.7)
    # spells (calendar days peak -> recovery/last): Jan1->Jan4 = 3, Jan4->Jan6 = 2, Jan6->Jan10 = 4 -> median 3
    assert M.median_drawdown_length(eq) == 3.0
    assert M.median_drawdown_length(S([1, 2])) == 0.0


# ---------------------------------------------------------------- round trips

def test_round_trips():
    fills = [
        fill("A", "buy", "entry", 1.0), fill("A", "sell", "rebalance", 0.4),     # trim does not count
        fill("A", "buy", "rebalance", 0.2), fill("A", "sell", "exit", 0.8),      # 1
        fill("B", "buy", "entry", 2.0), fill("B", "sell", "exit", 2.0),          # 2
        fill("A", "buy", "entry", 1.0), fill("A", "sell", "exit", 1.0),          # 3
        fill("B", "buy", "entry", 2.0),                                          # still open: no
    ]
    assert M.round_trips(fills) == 3
    assert M.round_trips([]) == 0


def test_round_trip_by_trims_to_zero():
    fills = [fill("A", "buy", "entry", 0.3), fill("A", "sell", "rebalance", 0.1),
             fill("A", "sell", "rebalance", 0.2)]
    assert M.round_trips(fills) == 1


# ---------------------------------------------------------------- deflated Sharpe

def _trials_with_var(n, var, seed=1):
    x = np.random.default_rng(seed).normal(size=n)
    return list((x - x.mean()) / x.std(ddof=1) * math.sqrt(var))


def test_deflated_sharpe_bailey_lopez_de_prado_example():
    """Bailey & Lopez de Prado (2014), numerical example: annualised SR 2.5 over 5 years of daily data
    (T = 1250, 250 bars/yr), N = 100 trials with annualised variance 0.5, skew -3, kurtosis 10:
    SR0 = 0.1132 per bar and DSR = 0.9004."""
    trials = _trials_with_var(100, 0.5 / 250)
    sr = 2.5 / math.sqrt(250)
    assert M.deflated_sharpe(sr, trials, 1250, -3.0, 10.0) == pytest.approx(0.9004, abs=5e-4)


def test_deflated_sharpe_hand_case_n2():
    # trials [0, 0.1]: sd = 0.0707107; Z(1 - 1/2) = 0; Z(1 - 1/(2e)) = Z(0.8160603) = 0.900476
    # SR0 = 0.0707107 * 0.5772157 * 0.900476 = 0.0367537; normal returns (skew 0, kurt 3), sr_hat 0.1, T = 101
    # z = (0.1 - 0.0367537) * 10 / sqrt(1 + 0.5 * 0.01) = 0.630925; Phi = 0.735955
    assert M.deflated_sharpe(0.1, [0.0, 0.1], 101, 0.0, 3.0) == pytest.approx(0.735955, abs=1e-5)


def test_deflated_sharpe_n_trials_override_and_more_trials_lower_dsr():
    trials = _trials_with_var(12, 0.0004)
    base = M.deflated_sharpe(0.08, trials, 1000, 0.0, 3.0)
    assert M.deflated_sharpe(0.08, trials, 1000, 0.0, 3.0, n_trials=12) == base
    assert M.deflated_sharpe(0.08, trials, 1000, 0.0, 3.0, n_trials=24) < base


def test_deflated_sharpe_degenerate():
    assert math.isnan(M.deflated_sharpe(0.1, [0.1], 100, 0.0, 3.0))
    assert math.isnan(M.deflated_sharpe(0.1, [0.0, 0.1], 1, 0.0, 3.0))


# ---------------------------------------------------------------- extras

def test_cagr():
    eq = SD([("2020-01-01", 100.0), ("2024-01-01", 146.41)])     # 1461 days = 4 * 365.25
    assert M.cagr(eq) == pytest.approx(0.10)


def test_turnover():
    fills = [fill("A", "buy", "entry", 30.0, price=10.0), fill("A", "sell", "exit", 30.0, price=10.0)]
    eq = S([300.0] * 252)
    assert M.turnover(fills, eq, 252) == pytest.approx(2.0)          # 600 / 300 per 1 year
    assert M.turnover(fills, S([300.0] * 126), 252) == pytest.approx(4.0)


def test_exposure():
    w = pd.DataFrame({"a": [0.2, 0.0], "b": [0.3, 0.1]})
    assert M.exposure(w) == pytest.approx(0.3)


def test_cost_breakdown():
    fills = [fill("A", "buy", "entry", 1, com=0.1, reg=0.0, slip=0.05),
             fill("A", "sell", "exit", 1, com=0.2, reg=0.01, slip=0.04)]
    cb = M.cost_breakdown(fills)
    assert cb["commission"] == pytest.approx(0.3)
    assert cb["regulatory"] == pytest.approx(0.01)
    assert cb["slippage"] == pytest.approx(0.09)
    assert cb["total"] == pytest.approx(0.4)


# ---------------------------------------------------------------- BRL / CDI flag

def test_brl_cdi_flag_compounds_only_business_days():
    # one week Mon 2024-01-01 .. Mon 2024-01-08, CDI 0.1%/day forward-filled over weekends
    days = pd.date_range("2024-01-01", "2024-01-08", freq="D")
    cdi = pd.Series(0.001, index=days)
    bday = pd.Series(days.dayofweek < 5, index=days)
    eq = pd.Series(np.linspace(100, 101, len(days)), index=days)
    ptax = pd.Series(5.0, index=days)
    out = M.brl_cdi_flag(eq, ptax, cdi, bday)
    years = 7 / 365.25
    # business days in [Jan 1, Jan 8): Mon..Fri = 5
    assert out["cdi_cagr"] == pytest.approx(1.001 ** (5 / years) - 1)
    assert out["brl_cagr"] == pytest.approx((101 / 100) ** (1 / years) - 1)
    assert out["available"] is True
    assert out["beats_cdi"] == (out["brl_cagr"] > out["cdi_cagr"])
    # without the mask every forward-filled calendar day compounds (7), which overstates CDI
    assert M.brl_cdi_flag(eq, ptax, cdi)["cdi_cagr"] > out["cdi_cagr"]


def test_brl_cdi_flag_ptax_moves_brl_and_cdi_on_own_calendar():
    # equity on a market calendar that skips Wed 2024-01-03 (a US holiday, say); CDI on every day still counts it
    eq = SD([("2024-01-01", 100), ("2024-01-02", 100), ("2024-01-04", 100), ("2024-01-08", 100)])
    days = pd.date_range("2024-01-01", "2024-01-08", freq="D")
    cdi = pd.Series(0.001, index=days)
    bday = pd.Series(days.dayofweek < 5, index=days)
    ptax = SD([("2024-01-01", 5.0), ("2024-01-05", 5.5)])            # forward-filled to Jan 8
    out = M.brl_cdi_flag(eq, ptax, cdi, bday)
    years = 7 / 365.25
    assert out["cdi_cagr"] == pytest.approx(1.001 ** (5 / years) - 1)
    assert out["brl_cagr"] == pytest.approx(1.1 ** (1 / years) - 1)
    assert out["beats_cdi"] is True


def test_brl_cdi_flag_unavailable_without_ptax():
    days = pd.date_range("2024-01-01", periods=5, freq="D")
    out = M.brl_cdi_flag(pd.Series(100.0, index=days), pd.Series(np.nan, index=days),
                         pd.Series(0.001, index=days))
    assert out["available"] is False and out["beats_cdi"] is False and math.isnan(out["brl_cagr"])
