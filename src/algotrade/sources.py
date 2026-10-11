"""Keyless, read-only HTTP GETs and parsers for every external source. The ONLY module that touches the network.

Owner: data-engineer. Stdlib only (urllib.request, zipfile, csv, json). Polite: fixed User-Agent, timeouts,
retries with backoff, a small delay between requests. No auth headers ever. Parsers are pure and are tested on
recorded real responses in `tests/fixtures/`. Bar parsers return the bar contract described in `data.py`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


class SourceError(RuntimeError):
    """Download failed after retries, or a response could not be parsed."""


def http_get(url: str, *, params: dict[str, str] | None = None, timeout: float = 30.0, retries: int = 3) -> bytes:
    """GET a public URL and return the body. Raises SourceError."""
    raise NotImplementedError


def binance_kline_url(base: str, symbol: str, month: str) -> str:
    """Monthly 1d kline zip URL: {base}/data/spot/monthly/klines/{symbol}/1d/{symbol}-1d-{YYYY-MM}.zip."""
    raise NotImplementedError


def parse_binance_klines_zip(raw: bytes) -> "pd.DataFrame":
    """Kline zip (monthly or daily) -> bar frame. Handles millisecond and microsecond open-time units."""
    raise NotImplementedError


def parse_exchange_info(raw: bytes) -> dict[str, dict[str, float]]:
    """exchangeInfo JSON -> {symbol: {"min_notional": x, "step_size": y}} from NOTIONAL/MIN_NOTIONAL and LOT_SIZE."""
    raise NotImplementedError


def parse_stooq_csv(raw: bytes) -> "pd.DataFrame":
    """Stooq daily CSV -> bar frame. Whether it is dividend-adjusted must be verified, not assumed."""
    raise NotImplementedError


def parse_yahoo_chart(raw: bytes) -> "pd.DataFrame":
    """Yahoo v8 chart JSON -> bar frame with OHLC scaled by adjclose/close (total return)."""
    raise NotImplementedError


def parse_fred_csv(raw: bytes) -> "pd.Series":
    """FRED fredgraph.csv (DTB3) -> float Series of annual percent rates; '.' means missing."""
    raise NotImplementedError


def parse_sgs_json(raw: bytes) -> "pd.Series":
    """BCB SGS JSON list of {"data": "dd/mm/yyyy", "valor": "x"} -> float Series indexed by date."""
    raise NotImplementedError
