"""Deterministic synthetic bars and markets for tests (seeded numpy generators; no network)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from algotrade.data import Bars


def synth_frame(start: str, n: int, *, seed: int = 0, daily: bool = True, drift: float = 0.0005,
                vol: float = 0.02, p0: float = 100.0) -> pd.DataFrame:
    """Geometric random walk with consistent OHLC. `daily` = every calendar day, else weekdays only."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq="D" if daily else "B", name="date").astype("datetime64[ns]")
    close = p0 * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    open_ = np.concatenate([[p0], close[:-1]]) * np.exp(rng.normal(0, vol / 4, n))
    hi = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, vol / 3, n)))
    lo = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, vol / 3, n)))
    volume = rng.uniform(1e3, 1e4, n)
    return pd.DataFrame({"open": open_, "high": hi, "low": lo, "close": close, "volume": volume}, index=idx)


def synth_bars(symbol: str, start: str = "2020-01-01", n: int = 400, *, seed: int = 0, daily: bool = True,
               source: str | None = None, adjusted: str | None = None, **kw) -> Bars:
    frame = synth_frame(start, n, seed=seed, daily=daily, **kw)
    return Bars(symbol, source or ("binance_vision" if daily else "yahoo"),
                adjusted or ("none" if daily else "total_return"), frame)  # type: ignore[arg-type]


def synth_market(symbols: list[str], start: str = "2020-01-01", n: int = 400, *, seed: int = 0,
                 daily: bool = True) -> dict[str, Bars]:
    return {s: synth_bars(s, start, n, seed=seed + i, daily=daily) for i, s in enumerate(symbols)}
