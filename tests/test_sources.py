import io
import json
import zipfile

import pandas as pd
import pytest

from algotrade import sources
from algotrade.sources import SourceError
from tests.fakes import FakeServer, fixture


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(sources, "POLITE_DELAY", 0.0)
    monkeypatch.setattr(sources, "BACKOFF_BASE", 0.0)


def test_kline_zip_milliseconds_2019():
    df = sources.parse_binance_klines_zip(fixture("binance_BTCUSDT-1d-2019-01.zip"))
    assert len(df) == 31
    assert df.index[0] == pd.Timestamp("2019-01-01") and df.index[-1] == pd.Timestamp("2019-01-31")
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.is_monotonic_increasing and df.index.name == "date"
    r = df.loc["2019-01-01"]
    assert (r.open, r.high, r.low, r.close) == (3701.23, 3810.16, 3642.00, 3797.14)
    assert r.volume == 23741.687033
    assert (df.dtypes == "float64").all()


def test_kline_zip_microseconds_2025():
    df = sources.parse_binance_klines_zip(fixture("binance_BTCUSDT-1d-2025-01.zip"))
    assert len(df) == 31 and df.index[0] == pd.Timestamp("2025-01-01")
    assert df.loc["2025-01-01", "close"] == 94591.79
    assert df.index.is_unique


def test_kline_daily_zip_and_header_row():
    df = sources.parse_binance_klines_zip(fixture("binance_ETHUSDT-1d-2026-09-30.zip"))
    assert list(df.index) == [pd.Timestamp("2026-09-30")]
    assert df.iloc[0].close == 2686.01
    # newer archives may carry a header line: it must be skipped
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.csv", "open_time,open,high,low,close,volume,close_time\n1735689600000000,1,2,0.5,1.5,10,0\n")
    assert len(sources.parse_binance_klines_zip(buf.getvalue())) == 1


def test_kline_bad_input():
    with pytest.raises(SourceError):
        sources.parse_binance_klines_zip(b"<html>nope</html>")


def test_exchange_info_notional_and_lot_size():
    info = sources.parse_exchange_info(fixture("binance_exchangeInfo.json"))
    assert set(info) == {"BTCUSDT", "ETHUSDT"}
    assert info["BTCUSDT"]["min_notional"] == 5.0
    assert info["BTCUSDT"]["step_size"] == 0.00001
    assert info["ETHUSDT"]["step_size"] > 0
    with pytest.raises(SourceError):
        sources.parse_exchange_info(b"{}")


def test_yahoo_chart_total_return_scaling():
    raw = fixture("yahoo_SPY_2024-12.json")
    df = sources.parse_yahoo_chart(raw)
    assert len(df) == 20 and df.index.is_monotonic_increasing and df.index.is_unique
    assert df.index[0] == pd.Timestamp("2024-12-10")
    divs = sources.parse_yahoo_dividends(raw)
    assert list(divs.index) == [pd.Timestamp("2024-12-20")] and divs.iloc[0] == 1.966
    res = json.loads(raw)["chart"]["result"][0]
    raw_close = res["indicators"]["quote"][0]["close"]
    adj = res["indicators"]["adjclose"][0]["adjclose"]
    assert df["close"].iloc[-1] == pytest.approx(adj[-1])
    assert df["close"].iloc[0] == pytest.approx(adj[0])
    assert adj[0] < raw_close[0]
    assert (df["high"] >= df["low"]).all() and (df["close"] <= df["high"] + 1e-9).all()


def test_yahoo_dividend_is_in_the_adjustment():
    """Evidence that the adjusted series carries the 2024-12-20 distribution of 1.966 per share."""
    res = json.loads(fixture("yahoo_SPY_2024-12.json"))["chart"]["result"][0]
    c = res["indicators"]["quote"][0]["close"]
    a = res["indicators"]["adjclose"][0]["adjclose"]
    ts = [pd.Timestamp(t, unit="s").normalize() for t in res["timestamp"]]
    i = ts.index(pd.Timestamp("2024-12-20"))
    # adjclose/close steps down by (1 - dividend / previous close) across the ex-date (later dividends cancel out)
    step = (a[i - 1] / c[i - 1]) / (a[i] / c[i])
    assert step == pytest.approx(1 - 1.966 / c[i - 1], rel=1e-3)
    assert (a[i + 1] / c[i + 1]) == pytest.approx(a[i] / c[i])


def test_yahoo_errors_and_nulls():
    with pytest.raises(SourceError):
        sources.parse_yahoo_chart(b'{"chart":{"result":null,"error":{"code":"Not Found"}}}')
    with pytest.raises(SourceError):
        sources.parse_yahoo_chart(b"garbage")
    raw = (b'{"chart":{"result":[{"timestamp":[1733837400,1733923800],"indicators":{"quote":[{"open":[1,null],'
           b'"high":[2,null],"low":[0.5,null],"close":[1.5,null],"volume":[5,null]}],"adjclose":[{"adjclose":[1.5,null]}]}}]}}')
    df = sources.parse_yahoo_chart(raw)
    assert len(df) == 1 and df.attrs["dropped_null_rows"] == 1


def test_stooq_challenge_page_is_an_error_not_data():
    with pytest.raises(SourceError, match="blocked"):
        sources.parse_stooq_csv(fixture("stooq_SPY_response.html"))


def test_stooq_csv_format_synthetic():
    # The real Stooq answer is a bot-check page (fixture above), so this CSV is hand-written in Stooq's layout.
    raw = b"Date,Open,High,Low,Close,Volume\n2024-01-02,10,11,9,10.5,1000\n2024-01-03,10.5,12,10,11,2000\n"
    df = sources.parse_stooq_csv(raw)
    assert len(df) == 2 and df.index[1] == pd.Timestamp("2024-01-03") and df.close.iloc[0] == 10.5


def test_fred_csv():
    s = sources.parse_fred_csv(fixture("fred_DTB3.csv"))
    assert s.index.is_monotonic_increasing and s.dtype == "float64"
    assert s.loc["2026-08-31"] == 3.78
    assert s.isna().any()          # Labor Day (2026-09-07) is blank
    dotted = sources.parse_fred_csv(b"observation_date,DTB3\n2020-01-01,.\n2020-01-02,1.5\n")
    assert dotted.isna().tolist() == [True, False]
    with pytest.raises(SourceError):
        sources.parse_fred_csv(b"<html>")


def test_sgs_json():
    ptax = sources.parse_sgs_json(fixture("sgs_1.json"))
    cdi = sources.parse_sgs_json(fixture("sgs_12.json"))
    assert ptax.index[0] == pd.Timestamp("2026-09-01") and ptax.iloc[0] == 5.1570
    assert cdi.iloc[0] == pytest.approx(0.05166)
    assert not ptax.index.has_duplicates
    with pytest.raises(SourceError):
        sources.parse_sgs_json(b'{"error": "x"}')


def test_url_builders():
    assert sources.binance_kline_url("https://h/", "BTCUSDT", "2025-01") == \
        "https://h/data/spot/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-2025-01.zip"
    assert "daily/klines/ETHUSDT/1d/ETHUSDT-1d-2026-09-30.zip" in sources.binance_daily_kline_url("https://h", "ETHUSDT", "2026-09-30")


def test_http_get_retries_5xx_but_not_404():
    with FakeServer({"/ok": (200, b"hello")}, flaky={"/ok": 2}) as srv:
        assert sources.http_get(srv.url + "/ok") == b"hello"
        assert srv.hits.count("/ok") == 3
        with pytest.raises(SourceError) as e:
            sources.http_get(srv.url + "/missing")
        assert e.value.status == 404
        assert srv.hits.count("/missing") == 1


def test_http_get_refuses_non_http_and_gives_up():
    with pytest.raises(SourceError):
        sources.http_get("ftp://x/y")
    with FakeServer({"/bad": (500, b"x")}) as srv:
        with pytest.raises(SourceError) as e:
            sources.http_get(srv.url + "/bad", retries=2)
        assert e.value.status == 500 and srv.hits.count("/bad") == 3
