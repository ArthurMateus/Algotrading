"""Re-record the small real responses in tests/fixtures/ from the public keyless endpoints (read-only GETs).

Run:  uv run python tools/record_fixtures.py
Polite: a handful of requests through algotrade.sources.http_get (fixed User-Agent, delay, retries).
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from algotrade import sources
from algotrade.config import load_config

FIX = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def main() -> int:
    urls = load_config("A").urls
    FIX.mkdir(parents=True, exist_ok=True)
    jobs = {
        # monthly kline zips: 2019 (open time in milliseconds), 2025 (microseconds), one daily zip
        "binance_BTCUSDT-1d-2019-01.zip": sources.binance_kline_url(urls["binance_vision"], "BTCUSDT", "2019-01"),
        "binance_BTCUSDT-1d-2025-01.zip": sources.binance_kline_url(urls["binance_vision"], "BTCUSDT", "2025-01"),
        "binance_ETHUSDT-1d-2026-09-30.zip": sources.binance_daily_kline_url(urls["binance_vision"], "ETHUSDT", "2026-09-30"),
        "binance_exchangeInfo.json": sources.exchange_info_url(urls["binance_api"], ["BTCUSDT", "ETHUSDT"]),
        # SPY across the 2024-12-20 ex-dividend date
        "yahoo_SPY_2024-12.json": sources.yahoo_chart_url(urls["yahoo"], "SPY", "2024-12-10", "2025-01-10"),
        "stooq_SPY_response.html": sources.stooq_url(urls["stooq"], "SPY"),
        "fred_DTB3.csv": sources.fred_url(urls["fred"], "DTB3"),
        "sgs_1.json": sources.sgs_url(urls["bcb_sgs"], 1, dt.date(2026, 9, 1), dt.date(2026, 9, 15)),
        "sgs_12.json": sources.sgs_url(urls["bcb_sgs"], 12, dt.date(2026, 9, 1), dt.date(2026, 9, 15)),
    }
    for name, url in jobs.items():
        body = sources.http_get(url)
        if name == "fred_DTB3.csv":      # the full file is ~300 KB (the cosd/coed query form hangs): keep header + tail
            lines = body.decode("utf-8").splitlines()
            body = ("\n".join([lines[0], *lines[-30:]]) + "\n").encode("utf-8")
        (FIX / name).write_bytes(body)
        print(f"{name}: {len(body)} bytes  <- {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
