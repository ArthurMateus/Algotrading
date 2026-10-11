"""Download, cache (Parquet under data/), integrity-check and align market and auxiliary data.

Owner: data-engineer.

Bar contract (`Bars.frame`): pandas DataFrame, DatetimeIndex named "date", tz-naive midnight = UTC calendar date
of the bar (A: the US session date; B: the 00:00-24:00 UTC day), strictly increasing, no duplicates; float64
columns open, high, low, close, volume. For A, OHLC are adjusted for splits and dividends when
`adjusted == "total_return"`. Cache: data/bars/<market>/<symbol>.parquet plus data/bars/<market>/manifest.json
(source, adjusted, fetched_at UTC, first/last date, rows, sha256). Aux series: data/aux/<name>.parquet.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np

from algotrade import sources

if TYPE_CHECKING:
    from algotrade.config import MarketConfig

BAR_COLUMNS = ["open", "high", "low", "close", "volume"]
BINANCE_FIRST_MONTH = "2017-07"      # first month probed; earlier months are not published (404 before listing)
YAHOO_START = "2000-01-01"
SGS_START = dt.date(2000, 1, 1)
SGS_CHUNK_YEARS = 9                  # the API refuses windows longer than 10 years for daily series
STOOQ_ADJUSTED = "price_only"        # unverified (the source is unreachable by script), so never assumed adjusted
OUTLIER_LOG_RETURN = {True: 0.25, False: 0.10}   # keyed by daily_calendar (crypto, ETF); report only
STALE_RUN = 5                        # identical closes for this many consecutive bars -> "stale"
TRADING_GAP_DAYS = 4                 # ETF bars further apart than this many calendar days -> "gap"


class DataError(RuntimeError):
    """The cache is missing or inconsistent. Never fixed by silently fetching."""


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
    # Additive field: True on dates with a real SGS 12 observation (Brazilian business days). Forward-filled
    # `cdi_daily` repeats the last value on weekends/holidays; compound only where this is True.
    cdi_business_day: "pd.Series | None" = None


@dataclass(frozen=True)
class Issue:
    symbol: str
    date: str
    kind: str                      # "gap" | "duplicate" | "non_monotonic" | "bad_ohlc" | "outlier" | "stale"
    detail: str


# ---------------------------------------------------------------- paths, manifests

def _bars_dir(cfg: "MarketConfig") -> Path:
    return Path(cfg.data_dir) / "bars" / cfg.name


def _aux_dir(cfg: "MarketConfig") -> Path:
    return Path(cfg.data_dir) / "aux"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise DataError(f"corrupt json cache {path}: {e}") from e


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def _ns(index: "pd.Index") -> "pd.DatetimeIndex":
    import pandas as pd
    return pd.DatetimeIndex(index, name="date").astype("datetime64[ns]")


def _clean_frame(df: "pd.DataFrame", end: dt.date) -> "pd.DataFrame":
    """Sort, drop exact index duplicates keeping the last row, truncate at `end` inclusive."""
    import pandas as pd
    df = df.copy()
    df.index = _ns(df.index)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df.loc[df.index <= pd.Timestamp(end)][BAR_COLUMNS].astype("float64")


def _save_bars(cfg: "MarketConfig", bars: Bars) -> None:
    d = _bars_dir(cfg)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{bars.symbol}.parquet"
    bars.frame.to_parquet(path, engine="pyarrow")
    man = _read_json(d / "manifest.json")
    f = bars.frame
    man[bars.symbol] = {
        "source": bars.source, "adjusted": bars.adjusted, "fetched_at": _now_utc(),
        "first": f.index[0].date().isoformat() if len(f) else None,
        "last": f.index[-1].date().isoformat() if len(f) else None,
        "rows": int(len(f)), "sha256": _sha256_file(path),
    }
    _write_json(d / "manifest.json", man)


# ---------------------------------------------------------------- downloads

def _month_iter(first: str, last: dt.date):
    y, m = int(first[:4]), int(first[5:7])
    while (y, m) <= (last.year, last.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def _month_end(y: int, m: int) -> dt.date:
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    return dt.date(ny, nm, 1) - dt.timedelta(days=1)


def _fetch_binance(cfg: "MarketConfig", symbol: str, end: dt.date, existing: "pd.DataFrame | None",
                   issues: list[Issue]) -> "pd.DataFrame":
    import pandas as pd
    base = cfg.urls["binance_vision"]
    today = dt.datetime.now(dt.timezone.utc).date()
    last_avail = min(end, today - dt.timedelta(days=1))      # a daily file appears the day after
    first = BINANCE_FIRST_MONTH
    found = False
    frames = []
    if existing is not None and len(existing):
        frames.append(existing)
        found = True
        first = existing.index[-1].strftime("%Y-%m")
    for y, m in _month_iter(first, end):
        mend = _month_end(y, m)
        got = False
        if mend <= last_avail:
            try:
                frames.append(sources.parse_binance_klines_zip(
                    sources.http_get(sources.binance_kline_url(base, symbol, f"{y:04d}-{m:02d}"))))
                got = found = True
            except sources.SourceError as e:
                if e.status != 404:
                    raise
        if got or not (found or mend > last_avail or (y, m) == (end.year, end.month)):
            continue                       # monthly file loaded, or the month is before the pair was listed
        day = dt.date(y, m, 1)
        while day <= min(mend, last_avail):
            try:
                frames.append(sources.parse_binance_klines_zip(
                    sources.http_get(sources.binance_daily_kline_url(base, symbol, day.isoformat()))))
                found = True
            except sources.SourceError as e:
                if e.status != 404:
                    raise
                if found:
                    issues.append(Issue(symbol, day.isoformat(), "source", "daily and monthly kline file not found (404)"))
            day += dt.timedelta(days=1)
    if not frames:
        raise DataError(f"{symbol}: no kline data found at {base}")
    return _clean_frame(pd.concat(frames), end)


def _fetch_stock(cfg: "MarketConfig", symbol: str, end: dt.date, state: dict, issues: list[Issue]) -> Bars:
    """Try cfg.sources in order. First total-return source wins; a price-only one is the last resort."""
    fallback: Bars | None = None
    errors = []
    for src in cfg.sources:
        if src in state["dead"]:
            continue
        try:
            if src == "stooq":
                df = sources.parse_stooq_csv(sources.http_get(sources.stooq_url(cfg.urls["stooq"], symbol)))
                cand = Bars(symbol, "stooq", STOOQ_ADJUSTED, _clean_frame(df, end))  # type: ignore[arg-type]
            elif src == "yahoo":
                url = sources.yahoo_chart_url(cfg.urls["yahoo"], symbol, YAHOO_START,
                                              (end + dt.timedelta(days=2)).isoformat())
                df = sources.parse_yahoo_chart(sources.http_get(url, timeout=60))
                if df.attrs.get("dropped_null_rows"):
                    issues.append(Issue(symbol, "", "source", f"yahoo: dropped {df.attrs['dropped_null_rows']} null OHLC rows"))
                cand = Bars(symbol, "yahoo", "total_return", _clean_frame(df, end))
            else:
                raise DataError(f"unknown stock source {src!r}")
        except sources.SourceError as e:
            state["dead"].add(src)         # do not hammer a source that just failed or blocked us
            errors.append(f"{src}: {e}")
            issues.append(Issue(symbol, "", "source", f"{src} failed, trying next source: {e}"[:300]))
            continue
        if cand.adjusted == "total_return":
            return cand
        fallback = fallback or cand
    if fallback is not None:
        issues.append(Issue(symbol, "", "source", "only a price-only (not dividend-adjusted) source worked"))
        return fallback
    raise DataError(f"{symbol}: every source failed: {errors}")


def fetch_market(cfg: "MarketConfig", end_date: str | None = None) -> list[Issue]:
    """Download (incrementally) every instrument to the cache up to cfg.end_date; return integrity issues.

    `end_date` (additive, optional) overrides cfg.end_date, e.g. for forward paper data after the criteria period.
    Issues of kind "source" record fallbacks (a source failed or was blocked); the others are integrity findings.
    """
    import pandas as pd
    end = dt.date.fromisoformat(end_date or cfg.end_date)
    issues: list[Issue] = []
    state = {"dead": set()}
    all_bars: dict[str, Bars] = {}
    for sym in cfg.instruments:
        if "binance_vision" in cfg.sources:
            path = _bars_dir(cfg) / f"{sym}.parquet"
            existing = None
            if path.exists():
                existing = _ns_frame(pd.read_parquet(path))
            frame = _fetch_binance(cfg, sym, end, existing, issues)
            bars = Bars(sym, "binance_vision", "none", frame)
        else:
            bars = _fetch_stock(cfg, sym, end, state, issues)
        _save_bars(cfg, bars)
        all_bars[sym] = bars
        issues.extend(check_integrity(bars, daily_calendar="binance_vision" in cfg.sources))
    issues.extend(_peer_calendar_issues(all_bars))
    _write_json(_bars_dir(cfg) / "issues.json", {
        "generated_at": _now_utc(), "end_date": end.isoformat(),
        "issues": [i.__dict__ for i in issues]})
    return issues


def _ns_frame(df: "pd.DataFrame") -> "pd.DataFrame":
    df = df.copy()
    df.index = _ns(df.index)
    return df


def _peer_calendar_issues(bars: dict[str, Bars]) -> list[Issue]:
    """ETFs: a weekday on which at least 3 peers have a bar but this one does not (and it is inside its range)."""
    import pandas as pd
    if len(bars) < 4 or any(b.source == "binance_vision" for b in bars.values()):
        return []
    counts = pd.concat([pd.Series(1, index=b.frame.index) for b in bars.values()], axis=1).sum(axis=1)
    issues = []
    for sym, b in bars.items():
        if not len(b.frame):
            continue
        rng = counts.loc[b.frame.index[0]:b.frame.index[-1]]
        missing = rng.index.difference(b.frame.index)
        for d in missing[rng.loc[missing] >= 3]:
            issues.append(Issue(sym, d.date().isoformat(), "gap", f"no bar while {int(rng.loc[d])} peers have one"))
    return issues


def _save_aux_series(cfg: "MarketConfig", name: str, s: "pd.Series", url: str) -> None:
    d = _aux_dir(cfg)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.parquet"
    s = s[~s.index.duplicated(keep="last")].sort_index().astype("float64")
    s.rename(name).to_frame().to_parquet(path, engine="pyarrow")
    man = _read_json(d / "manifest.json")
    valid = s.dropna()
    man[name] = {"source": url, "fetched_at": _now_utc(),
                 "first": valid.index[0].date().isoformat() if len(valid) else None,
                 "last": valid.index[-1].date().isoformat() if len(valid) else None,
                 "rows": int(len(s)), "sha256": _sha256_file(path)}
    _write_json(d / "manifest.json", man)


def fetch_aux(cfg: "MarketConfig", end_date: str | None = None) -> list[Issue]:
    """Download DTB3 (FRED), SGS 1 and 12 (BCB, chunked by date range) and, for B, exchangeInfo, to the cache.

    Returns "source" Issues for series that failed (the cache is left as it was); it does not raise for those,
    because `load_aux` degrades as the SPEC says (rf = 0 and rf_available = False when DTB3 is missing).
    """
    import pandas as pd
    end = dt.date.fromisoformat(end_date or cfg.end_date)
    issues: list[Issue] = []
    try:
        url = sources.fred_url(cfg.urls["fred"], "DTB3")
        s = sources.parse_fred_csv(sources.http_get(url, timeout=60))
        _save_aux_series(cfg, "dtb3", s, url)
    except sources.SourceError as e:
        issues.append(Issue("DTB3", "", "source", f"FRED DTB3 failed: {e}"[:300]))
    for number, name in ((1, "ptax"), (12, "cdi")):
        try:
            parts = []
            start = SGS_START
            while start <= end:
                stop = min(dt.date(start.year + SGS_CHUNK_YEARS, 12, 31), end)
                parts.append(sources.parse_sgs_json(
                    sources.http_get(sources.sgs_url(cfg.urls["bcb_sgs"], number, start, stop))))
                start = stop + dt.timedelta(days=1)
            _save_aux_series(cfg, name, pd.concat(parts), f"{cfg.urls['bcb_sgs']}/dados/serie/bcdata.sgs.{number}/dados")
        except sources.SourceError as e:
            issues.append(Issue(f"SGS{number}", "", "source", f"BCB SGS {number} failed: {e}"[:300]))
    if "binance_vision" in cfg.sources:
        try:
            url = sources.exchange_info_url(cfg.urls["binance_api"], list(cfg.instruments))
            info = sources.parse_exchange_info(sources.http_get(url))
            _write_json(_aux_dir(cfg) / "exchange_info.json", {
                "fetched_at": _now_utc(), "source": url,
                "symbols": {k: v for k, v in info.items() if k in cfg.instruments}})
        except sources.SourceError as e:
            issues.append(Issue("exchangeInfo", "", "source", f"exchangeInfo failed, config fallback used: {e}"[:300]))
    return issues


# ---------------------------------------------------------------- cache readers (no network)

def load_bars(cfg: "MarketConfig") -> dict[str, Bars]:
    """Read cached bars (no network). Raises if the cache is missing; never fetches silently."""
    import pandas as pd
    d = _bars_dir(cfg)
    man = _read_json(d / "manifest.json")
    out: dict[str, Bars] = {}
    for sym in cfg.instruments:
        path = d / f"{sym}.parquet"
        if not path.exists() or sym not in man:
            raise DataError(f"no cached bars for {sym} in {d}: run `uv run algotrade fetch --market {cfg.name}`")
        meta = man[sym]
        out[sym] = Bars(sym, meta["source"], meta["adjusted"], _ns_frame(pd.read_parquet(path)))
    return out


def check_integrity(bars: Bars, *, daily_calendar: bool) -> list[Issue]:
    """Gaps vs the expected calendar, duplicates, non-monotonic index, high < low or close outside [low, high],
    non-positive prices, |log return| outliers. Issues are reported, never silently dropped."""
    import pandas as pd
    sym, df = bars.symbol, bars.frame
    issues: list[Issue] = []
    idx = pd.DatetimeIndex(df.index)
    iso = lambda t: pd.Timestamp(t).date().isoformat()   # noqa: E731
    for t in idx[idx.duplicated(keep="first")].unique():
        issues.append(Issue(sym, iso(t), "duplicate", f"{int((idx == t).sum())} rows share this date"))
    if not idx.is_monotonic_increasing:
        n = int((idx[1:] <= idx[:-1]).sum())
        issues.append(Issue(sym, "", "non_monotonic", f"{n} positions where the date does not increase"))
    df = df[~idx.duplicated(keep="last")].sort_index()
    if df.empty:
        return issues + [Issue(sym, "", "gap", "no rows")]
    ohlc = df[["open", "high", "low", "close"]]
    for t in df.index[(ohlc <= 0).any(axis=1) | ohlc.isna().any(axis=1)]:
        issues.append(Issue(sym, iso(t), "bad_ohlc", "non-positive or missing price"))
    tol = 1e-9
    bad = ((df["high"] < df["low"] * (1 - tol))
           | (df["close"] > df["high"] * (1 + tol)) | (df["close"] < df["low"] * (1 - tol))
           | (df["open"] > df["high"] * (1 + tol)) | (df["open"] < df["low"] * (1 - tol)))
    for t in df.index[bad & (ohlc > 0).all(axis=1)]:
        r = df.loc[t]
        issues.append(Issue(sym, iso(t), "bad_ohlc",
                            f"o={r.open:.6g} h={r.high:.6g} l={r.low:.6g} c={r.close:.6g} inconsistent"))
    # gaps
    if daily_calendar:
        missing = pd.date_range(df.index[0], df.index[-1], freq="D").difference(df.index)
        if len(missing):
            runs = (pd.Series(missing).diff() != pd.Timedelta(days=1)).cumsum().to_numpy()
            for r in np.unique(runs):
                block = missing[runs == r]
                issues.append(Issue(sym, iso(block[0]), "gap", f"{len(block)} missing day(s) {iso(block[0])}..{iso(block[-1])}"))
    else:
        gaps = pd.Series(df.index[1:] - df.index[:-1], index=df.index[1:])
        for t, g in gaps[gaps > pd.Timedelta(days=TRADING_GAP_DAYS)].items():
            issues.append(Issue(sym, iso(t), "gap", f"{g.days} calendar days since the previous bar"))
    # outliers (reported, never dropped)
    thr = OUTLIER_LOG_RETURN[daily_calendar]
    pos = df["close"].where(df["close"] > 0)
    lr = np.log(pos).diff()
    for t, v in lr[lr.abs() > thr].items():
        issues.append(Issue(sym, iso(t), "outlier", f"log return {v:+.3f} (threshold {thr})"))
    # stale: the same close for STALE_RUN or more consecutive bars
    same = (df["close"].diff() == 0)
    run = same.groupby((~same).cumsum()).cumsum()
    for t in df.index[run == STALE_RUN - 1]:
        issues.append(Issue(sym, iso(t), "stale", f"close unchanged for {STALE_RUN}+ consecutive bars"))
    zero = df["volume"] <= 0
    if zero.any():
        issues.append(Issue(sym, iso(df.index[zero][0]), "bad_ohlc", f"{int(zero.sum())} bar(s) with zero volume"))
    return issues


def build_panel(bars: dict[str, Bars], end_date: str) -> Panel:
    """Align instruments on the market calendar, truncated at end_date inclusive."""
    import pandas as pd
    if not bars:
        raise DataError("no bars to align")
    end = pd.Timestamp(end_date)
    firsts = [b.frame.index[0] for b in bars.values()]
    lasts = [min(b.frame.index[-1], end) for b in bars.values()]
    crypto = any(b.source == "binance_vision" for b in bars.values())
    if crypto:
        cal = pd.date_range(min(firsts), max(lasts), freq="D", name="date")
    else:
        cal = pd.DatetimeIndex(sorted(set().union(*[set(b.frame.index[b.frame.index <= end]) for b in bars.values()])),
                               name="date")
    syms = list(bars)
    open_ = pd.DataFrame({s: bars[s].frame["open"].reindex(cal) for s in syms}, index=cal)
    close = pd.DataFrame({s: bars[s].frame["close"].reindex(cal) for s in syms}, index=cal)
    valid = open_.notna() & close.notna()
    open_, close = open_.where(valid), close.where(valid)
    kinds = {b.adjusted for b in bars.values()}
    adjusted = "price_only" if "price_only" in kinds else ("total_return" if "total_return" in kinds else "none")
    return Panel(open=open_, close=close, valid=valid, adjusted=adjusted)


def _read_aux_series(cfg: "MarketConfig", name: str) -> "pd.Series | None":
    import pandas as pd
    path = _aux_dir(cfg) / f"{name}.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    s = df.iloc[:, 0].astype("float64")
    s.index = _ns(s.index)
    return s


def _ffill_to(s: "pd.Series | None", index: "pd.DatetimeIndex") -> "pd.Series":
    import pandas as pd
    if s is None or s.dropna().empty:
        return pd.Series(np.nan, index=index, dtype="float64")
    union = s.index.union(index)
    return s.reindex(union).ffill().reindex(index)


def load_aux(cfg: "MarketConfig", index: "pd.DatetimeIndex") -> Aux:
    """Read cached aux series and align them to `index` (forward fill only).

    rf_per_bar = DTB3 / 100 / periods_per_year (zeros and rf_available=False if DTB3 is missing; leading dates
    before the first observation are 0). ptax and cdi_daily are NaN where the cache has nothing yet.
    """
    import pandas as pd
    index = _ns(index)
    dtb3 = _read_aux_series(cfg, "dtb3")
    rf_ok = dtb3 is not None and not dtb3.dropna().empty
    rf = _ffill_to(dtb3, index) / 100.0 / cfg.periods_per_year
    rf = rf.fillna(0.0) if rf_ok else pd.Series(0.0, index=index)
    cdi = _read_aux_series(cfg, "cdi")
    cdi_frac = _ffill_to(cdi, index) / 100.0
    bday = pd.Series(index.isin(cdi.dropna().index) if cdi is not None else False, index=index)
    return Aux(rf_per_bar=rf.rename("rf_per_bar"), rf_available=bool(rf_ok),
               ptax=_ffill_to(_read_aux_series(cfg, "ptax"), index).rename("ptax"),
               cdi_daily=cdi_frac.rename("cdi_daily"), cdi_business_day=bday.rename("cdi_business_day"))


def _exchange_info(cfg: "MarketConfig") -> dict[str, dict[str, float]]:
    return _read_json(_aux_dir(cfg) / "exchange_info.json").get("symbols", {})


def min_order_usd(cfg: "MarketConfig") -> dict[str, float]:
    """Per-symbol minimum order notional: exchangeInfo NOTIONAL filter for B (fallback cfg value), cfg for A."""
    info = _exchange_info(cfg) if "binance_vision" in cfg.sources else {}
    return {s: float(info.get(s, {}).get("min_notional", cfg.costs.min_order_usd)) for s in cfg.instruments}


def lot_step(cfg: "MarketConfig") -> dict[str, float]:
    """Per-symbol quantity step: exchangeInfo LOT_SIZE stepSize for B; 0.0 (no rounding) for A and as fallback."""
    info = _exchange_info(cfg) if "binance_vision" in cfg.sources else {}
    return {s: float(info.get(s, {}).get("step_size", 0.0)) for s in cfg.instruments}
