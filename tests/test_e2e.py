"""CLI end to end on synthetic data in temp dirs: fetch (loopback fake server) -> backtest IS -> backtest OOS ->
second OOS refused -> forced rerun logged -> status. `algotrade.config.load_config` is redirected so the real data/
and reports/ are never read or written (the safety fixture below fails the test if they change)."""
from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from algotrade import cli, config, data, sources
from algotrade.variants import oos_runs, runs
from tests.fakes import FakeServer, fixture
from tests.synth import synth_frame

ROOT = Path(__file__).resolve().parent.parent
SYMS = ("BTCUSDT", "ETHUSDT")
START, END = dt.date(2024, 1, 1), dt.date(2025, 6, 30)


def _tree_digest(p: Path) -> str:
    h = hashlib.sha256()
    if p.exists():
        for f in sorted(x for x in p.rglob("*") if x.is_file()):
            h.update(str(f.relative_to(p)).encode())
            h.update(str(f.stat().st_size).encode())
            h.update(str(f.stat().st_mtime_ns).encode())
    return h.hexdigest()


def _month_zip(frame, y: int, m: int) -> bytes:
    sub = frame[(frame.index.year == y) & (frame.index.month == m)]
    rows = []
    for ts, r in sub.iterrows():
        ms = int(ts.value // 10**6)
        rows.append(f"{ms},{r.open},{r.high},{r.low},{r.close},{r.volume},{ms + 86399999},0,0,0,0,0")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"x-1d-{y}-{m:02d}.csv", "\n".join(rows) + "\n")
    return buf.getvalue()


def _routes() -> dict[str, tuple[int, bytes]]:
    n = (END - START).days + 1
    routes = {"/graph/fredgraph.csv": (200, fixture("fred_DTB3.csv")),
              "/dados/serie/bcdata.sgs.1/": (200, fixture("sgs_1.json")),
              "/dados/serie/bcdata.sgs.12/": (200, fixture("sgs_12.json")),
              "/api/v3/exchangeInfo": (200, fixture("binance_exchangeInfo.json"))}
    for i, s in enumerate(SYMS):
        fr = synth_frame(START.isoformat(), n, seed=40 + i, drift=0.002, vol=0.015)
        y, m = START.year, START.month
        while (y, m) <= (END.year, END.month):
            routes[f"/data/spot/monthly/klines/{s}/1d/{s}-1d-{y:04d}-{m:02d}.zip"] = (200, _month_zip(fr, y, m))
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return routes


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Temp data/reports dirs + fake server; every load_config call inside the package returns the temp config."""
    real_data, real_reports = ROOT / "data", ROOT / "reports"
    before = (_tree_digest(real_data), _tree_digest(real_reports))
    monkeypatch.setattr(sources, "POLITE_DELAY", 0.0)
    monkeypatch.setattr(sources, "BACKOFF_BASE", 0.0)
    monkeypatch.setattr(data, "BINANCE_FIRST_MONTH", "2024-01")
    real_load = config.load_config
    with FakeServer(_routes()) as srv:
        def patched(market, *a, **k):
            cfg = real_load(market, *a, **k)
            return dataclasses.replace(
                cfg, data_dir=tmp_path / "data", reports_dir=tmp_path / "reports",
                urls={u: srv.url for u in cfg.urls}, end_date=END.isoformat(), warmup_bars=30, vol_window=10)
                # the real grid (63/126/252): run_is refuses any key outside variants.PREREGISTERED_KEYS
        monkeypatch.setattr(config, "load_config", patched)
        yield tmp_path, srv
    assert (_tree_digest(real_data), _tree_digest(real_reports)) == before, "the real data/ or reports/ changed"


def test_full_cli_flow(world, capsys):
    tmp, srv = world
    reports = tmp / "reports"

    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "no cached data" in out and "OOS: not run" in out and "variants used 0/12" in out

    assert cli.main(["fetch", "--market", "B"]) == 0
    out = capsys.readouterr().out
    assert "BTCUSDT" in out and "ETHUSDT" in out and "binance_vision" in out
    assert (tmp / "data" / "bars" / "B" / "BTCUSDT.parquet").exists()
    assert (tmp / "data" / "bars" / "B" / "manifest.json").exists()
    assert (tmp / "data" / "aux" / "manifest.json").exists()
    assert any("/api/v3/exchangeInfo" in h for h in srv.hits)

    # OOS before IS: refused (no selection), nothing logged
    assert cli.main(["backtest", "--market", "B", "--split", "oos"]) == 1
    assert "refused" in capsys.readouterr().out and oos_runs(reports, "B") == []

    assert cli.main(["backtest", "--market", "B", "--split", "is"]) == 0
    out = capsys.readouterr().out
    assert "selected" in out and "6." in out and "7." in out
    sel = json.loads((reports / "is_selection_B.json").read_text(encoding="utf-8"))
    chosen = json.loads((reports / "selected-B.json").read_text(encoding="utf-8"))
    assert chosen["variant"] == sel["selected"]["key"]
    is_md = (reports / "backtest-B-is.md").read_text(encoding="utf-8")
    assert is_md.isascii() and "| 6 |" in is_md
    assert len(runs(reports, "B")) == 13 and (reports / "variants.md").exists()
    assert oos_runs(reports, "B") == []

    assert cli.main(["backtest", "--market", "B", "--split", "oos"]) == 0
    out = capsys.readouterr().out
    assert "OOS" in out and ("PASS" in out or "FAIL" in out)
    for n in range(1, 9):
        assert f"  {n}. " in out
    oos_md = (reports / "backtest-B-oos.md").read_text(encoding="utf-8")
    assert all(f"| {n} | " in oos_md for n in range(1, 9)) and "FORCED" not in oos_md
    assert len(oos_runs(reports, "B")) == 1

    # second OOS: refused, exit 1, report untouched, nothing new logged
    n_runs = len(runs(reports, "B"))
    assert cli.main(["backtest", "--market", "B", "--split", "oos"]) == 1
    assert "refused" in capsys.readouterr().out
    assert (reports / "backtest-B-oos.md").read_text(encoding="utf-8") == oos_md
    assert len(oos_runs(reports, "B")) == 1 and len(runs(reports, "B")) == n_runs

    # --force without a reason: bad arguments (2), still one OOS use
    assert cli.main(["backtest", "--market", "B", "--split", "oos", "--force"]) == 2
    assert len(oos_runs(reports, "B")) == 1
    # no re-selection after OOS
    assert cli.main(["backtest", "--market", "B", "--split", "is"]) == 1

    assert cli.main(["backtest", "--market", "B", "--split", "oos", "--force", "--reason", "e2e test rerun"]) == 0
    out = capsys.readouterr().out
    assert "FORCED RERUN" in out
    forced = oos_runs(reports, "B")
    assert len(forced) == 2 and forced[1]["forced"] is True and forced[1]["reason"] == "e2e test rerun"
    assert "FORCED OOS RERUN #2" in (reports / "backtest-B-oos.md").read_text(encoding="utf-8")

    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "[B] variants used 12/12" in out and f"IS selection: {sel['selected']['key']}" in out
    assert "OOS: run 2 time(s)" in out and "BTCUSDT" in out


def test_backtest_without_fetch_is_refused_not_crashing(world, capsys):
    assert cli.main(["backtest", "--market", "B", "--split", "is"]) == 1
    assert "refused or failed" in capsys.readouterr().out
    assert cli.main(["paper", "--market", "B"]) == 1                 # no selection: paper never picks a variant
    assert "refused" in capsys.readouterr().out


def test_bad_cli_arguments_exit_2():
    assert cli.main([]) == 2
    assert cli.main(["backtest", "--market", "A"]) == 2
    assert cli.main(["nonsense"]) == 2
