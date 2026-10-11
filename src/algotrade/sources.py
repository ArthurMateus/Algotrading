"""Keyless, read-only HTTP GETs and parsers for every external source. The ONLY module that touches the network.

Owner: data-engineer. Stdlib (urllib.request, zipfile, csv, json) plus pandas for the parsed frames. Polite: fixed
User-Agent, timeouts, retries with backoff, a small delay between requests. No auth headers ever. Parsers are pure
and are tested on recorded real responses in `tests/fixtures/`. Bar parsers return the bar contract described in
`data.py` (DatetimeIndex "date", float64 open high low close volume).

Extras beyond the SPEC list (additive): `binance_daily_kline_url`, `stooq_url`, `yahoo_chart_url`, `fred_url`,
`sgs_url`, `exchange_info_url`, `parse_yahoo_dividends`, `SourceError.status`.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    pass

USER_AGENT = "algotrade-research/0.1 (paper-trading tryout; read-only public data)"
POLITE_DELAY = 0.25          # seconds between any two requests (tests set this to 0)
BACKOFF_BASE = 1.0           # seconds; doubles each retry (tests set this to 0)
BAR_COLUMNS = ["open", "high", "low", "close", "volume"]

_last_request_at = 0.0


class SourceError(RuntimeError):
    """Download failed after retries, or a response could not be parsed."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def http_get(url: str, *, params: dict[str, str] | None = None, timeout: float = 30.0, retries: int = 3) -> bytes:
    """GET a public URL and return the body. Raises SourceError. 4xx (except 429) is not retried."""
    global _last_request_at
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    if not url.lower().startswith(("http://", "https://")):
        raise SourceError(f"refusing non-http url: {url}")
    last: Exception | None = None
    status: int | None = None
    for attempt in range(retries + 1):
        wait = POLITE_DELAY - (time.monotonic() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            last, status = e, e.code
            if 400 <= e.code < 500 and e.code != 429:
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last = e
        if attempt < retries:
            time.sleep(BACKOFF_BASE * (2 ** attempt))
    raise SourceError(f"GET failed: {url}: {last}", status=status)


# ---------------------------------------------------------------- URL builders

def binance_kline_url(base: str, symbol: str, month: str) -> str:
    """Monthly 1d kline zip URL: {base}/data/spot/monthly/klines/{symbol}/1d/{symbol}-1d-{YYYY-MM}.zip."""
    return f"{base.rstrip('/')}/data/spot/monthly/klines/{symbol}/1d/{symbol}-1d-{month}.zip"


def binance_daily_kline_url(base: str, symbol: str, day: str) -> str:
    """Daily 1d kline zip URL: {base}/data/spot/daily/klines/{symbol}/1d/{symbol}-1d-{YYYY-MM-DD}.zip."""
    return f"{base.rstrip('/')}/data/spot/daily/klines/{symbol}/1d/{symbol}-1d-{day}.zip"


def exchange_info_url(base: str, symbols: list[str]) -> str:
    return f"{base.rstrip('/')}/api/v3/exchangeInfo?symbols=" + urllib.parse.quote(json.dumps(symbols, separators=(",", ":")))


def stooq_url(base: str, symbol: str) -> str:
    return f"{base.rstrip('/')}/q/d/l/?s={symbol.lower()}.us&i=d"


def yahoo_chart_url(base: str, symbol: str, start: str, end: str) -> str:
    """Daily chart with dividend and split events. `start`/`end` are ISO dates; end is exclusive-ish (+1 day)."""
    p1 = int(dt.datetime.fromisoformat(start).replace(tzinfo=dt.timezone.utc).timestamp())
    p2 = int(dt.datetime.fromisoformat(end).replace(tzinfo=dt.timezone.utc).timestamp())
    return (f"{base.rstrip('/')}/v8/finance/chart/{symbol}?period1={p1}&period2={p2}"
            "&interval=1d&events=div%2Csplit")


def fred_url(base: str, series: str, start: str | None = None, end: str | None = None) -> str:
    url = f"{base.rstrip('/')}/graph/fredgraph.csv?id={series}"
    if start:
        url += f"&cosd={start}"
    if end:
        url += f"&coed={end}"
    return url


def sgs_url(base: str, series: int, start: dt.date, end: dt.date) -> str:
    return (f"{base.rstrip('/')}/dados/serie/bcdata.sgs.{series}/dados?formato=json"
            f"&dataInicial={start:%d/%m/%Y}&dataFinal={end:%d/%m/%Y}")


# ---------------------------------------------------------------- parsers

def _empty_bars() -> pd.DataFrame:
    import pandas as pd
    idx = pd.DatetimeIndex([], name="date")
    return pd.DataFrame({c: pd.Series([], dtype="float64") for c in BAR_COLUMNS}, index=idx)


def parse_binance_klines_zip(raw: bytes) -> "pd.DataFrame":
    """Kline zip (monthly or daily) -> bar frame. Handles millisecond and microsecond open-time units."""
    import pandas as pd
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".csv")]
            if len(names) != 1:
                raise SourceError(f"expected one csv in kline zip, found {z.namelist()}")
            text = z.read(names[0]).decode("utf-8")
    except zipfile.BadZipFile as e:
        raise SourceError(f"not a zip file: {e}") from e
    rows = []
    for rec in csv.reader(io.StringIO(text)):
        if not rec:
            continue
        try:
            t = int(rec[0])
        except ValueError:
            continue                      # header row (newer files have one)
        if len(rec) < 6:
            raise SourceError(f"kline row has {len(rec)} fields: {rec}")
        # ms ~ 1.5e12, us ~ 1.5e15 for current dates; anything >= 1e14 is microseconds.
        unit = "us" if t >= 10**14 else "ms"
        rows.append((pd.Timestamp(t, unit=unit), *[float(x) for x in rec[1:6]]))
    if not rows:
        return _empty_bars()
    df = pd.DataFrame(rows, columns=["t", *BAR_COLUMNS])
    # Open time is 00:00:00 UTC for 1d klines; floor defensively.
    df["date"] = pd.DatetimeIndex(df["t"]).floor("D").astype("datetime64[ns]")
    df = df.drop(columns="t").set_index("date")
    return df.astype("float64")


def parse_exchange_info(raw: bytes) -> dict[str, dict[str, float]]:
    """exchangeInfo JSON -> {symbol: {"min_notional": x, "step_size": y}} from NOTIONAL/MIN_NOTIONAL and LOT_SIZE."""
    try:
        data = json.loads(raw)
        out: dict[str, dict[str, float]] = {}
        for s in data["symbols"]:
            entry: dict[str, float] = {}
            for f in s["filters"]:
                ft = f["filterType"]
                if ft in ("NOTIONAL", "MIN_NOTIONAL") and "min_notional" not in entry:
                    entry["min_notional"] = float(f["minNotional"])
                elif ft == "LOT_SIZE":
                    entry["step_size"] = float(f["stepSize"])
            out[s["symbol"]] = entry
        return out
    except (ValueError, KeyError, TypeError) as e:
        raise SourceError(f"cannot parse exchangeInfo: {e!r}") from e


def parse_stooq_csv(raw: bytes) -> "pd.DataFrame":
    """Stooq daily CSV -> bar frame. Whether it is dividend-adjusted must be verified, not assumed.

    Stooq answers automated clients with a JavaScript proof-of-work page (HTTP 200, HTML). That is not data:
    SourceError. This module does not try to solve it (that would be circumventing a bot check).
    """
    import pandas as pd
    text = raw.decode("utf-8", errors="replace").lstrip("﻿")
    first = text.splitlines()[0].strip().lower() if text.strip() else ""
    if not first.startswith("date,open,high,low,close"):
        raise SourceError(f"stooq did not return a CSV (blocked or no data): {text[:80]!r}")
    df = pd.read_csv(io.StringIO(text))
    df.columns = [c.strip().lower() for c in df.columns]
    if "volume" not in df.columns:
        df["volume"] = float("nan")
    df["date"] = pd.to_datetime(df["date"]).astype("datetime64[ns]")
    df = df.set_index("date")[BAR_COLUMNS].astype("float64")
    return df


def _chart_result(raw: bytes) -> dict:
    try:
        d = json.loads(raw)
        chart = d["chart"]
        if chart.get("error"):
            raise SourceError(f"yahoo error: {chart['error']}")
        return chart["result"][0]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise SourceError(f"cannot parse yahoo chart: {e!r}") from e


def parse_yahoo_chart(raw: bytes) -> "pd.DataFrame":
    """Yahoo v8 chart JSON -> bar frame with OHLC scaled by adjclose/close (total return).

    The date is the UTC date of the bar timestamp (the 09:30 New York open is 13:30/14:30 UTC, same date).
    Rows with a null OHLC are dropped; their count is in `df.attrs["dropped_null_rows"]`.
    """
    import pandas as pd
    res = _chart_result(raw)
    try:
        ts = res.get("timestamp") or []
        q = res["indicators"]["quote"][0]
        adj = res["indicators"]["adjclose"][0]["adjclose"]
    except (KeyError, IndexError, TypeError) as e:
        raise SourceError(f"yahoo chart has no price arrays: {e!r}") from e
    if not ts:
        df = _empty_bars()
        df.attrs["dropped_null_rows"] = 0
        return df
    df = pd.DataFrame({
        "t": ts, "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"],
        "volume": q["volume"], "adj": adj,
    })
    for c in ["open", "high", "low", "close", "volume", "adj"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    bad = df[["open", "high", "low", "close", "adj"]].isna().any(axis=1)
    dropped = int(bad.sum())
    df = df[~bad].copy()
    factor = df["adj"] / df["close"]
    for c in ["open", "high", "low", "close"]:
        df[c] = df[c] * factor
    df["volume"] = df["volume"].fillna(0.0)
    df["date"] = pd.to_datetime(df["t"], unit="s").dt.floor("D").astype("datetime64[ns]")
    out = df.set_index("date")[BAR_COLUMNS].astype("float64")
    out.attrs["dropped_null_rows"] = dropped
    return out


def parse_yahoo_dividends(raw: bytes) -> "pd.Series":
    """Dividend events in a Yahoo chart response -> float Series (cash per share) indexed by ex-date."""
    import pandas as pd
    res = _chart_result(raw)
    divs = (res.get("events") or {}).get("dividends") or {}
    rows = sorted((int(v["date"]), float(v["amount"])) for v in divs.values())
    idx = pd.DatetimeIndex([pd.Timestamp(t, unit="s").floor("D") for t, _ in rows], name="date").astype("datetime64[ns]")
    return pd.Series([a for _, a in rows], index=idx, dtype="float64", name="dividend")


def parse_fred_csv(raw: bytes) -> "pd.Series":
    """FRED fredgraph.csv (DTB3) -> float Series of annual percent rates; '.' means missing."""
    import pandas as pd
    text = raw.decode("utf-8", errors="replace").lstrip("﻿")
    lines = text.strip().splitlines()
    if len(lines) < 2 or "," not in lines[0] or not lines[0].lower().startswith(("observation_date", "date")):
        raise SourceError(f"not a FRED csv: {text[:80]!r}")
    df = pd.read_csv(io.StringIO(text), na_values=["."], dtype={1: "float64"})
    name = df.columns[1]
    s = pd.Series(df[name].astype("float64").to_numpy(),
                  index=pd.DatetimeIndex(pd.to_datetime(df.iloc[:, 0]), name="date").astype("datetime64[ns]"), name=name)
    return s


def parse_sgs_json(raw: bytes) -> "pd.Series":
    """BCB SGS JSON list of {"data": "dd/mm/yyyy", "valor": "x"} -> float Series indexed by date."""
    import pandas as pd
    try:
        rows = json.loads(raw)
        if not isinstance(rows, list):
            raise SourceError(f"SGS did not return a list: {str(rows)[:120]}")
        dates = pd.to_datetime([r["data"] for r in rows], format="%d/%m/%Y")
        vals = [float(str(r["valor"]).replace(",", ".")) for r in rows]
    except (ValueError, KeyError, TypeError) as e:
        raise SourceError(f"cannot parse SGS json: {e!r}") from e
    return pd.Series(vals, index=pd.DatetimeIndex(dates, name="date").astype("datetime64[ns]"), dtype="float64", name="valor")
