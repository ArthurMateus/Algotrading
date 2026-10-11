"""Metrics for every pass/fail criterion and the reported extras. Pure functions on pandas Series.

Owner: backtest-engineer. Annualisation: periods_per_year = 252 (A) or 365 (B). Sharpe uses daily simple returns in
excess of `rf_per_bar`, mean / stdev(ddof=1) * sqrt(periods_per_year). Normal CDF and inverse come from
statistics.NormalDist (no scipy). pandas is imported lazily (inside functions) on purpose.
"""
from __future__ import annotations

import math
from statistics import NormalDist
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

    from algotrade.broker import Fill

EULER_GAMMA = 0.5772156649015329
DAYS_PER_YEAR = 365.25


def _excess(returns: "pd.Series", rf_per_bar: "pd.Series | None") -> np.ndarray:
    r = returns.astype("float64")
    if rf_per_bar is not None:
        rf = rf_per_bar.reindex(r.index).astype("float64").fillna(0.0)
        r = r - rf
    x = r.to_numpy()
    return x[np.isfinite(x)]


def per_bar_sharpe(returns: "pd.Series", rf_per_bar: "pd.Series") -> float:
    """Non-annualised Sharpe (used by the deflated Sharpe ratio). NaN if fewer than 2 bars or stdev is 0."""
    x = _excess(returns, rf_per_bar)
    if len(x) < 2:
        return float("nan")
    sd = float(np.std(x, ddof=1))
    if not math.isfinite(sd) or sd <= 1e-15:
        return float("nan")
    return float(np.mean(x)) / sd


def sharpe(returns: "pd.Series", rf_per_bar: "pd.Series", periods_per_year: int) -> float:
    """Annualised Sharpe of returns - rf (rf aligned on the same index). NaN if stdev is 0."""
    return per_bar_sharpe(returns, rf_per_bar) * math.sqrt(periods_per_year)


def moments(returns: "pd.Series", rf_per_bar: "pd.Series | None" = None) -> tuple[float, float, int]:
    """(skew, non-excess kurtosis, n) of the (excess) per-bar returns, population moments, for the DSR."""
    x = _excess(returns, rf_per_bar)
    n = len(x)
    if n < 2:
        return float("nan"), float("nan"), n
    d = x - x.mean()
    m2 = float(np.mean(d ** 2))
    if m2 <= 0:
        return float("nan"), float("nan"), n
    return float(np.mean(d ** 3)) / m2 ** 1.5, float(np.mean(d ** 4)) / m2 ** 2, n


def max_drawdown(equity: "pd.Series") -> float:
    """Largest peak-to-trough fall of daily close equity, as a positive fraction."""
    e = equity.astype("float64").to_numpy()
    if len(e) == 0:
        return 0.0
    peak = np.maximum.accumulate(e)
    return float(np.max(1.0 - e / peak))


def _spells(equity: "pd.Series") -> list[tuple["pd.Timestamp", "pd.Timestamp", bool]]:
    """Underwater spells: (peak date, recovery date or last date, recovered?). Underwater = equity < running
    peak; the spell ends on the first date equity is back at or above that peak."""
    e = equity.astype("float64")
    idx = e.index
    vals = e.to_numpy()
    out = []
    peak_val, peak_i, in_spell = -math.inf, 0, False
    for i, v in enumerate(vals):
        if v >= peak_val:
            if in_spell:
                out.append((idx[peak_i], idx[i], True))
                in_spell = False
            peak_val, peak_i = v, i
        else:
            in_spell = True
    if in_spell:
        out.append((idx[peak_i], idx[-1], False))
    return out


def calendar_months(start: "pd.Timestamp", end: "pd.Timestamp") -> float:
    """Calendar months from start to end: whole months via pandas DateOffset plus the fraction of the next month.
    calendar_months(s, e) <= k exactly when e <= s + DateOffset(months=k)."""
    import pandas as pd
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if end <= start:
        return 0.0
    m = (end.year - start.year) * 12 + (end.month - start.month)
    while start + pd.DateOffset(months=m) > end:
        m -= 1
    while start + pd.DateOffset(months=m + 1) <= end:
        m += 1
    a, b = start + pd.DateOffset(months=m), start + pd.DateOffset(months=m + 1)
    return m + (end - a) / (b - a)


def longest_underwater(equity: "pd.Series") -> tuple[str, str, float, bool]:
    """(peak date, recovery date or last date, length in calendar months, recovered?). An unrecovered spell runs
    to the end of the window. Months = calendar months via pandas DateOffset; criterion 3 passes if the recovery
    (or last) date <= peak date + 18 months. No underwater spell: (first, first, 0.0, True)."""
    if len(equity) == 0:
        raise ValueError("empty equity series")
    best = None
    for peak, end, rec in _spells(equity):
        months = calendar_months(peak, end)
        if best is None or months > best[2]:
            best = (peak, end, months, rec)
    if best is None:
        d = equity.index[0]
        return d.date().isoformat(), d.date().isoformat(), 0.0, True
    return best[0].date().isoformat(), best[1].date().isoformat(), float(best[2]), bool(best[3])


def round_trips(fills: list["Fill"]) -> int:
    """Completed flat -> long -> flat cycles, summed over symbols. Trims do not count; a position still open at
    the end of the window does not count. Fills must be in chronological order."""
    pos: dict[str, float] = {}
    n = 0
    for f in fills:
        q0 = pos.get(f.symbol, 0.0)
        if f.side == "buy":
            pos[f.symbol] = q0 + f.qty
            continue
        q1 = q0 - f.qty
        if q0 > 0 and (f.kind == "exit" or q1 <= 1e-9 * q0):
            n += 1
            pos[f.symbol] = 0.0
        else:
            pos[f.symbol] = max(q1, 0.0)
    return n


def deflated_sharpe(sr_hat: float, sr_trials: list[float], n_obs: int, skew: float, kurtosis: float,
                    n_trials: int | None = None) -> float:
    """Bailey & Lopez de Prado (2014). All Sharpe values per bar (not annualised); kurtosis is non-excess.
    SR0 = sqrt(var(sr_trials)) * ((1-g) * Z(1 - 1/N) + g * Z(1 - 1/(N e))), g = Euler-Mascheroni, N = len(sr_trials);
    DSR = Phi((sr_hat - SR0) * sqrt(n_obs - 1) / sqrt(1 - skew*sr_hat + (kurtosis - 1)/4 * sr_hat**2)).

    var() is the sample variance (ddof=1) of the finite trial Sharpes. `n_trials` (optional, additive) overrides
    N when more variants were logged than Sharpes are passed (N = distinct variants logged, SPEC 11.9).
    NaN if N < 2, n_obs < 2 or the denominator is not positive."""
    trials = np.asarray([s for s in sr_trials if s is not None and math.isfinite(s)], dtype="float64")
    n = int(n_trials) if n_trials is not None else len(trials)
    if n < 2 or len(trials) < 2 or n_obs < 2 or not math.isfinite(sr_hat):
        return float("nan")
    z = NormalDist().inv_cdf
    sd = float(np.std(trials, ddof=1))
    sr0 = sd * ((1.0 - EULER_GAMMA) * z(1.0 - 1.0 / n) + EULER_GAMMA * z(1.0 - 1.0 / (n * math.e)))
    den = 1.0 - skew * sr_hat + (kurtosis - 1.0) / 4.0 * sr_hat ** 2
    if not math.isfinite(den) or den <= 0:
        return float("nan")
    return NormalDist().cdf((sr_hat - sr0) * math.sqrt(n_obs - 1) / math.sqrt(den))


def _years(equity: "pd.Series") -> float:
    return (equity.index[-1] - equity.index[0]).days / DAYS_PER_YEAR


def cagr(equity: "pd.Series") -> float:
    """Compound annual growth over calendar time (365.25-day years). NaN if under one day or non-positive."""
    if len(equity) < 2:
        return float("nan")
    y = _years(equity)
    a, b = float(equity.iloc[0]), float(equity.iloc[-1])
    if y <= 0 or a <= 0 or b <= 0 or not (math.isfinite(a) and math.isfinite(b)):
        return float("nan")
    return (b / a) ** (1.0 / y) - 1.0


def turnover(fills: list["Fill"], equity: "pd.Series", periods_per_year: int) -> float:
    """Annualised traded notional / mean equity: sum(qty * fill price) / mean(equity) / (len(equity) / P)."""
    if len(equity) == 0:
        return float("nan")
    traded = sum(f.qty * f.price for f in fills)
    mean_eq = float(equity.mean())
    if mean_eq <= 0:
        return float("nan")
    return traded / mean_eq / (len(equity) / periods_per_year)


def exposure(weights: "pd.DataFrame") -> float:
    """Mean gross weight held at close."""
    if len(weights) == 0:
        return 0.0
    return float(weights.abs().fillna(0.0).sum(axis=1).mean())


def underwater_share(equity: "pd.Series") -> float:
    """Share of days with equity below its running peak."""
    if len(equity) == 0:
        return 0.0
    e = equity.astype("float64")
    return float((e < e.cummax()).mean())


def median_drawdown_length(equity: "pd.Series") -> float:
    """Median length (calendar days) of underwater spells (peak date to recovery, or to the last date if
    unrecovered). 0.0 if there is none."""
    sp = _spells(equity)
    if not sp:
        return 0.0
    return float(np.median([(end - peak).days for peak, end, _ in sp]))


def cost_breakdown(fills: list["Fill"]) -> dict[str, float]:
    """{"commission": .., "regulatory": .., "slippage": .., "total": ..} in USD (spot only: no funding)."""
    com = float(sum(f.commission for f in fills))
    reg = float(sum(f.regulatory for f in fills))
    slip = float(sum(f.slippage_cost for f in fills))
    return {"commission": com, "regulatory": reg, "slippage": slip, "total": com + reg + slip}


def brl_cdi_flag(equity_usd: "pd.Series", ptax: "pd.Series", cdi_daily: "pd.Series",
                 cdi_business_day: "pd.Series | None" = None) -> dict[str, float | bool]:
    """Convert equity to BRL with PTAX, compare its CAGR with compounded CDI over the same dates.
    Returns {"brl_cagr", "cdi_cagr", "beats_cdi", "available"}. Before tax on both sides. A flag, not pass/fail.

    CDI compounds once per real SGS 12 observation (Brazilian business day) d with first <= d < last, where
    first/last are the equity window ends: `cdi_business_day` (Aux.cdi_business_day) marks those dates in the
    forward-filled `cdi_daily`. Without a mask, every non-NaN date of `cdi_daily` is treated as an observation,
    which is only correct for the raw (not forward-filled) series. `cdi_daily` may be on its own (e.g. daily)
    index; it is sliced by date, not reindexed to the equity calendar, so business days that are not market
    days (US holidays for A) still compound. PTAX is forward-filled onto the equity dates (never backward)."""
    import pandas as pd
    nan = float("nan")
    out: dict[str, float | bool] = {"brl_cagr": nan, "cdi_cagr": nan, "beats_cdi": False, "available": False}
    if len(equity_usd) < 2:
        return out
    eq = equity_usd.astype("float64")
    first, last = eq.index[0], eq.index[-1]
    px = ptax.astype("float64").dropna()
    px = px.reindex(px.index.union(eq.index)).ffill().reindex(eq.index)
    brl = eq * px
    cdi = cdi_daily.astype("float64")
    mask = cdi.notna()
    if cdi_business_day is not None:
        mask &= cdi_business_day.reindex(cdi.index).fillna(False).astype(bool)
    window = cdi[mask & (cdi.index >= first) & (cdi.index < last)]
    if pd.isna(brl.iloc[0]) or pd.isna(brl.iloc[-1]) or window.empty:
        return out
    years = (last - first).days / DAYS_PER_YEAR
    growth = float(np.prod(1.0 + window.to_numpy()))
    out["brl_cagr"] = cagr(brl)
    out["cdi_cagr"] = growth ** (1.0 / years) - 1.0
    out["beats_cdi"] = bool(out["brl_cagr"] > out["cdi_cagr"])
    out["available"] = True
    return out
