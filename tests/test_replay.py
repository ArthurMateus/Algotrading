"""Deterministic replay and backtest-vs-paper agreement. Only the network is faked (here: not even that, the paper
cache is seeded); our own code runs for real. Everything lives in temp dirs; nothing touches data/ or reports/."""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
from dataclasses import fields
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from algotrade import data, engine, paper, strategy
from algotrade.broker import Fill
from algotrade.config import load_config
from algotrade.data import Bars, build_panel
from algotrade.ledger import Ledger
from tests.synth import synth_frame, synth_market

SYMS = ("BTCUSDT", "ETHUSDT")
D0 = dt.date(2024, 1, 1)                       # first paper "today"; the first usable bar is 2023-12-31
FILL_FIELDS = [f.name for f in fields(Fill)]


# ------------------------------------------------------------------ helpers

def _cfg(root: Path):
    return dataclasses.replace(load_config("B"), data_dir=root / "data", reports_dir=root / "reports")


def _frames(n: int = 420, drift: float = 0.004, vol: float = 0.012):
    return {s: synth_frame("2023-01-01", n, seed=7 + i, drift=drift, vol=vol) for i, s in enumerate(SYMS)}


def _paper_setup(root: Path, key: str, frames):
    cfg = _cfg(root)
    for s, f in frames.items():
        data._save_bars(cfg, Bars(s, "binance_vision", "none", f))
    Path(cfg.reports_dir).mkdir(parents=True, exist_ok=True)
    (Path(cfg.reports_dir) / "selected-B.json").write_text(json.dumps({"variant": key}), encoding="utf-8")
    return cfg


def _engine_run(cfg, frames, key: str, start: str, end: str, cost_mult: float = 1.0):
    panel = build_panel({s: Bars(s, "binance_vision", "none", f) for s, f in frames.items()}, end)
    v = strategy.Variant(*key.split("-")[:1], int(key.split("-")[1]), key.split("-")[2])
    tg = strategy.target_weights(panel, v, cfg)
    dd = strategy.decision_dates(panel.close.index, v.rebalance)
    return engine.run(panel, tg, dd, cfg, start=start, end=end, cost_mult=cost_mult, label=key)


def _paper_fills(cfg) -> list[dict]:
    return [e for e in Ledger(paper.paper_dir(cfg) / "ledger.jsonl").events() if e["type"] == "fill"]


def _drive_paper(cfg, days: int):
    for k in range(days):
        paper.step(cfg, D0 + dt.timedelta(days=k), fetch=False)


# ------------------------------------------------------------------ determinism

@pytest.mark.parametrize("key", ["TSMOM-63-weekly", "SMA-126-monthly"])
def test_same_inputs_give_identical_fills_equity_and_metrics(key):
    from algotrade import metrics as M
    cfg = load_config("B")
    out = []
    for _ in range(2):
        market = synth_market(list(cfg.instruments), "2019-01-01", 700, seed=21)     # regenerated each run
        panel = build_panel(market, "2030-01-01")
        v = strategy.Variant(*key.split("-")[:1], int(key.split("-")[1]), key.split("-")[2])
        tg = strategy.target_weights(panel, v, cfg)
        dd = strategy.decision_dates(panel.close.index, v.rebalance)
        res = engine.run(panel, tg, dd, cfg, start="2019-09-15", end="2020-11-30", label=key)
        rf = pd.Series(0.0001, index=res.returns.index)
        out.append((res, M.sharpe(res.returns, rf, cfg.periods_per_year), M.max_drawdown(res.equity)))
    (a, sa, da), (b, sb, db) = out
    assert a.fills and a.fills == b.fills and a.skips == b.skips
    pd.testing.assert_series_equal(a.equity, b.equity)
    pd.testing.assert_frame_equal(a.weights, b.weights)
    assert a.ledger.events() == b.ledger.events()
    assert (sa == sb or (np.isnan(sa) and np.isnan(sb))) and da == db


def test_paper_ledger_is_identical_across_two_independent_runs(tmp_path):
    ledgers = []
    for name in ("one", "two"):
        cfg = _paper_setup(tmp_path / name, "TSMOM-63-weekly", _frames())
        _drive_paper(cfg, 30)
        ledgers.append((paper.paper_dir(cfg) / "ledger.jsonl").read_bytes())
    assert ledgers[0] == ledgers[1] and b'"fill"' in ledgers[0]


# ------------------------------------------------------------------ backtest vs paper

@pytest.mark.parametrize("key,days", [("TSMOM-63-weekly", 45), ("SMA-126-monthly", 70)])
def test_backtest_and_paper_make_the_same_fills(tmp_path, key, days):
    frames = _frames()
    cfg = _paper_setup(tmp_path, key, frames)
    _drive_paper(cfg, days)
    pf = _paper_fills(cfg)
    assert pf, "the scenario must trade or the comparison is vacuous"
    start = "2023-12-31"
    end = (D0 + dt.timedelta(days=days - 1) - dt.timedelta(days=1)).isoformat()    # newest bar paper has seen
    res = _engine_run(cfg, frames, key, start, end)
    ef = [{k: getattr(f, k) for k in FILL_FIELDS} for f in res.fills]
    got = [{k: e[k] for k in FILL_FIELDS} for e in pf]
    assert len(ef) == len(got)
    for a, b in zip(ef, got):
        assert (a["date"], a["symbol"], a["side"], a["kind"]) == (b["date"], b["symbol"], b["side"], b["kind"])
        for k in ("qty", "price", "open_price", "commission", "regulatory", "slippage_cost"):
            assert a[k] == pytest.approx(b[k], rel=1e-9, abs=1e-12), (a["date"], a["symbol"], k)
    # equity curves agree bar by bar
    marks = {e["date"]: e["equity"] for e in Ledger(paper.paper_dir(cfg) / "ledger.jsonl").events()
             if e["type"] == "mark"}
    for ts, eq in res.equity.items():
        assert marks[ts.date().isoformat()] == pytest.approx(eq, rel=1e-9)


def test_backtest_and_paper_agree_after_a_kill_switch(tmp_path):
    """A crash that trips the kill switch must exit identically in both."""
    frames = _frames(drift=0.004, vol=0.001)
    for f in frames.values():
        f.loc["2024-01-10":, ["open", "high", "low", "close"]] *= 0.3       # -70% from Jan 10
    key = "TSMOM-63-weekly"
    cfg = _paper_setup(tmp_path, key, frames)
    _drive_paper(cfg, 30)
    pf = _paper_fills(cfg)
    assert any(e["type"] == "kill" for e in Ledger(paper.paper_dir(cfg) / "ledger.jsonl").events())
    res = _engine_run(cfg, frames, key, "2023-12-31", (D0 + dt.timedelta(days=28)).isoformat())
    assert res.killed_on and any(f.side == "sell" for f in res.fills)
    assert [(f.date, f.symbol, f.side) for f in res.fills] == [(e["date"], e["symbol"], e["side"]) for e in pf]
    for f, e in zip(res.fills, pf):
        assert f.qty == pytest.approx(e["qty"], rel=1e-9) and f.price == pytest.approx(e["price"], rel=1e-9)
