"""Signals, volatility-target sizing and the rebalance schedule. Pure, deterministic, look-ahead free.

Owner: strategy-developer. Every value indexed at date t uses only closes up to and including t. The engine fills
decisions at the OPEN of the next bar (t+1). Parameters come only from config (= docs/success-criteria.md §3).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import pandas as pd

    from algotrade.config import MarketConfig
    from algotrade.data import Panel


@dataclass(frozen=True, order=True)
class Variant:
    signal: Literal["TSMOM", "SMA"]
    lookback: int                                  # 63 | 126 | 252
    rebalance: Literal["weekly", "monthly"]

    @property
    def key(self) -> str:
        """Stable id, e.g. 'TSMOM-252-monthly'. Used by the variant log and the cap."""
        raise NotImplementedError


def grid(cfg: "MarketConfig") -> list[Variant]:
    """The 12 pre-registered variants (2 signals x 3 lookbacks x 2 rebalance), in a fixed order."""
    raise NotImplementedError


def tsmom_signal(close: "pd.Series", lookback: int) -> "pd.Series":
    """True at t if close[t] / close[t - lookback] - 1 > 0. NaN (treated as flat) until defined."""
    raise NotImplementedError


def sma_signal(close: "pd.Series", lookback: int) -> "pd.Series":
    """True at t if close[t] > mean(close[t-lookback+1 .. t]). NaN (flat) until defined."""
    raise NotImplementedError


def realised_vol(close: "pd.Series", window: int, periods_per_year: int) -> "pd.Series":
    """Annualised stdev (ddof=1) of the last `window` daily log returns ending at t, x sqrt(periods_per_year)."""
    raise NotImplementedError


def sleeve_weight(vol: "pd.Series", sigma_target: float, n_instruments: int) -> "pd.Series":
    """(1/N) * min(1, sigma_target / vol). Never above 1/N, so gross exposure <= 100%."""
    raise NotImplementedError


def decision_dates(index: "pd.DatetimeIndex", rebalance: str) -> "pd.DatetimeIndex":
    """Closes at which a rebalance is decided: the last bar BEFORE the first bar of each ISO week (Monday) or
    calendar month, so the fill happens at the open of that first bar."""
    raise NotImplementedError


def target_weights(panel: "Panel", variant: Variant, cfg: "MarketConfig") -> "pd.DataFrame":
    """Target weight per (decision date, symbol): sleeve_weight if the signal is long, else 0.
    Index = every bar of the panel (the engine uses rows at decision dates only). Missing data -> NaN."""
    raise NotImplementedError


def benchmark_weights(panel: "Panel") -> "pd.DataFrame":
    """Equal weight 1/N in every instrument at every bar (monthly rebalance is applied by the engine)."""
    raise NotImplementedError
