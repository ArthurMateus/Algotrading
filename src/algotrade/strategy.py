"""Signals, volatility-target sizing and the rebalance schedule. Pure, deterministic, look-ahead free.

Owner: strategy-developer. Every value indexed at date t uses only closes up to and including t. The engine fills
decisions at the OPEN of the next bar (t+1). Parameters come only from config (= docs/success-criteria.md §3).

Conventions (docs/SPEC.md §3, §11):
- Signals are float64 series: 1.0 = long, 0.0 = flat, NaN = undefined (warm-up or no bar on that row; the caller
  treats NaN as "no decision"). Lookbacks and the vol window count REAL bars of the instrument: NaN rows of the
  input (panel rows where `valid` is False) are skipped, never filled, and get NaN in the output.
- Rolling means and standard deviations use `math.fsum` per window (correctly rounded), so a value at t is a
  function of the window's numbers only: appending or changing later bars cannot change it, not even in the last bit.
- pandas is imported inside functions only (a top-level import pulls `hmac` into sys.modules; tests/test_safety.py).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

    from algotrade.config import MarketConfig
    from algotrade.data import Panel

SIGNALS = ("TSMOM", "SMA")
REBALANCES = ("weekly", "monthly")


@dataclass(frozen=True, order=True)
class Variant:
    signal: Literal["TSMOM", "SMA"]
    lookback: int                                  # 63 | 126 | 252
    rebalance: Literal["weekly", "monthly"]

    def __post_init__(self) -> None:
        if self.signal not in SIGNALS:
            raise ValueError(f"unknown signal {self.signal!r}")
        if self.rebalance not in REBALANCES:
            raise ValueError(f"unknown rebalance {self.rebalance!r}")
        if isinstance(self.lookback, bool) or not isinstance(self.lookback, int) or self.lookback < 1:
            raise ValueError(f"lookback must be a positive int, got {self.lookback!r}")

    @property
    def key(self) -> str:
        """Stable id, e.g. 'TSMOM-252-monthly'. Used by the variant log and the cap."""
        return f"{self.signal}-{self.lookback}-{self.rebalance}"


def grid(cfg: "MarketConfig") -> list[Variant]:
    """The 12 pre-registered variants (2 signals x 3 lookbacks x 2 rebalance), in a fixed order.

    Order: config order of signals, then lookbacks, then rebalance (TSMOM-63-weekly, TSMOM-63-monthly, ...).
    Raises ValueError if the config grid holds duplicates or more variants than `variant_cap`.
    """
    variants = [Variant(s, lb, r) for s in cfg.grid_signals for lb in cfg.grid_lookbacks for r in cfg.grid_rebalance]
    if len({v.key for v in variants}) != len(variants):
        raise ValueError("config grid contains duplicate values")
    if len(variants) > cfg.variant_cap:
        raise ValueError(f"grid has {len(variants)} variants, above the cap of {cfg.variant_cap}")
    return variants


# ---------------------------------------------------------------- helpers (numpy on the real bars only)

def _real(close: "pd.Series") -> tuple["pd.Series", np.ndarray]:
    """The non-NaN part of `close` and its float64 values."""
    import pandas as pd
    s = pd.Series(close, dtype="float64")
    real = s[s.notna()]
    return real, real.to_numpy(dtype="float64", copy=True)


def _back(values: np.ndarray, real: "pd.Series", like: "pd.Series", name) -> "pd.Series":
    """Put values computed on the real bars back on the full index (NaN on skipped rows)."""
    import pandas as pd
    out = pd.Series(values, index=real.index, dtype="float64").reindex(like.index)
    out.name = name
    return out


def _check_lookback(n: int, what: str) -> None:
    if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or n < 1:
        raise ValueError(f"{what} must be a positive int, got {n!r}")


def tsmom_signal(close: "pd.Series", lookback: int) -> "pd.Series":
    """True at t if close[t] / close[t - lookback] - 1 > 0. NaN (treated as flat) until defined.

    Returns float64 (1.0 / 0.0 / NaN). Defined from the (lookback+1)-th real bar on.
    """
    _check_lookback(lookback, "lookback")
    real, v = _real(close)
    out = np.full(v.shape, np.nan)
    if len(v) > lookback:
        out[lookback:] = (v[lookback:] / v[:-lookback] - 1.0 > 0.0).astype("float64")
    return _back(out, real, close, getattr(close, "name", None))


def sma_signal(close: "pd.Series", lookback: int) -> "pd.Series":
    """True at t if close[t] > mean(close[t-lookback+1 .. t]). NaN (flat) until defined.

    Returns float64 (1.0 / 0.0 / NaN). Defined from the lookback-th real bar on. A tie (close == SMA) is flat.
    """
    _check_lookback(lookback, "lookback")
    real, v = _real(close)
    out = np.full(v.shape, np.nan)
    vals = v.tolist()
    for t in range(lookback - 1, len(vals)):
        sma = math.fsum(vals[t - lookback + 1:t + 1]) / lookback
        out[t] = 1.0 if vals[t] > sma else 0.0
    return _back(out, real, close, getattr(close, "name", None))


def realised_vol(close: "pd.Series", window: int, periods_per_year: int) -> "pd.Series":
    """Annualised stdev (ddof=1) of the last `window` daily log returns ending at t, x sqrt(periods_per_year).

    Returns are between consecutive REAL bars. Needs window+1 real bars, so it is defined from the
    (window+1)-th real bar on.
    """
    _check_lookback(window, "window")
    if window < 2:
        raise ValueError("window must be >= 2 for a ddof=1 stdev")
    real, v = _real(close)
    out = np.full(v.shape, np.nan)
    if len(v) > window:
        r = np.log(v[1:] / v[:-1]).tolist()          # r[i] is the return ending at real bar i+1
        ann = math.sqrt(periods_per_year)
        for t in range(window, len(v)):
            w = r[t - window:t]
            m = math.fsum(w) / window
            var = math.fsum((x - m) * (x - m) for x in w) / (window - 1)
            out[t] = math.sqrt(var) * ann
    return _back(out, real, close, getattr(close, "name", None))


def sleeve_weight(vol: "pd.Series", sigma_target: float, n_instruments: int) -> "pd.Series":
    """(1/N) * min(1, sigma_target / vol). Never above 1/N, so gross exposure <= 100%.

    NaN vol -> NaN. vol == 0 -> 1/N (the cap binds).
    """
    import pandas as pd
    if n_instruments < 1:
        raise ValueError("n_instruments must be >= 1")
    if not sigma_target > 0:
        raise ValueError("sigma_target must be > 0")
    v = pd.Series(vol, dtype="float64")
    a = v.to_numpy(dtype="float64", copy=True)
    with np.errstate(divide="ignore"):
        ratio = np.where(a > 0, sigma_target / np.where(a > 0, a, 1.0), np.inf)
    w = np.minimum(1.0, ratio) / n_instruments
    w[np.isnan(a)] = np.nan
    return pd.Series(w, index=v.index, name=v.name, dtype="float64")


def _period_key(dates: "pd.DatetimeIndex", rebalance: str) -> np.ndarray:
    if rebalance == "weekly":
        iso = dates.isocalendar()
        return iso["year"].to_numpy(dtype="int64") * 100 + iso["week"].to_numpy(dtype="int64")
    if rebalance == "monthly":
        return dates.year.to_numpy(dtype="int64") * 12 + dates.month.to_numpy(dtype="int64")
    raise ValueError(f"unknown rebalance {rebalance!r}")


def decision_dates(index: "pd.DatetimeIndex", rebalance: str,
                   next_bar: "pd.Timestamp | None" = None) -> "pd.DatetimeIndex":
    """Closes at which a rebalance is decided: the last bar BEFORE the first bar of each ISO week (Monday) or
    calendar month, so the fill happens at the open of that first bar.

    Only bar DATES are used (the calendar), never prices. The first bar of `index` is never a decision (no bar
    before it); SPEC §11.2's "first decision at the window's first close" is the engine's job. The last bar of
    `index` is a decision only if `next_bar` (the date of the next bar, known from the calendar, e.g. in paper
    trading) starts a new week/month. Additive keyword, default None.
    """
    import pandas as pd
    idx = pd.DatetimeIndex(index)
    if rebalance not in REBALANCES:
        raise ValueError(f"unknown rebalance {rebalance!r}")
    if not idx.is_unique or not idx.is_monotonic_increasing:
        raise ValueError("index must be strictly increasing")
    if next_bar is not None:
        nb = pd.Timestamp(next_bar)
        if len(idx) and nb <= idx[-1]:
            raise ValueError("next_bar must be after the last bar of index")
        full = idx.append(pd.DatetimeIndex([nb]))
    else:
        full = idx
    if len(full) < 2:
        return pd.DatetimeIndex([], dtype=idx.dtype, name="date")
    key = _period_key(full, rebalance)
    starts_new = key[1:] != key[:-1]               # bar i+1 is the first bar of a new period
    out = full[:-1][starts_new]
    return pd.DatetimeIndex(out, name="date")


def _instruments(panel: "Panel", cfg: "MarketConfig") -> list[str]:
    syms = list(cfg.instruments)
    missing = [s for s in syms if s not in panel.close.columns]
    if missing:
        raise ValueError(f"panel lacks instruments {missing}")
    return syms


def target_weights(panel: "Panel", variant: Variant, cfg: "MarketConfig") -> "pd.DataFrame":
    """Target weight per (decision date, symbol): sleeve_weight if the signal is long, else 0.
    Index = every bar of the panel (the engine uses rows at decision dates only). Missing data -> NaN.

    Columns = cfg.instruments, N = len(cfg.instruments). NaN where the panel has no valid bar for the symbol on
    that row, or during warm-up (signal or 60-bar vol undefined). A flat signal gives 0 even if vol is undefined.
    """
    import pandas as pd
    syms = _instruments(panel, cfg)
    n = len(syms)
    cols = {}
    for s in syms:
        close = panel.close[s].where(panel.valid[s])
        if variant.signal == "TSMOM":
            sig = tsmom_signal(close, variant.lookback)
        else:
            sig = sma_signal(close, variant.lookback)
        sw = sleeve_weight(realised_vol(close, cfg.vol_window, cfg.periods_per_year), cfg.sigma_target, n)
        sa, wa = sig.to_numpy(), sw.to_numpy()
        w = np.where(sa == 1.0, wa, np.where(sa == 0.0, 0.0, np.nan))
        cols[s] = w
    return pd.DataFrame(cols, index=panel.close.index, columns=syms, dtype="float64")


def benchmark_weights(panel: "Panel") -> "pd.DataFrame":
    """Equal weight 1/N in every instrument at every bar (monthly rebalance is applied by the engine).

    N = number of panel columns. Not NaN on invalid rows: the weight needs no price (the engine still cannot fill
    a symbol without a bar).
    """
    import pandas as pd
    cols = list(panel.close.columns)
    return pd.DataFrame(1.0 / len(cols), index=panel.close.index, columns=cols, dtype="float64")
