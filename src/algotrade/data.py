"""Download, cache (Parquet under data/), integrity-check and align market and auxiliary data.

Owner: data-engineer.

Bar contract (`Bars.frame`): pandas DataFrame, DatetimeIndex named "date", tz-naive midnight = UTC calendar date
of the bar (A: the US session date; B: the 00:00-24:00 UTC day), strictly increasing, no duplicates; float64
columns open, high, low, close, volume. For A, OHLC are adjusted for splits and dividends when
`adjusted == "total_return"`. Cache: data/bars/<market>/<symbol>.parquet plus data/bars/<market>/manifest.json
(source, adjusted, fetched_at UTC, first/last date, rows, sha256). Aux series: data/aux/<name>.parquet.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import pandas as pd

    from algotrade.config import MarketConfig


@dataclass(frozen=True)
class Bars:
    symbol: str
    source: str                                                # "stooq" | "yahoo" | "binance_vision"
    adjusted: Literal["total_return", "price_only", "none"]    # "none" for crypto
    frame: "pd.DataFrame"


@dataclass(frozen=True)
class Panel:
    """Aligned market: date x symbol frames on one calendar (A: union of ETF dates; B: every UTC day)."""
    open: "pd.DataFrame"
    close: "pd.DataFrame"
    valid: "pd.DataFrame"          # bool: a real bar exists for (date, symbol); False means NaN prices
    adjusted: str                  # weakest adjustment across instruments (flagged in reports)


@dataclass(frozen=True)
class Aux:
    """Per-date auxiliary series on the market calendar, forward-filled only (never backward)."""
    rf_per_bar: "pd.Series"        # DTB3 / 100 / periods_per_year; zeros and rf_available=False if DTB3 missing
    rf_available: bool
    ptax: "pd.Series"              # BRL per USD (SGS 1)
    cdi_daily: "pd.Series"         # CDI per day as a fraction (SGS 12 / 100)


@dataclass(frozen=True)
class Issue:
    symbol: str
    date: str
    kind: str                      # "gap" | "duplicate" | "non_monotonic" | "bad_ohlc" | "outlier" | "stale"
    detail: str


def fetch_market(cfg: "MarketConfig") -> list[Issue]:
    """Download (incrementally) every instrument to the cache up to cfg.end_date; return integrity issues."""
    raise NotImplementedError


def fetch_aux(cfg: "MarketConfig") -> None:
    """Download DTB3 (FRED), SGS 1 and 12 (BCB, chunked by date range) and, for B, exchangeInfo, to the cache."""
    raise NotImplementedError


def load_bars(cfg: "MarketConfig") -> dict[str, Bars]:
    """Read cached bars (no network). Raises if the cache is missing; never fetches silently."""
    raise NotImplementedError


def check_integrity(bars: Bars, *, daily_calendar: bool) -> list[Issue]:
    """Gaps vs the expected calendar, duplicates, non-monotonic index, high < low or close outside [low, high],
    non-positive prices, |log return| outliers. Issues are reported, never silently dropped."""
    raise NotImplementedError


def build_panel(bars: dict[str, Bars], end_date: str) -> Panel:
    """Align instruments on the market calendar, truncated at end_date inclusive."""
    raise NotImplementedError


def load_aux(cfg: "MarketConfig", index: "pd.DatetimeIndex") -> Aux:
    """Read cached aux series and align them to `index` (forward fill only)."""
    raise NotImplementedError


def min_order_usd(cfg: "MarketConfig") -> dict[str, float]:
    """Per-symbol minimum order notional: exchangeInfo NOTIONAL filter for B (fallback cfg value), cfg for A."""
    raise NotImplementedError


def lot_step(cfg: "MarketConfig") -> dict[str, float]:
    """Per-symbol quantity step: exchangeInfo LOT_SIZE stepSize for B; 0.0 (no rounding) for A and as fallback."""
    raise NotImplementedError
