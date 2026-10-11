"""Metrics for every pass/fail criterion and the reported extras. Pure functions on pandas Series.

Owner: backtest-engineer. Annualisation: periods_per_year = 252 (A) or 365 (B). Sharpe uses daily simple returns in
excess of `rf_per_bar`, mean / stdev(ddof=1) * sqrt(periods_per_year). Normal CDF and inverse come from
statistics.NormalDist (no scipy).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

    from algotrade.broker import Fill


def sharpe(returns: "pd.Series", rf_per_bar: "pd.Series", periods_per_year: int) -> float:
    """Annualised Sharpe of returns - rf (rf aligned on the same index). NaN if stdev is 0."""
    raise NotImplementedError


def per_bar_sharpe(returns: "pd.Series", rf_per_bar: "pd.Series") -> float:
    """Non-annualised Sharpe (used by the deflated Sharpe ratio)."""
    raise NotImplementedError


def max_drawdown(equity: "pd.Series") -> float:
    """Largest peak-to-trough fall of daily close equity, as a positive fraction."""
    raise NotImplementedError


def longest_underwater(equity: "pd.Series") -> tuple[str, str, float, bool]:
    """(peak date, recovery date or last date, length in calendar months, recovered?). An unrecovered spell runs
    to the end of the window. Months = calendar months via pandas DateOffset; criterion 3 passes if the recovery
    (or last) date <= peak date + 18 months."""
    raise NotImplementedError


def round_trips(fills: list["Fill"]) -> int:
    """Completed flat -> long -> flat cycles, summed over symbols. Trims do not count; a position still open at
    the end of the window does not count."""
    raise NotImplementedError


def deflated_sharpe(sr_hat: float, sr_trials: list[float], n_obs: int, skew: float, kurtosis: float) -> float:
    """Bailey & Lopez de Prado (2014). All Sharpe values per bar (not annualised); kurtosis is non-excess.
    SR0 = sqrt(var(sr_trials)) * ((1-g) * Z(1 - 1/N) + g * Z(1 - 1/(N e))), g = Euler-Mascheroni, N = len(sr_trials);
    DSR = Phi((sr_hat - SR0) * sqrt(n_obs - 1) / sqrt(1 - skew*sr_hat + (kurtosis - 1)/4 * sr_hat**2))."""
    raise NotImplementedError


def cagr(equity: "pd.Series") -> float:
    """Compound annual growth over calendar time (365.25-day years)."""
    raise NotImplementedError


def turnover(fills: list["Fill"], equity: "pd.Series", periods_per_year: int) -> float:
    """Annualised traded notional / mean equity."""
    raise NotImplementedError


def exposure(weights: "pd.DataFrame") -> float:
    """Mean gross weight held at close."""
    raise NotImplementedError


def underwater_share(equity: "pd.Series") -> float:
    """Share of days with equity below its running peak."""
    raise NotImplementedError


def median_drawdown_length(equity: "pd.Series") -> float:
    """Median length (calendar days) of underwater spells."""
    raise NotImplementedError


def cost_breakdown(fills: list["Fill"]) -> dict[str, float]:
    """{"commission": .., "regulatory": .., "slippage": ..} in USD."""
    raise NotImplementedError


def brl_cdi_flag(equity_usd: "pd.Series", ptax: "pd.Series", cdi_daily: "pd.Series") -> dict[str, float | bool]:
    """Convert equity to BRL with PTAX, compare its CAGR with compounded CDI over the same dates.
    Returns {"brl_cagr", "cdi_cagr", "beats_cdi"}. Before tax on both sides. A flag, not pass/fail."""
    raise NotImplementedError
