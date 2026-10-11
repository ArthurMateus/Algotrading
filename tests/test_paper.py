"""Forward paper runner: idempotence, crash resume, fill timing, stale halt, kill switch, refusal, replay == live.

Only the network is faked (tests/fakes.py loopback server); our own code runs for real. Every ledger lives in a
temp dir, never in the real data/paper/.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from algotrade import data, paper, sources
from algotrade.config import load_config
from algotrade.data import Bars
from algotrade.ledger import Ledger
from tests.fakes import FakeServer
from tests.synth import synth_frame

SYMS = ("BTCUSDT", "ETHUSDT")
D0 = dt.date(2024, 1, 1)           # first paper "today": the newest usable bar is 2023-12-31
SLIP_B = 0.0005


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(sources, "POLITE_DELAY", 0.0)
    monkeypatch.setattr(sources, "BACKOFF_BASE", 0.0)


def make_cfg(root: Path, url: str = "http://127.0.0.1:9"):
    cfg = load_config("B")
    return dataclasses.replace(cfg, data_dir=root / "data", reports_dir=root / "reports",
                               urls={k: url for k in cfg.urls})


def select(cfg, key: str = "TSMOM-63-weekly", name: str = "selected-B.json") -> None:
    Path(cfg.reports_dir).mkdir(parents=True, exist_ok=True)
    (Path(cfg.reports_dir) / name).write_text(json.dumps({"variant": key}), encoding="utf-8")


def frames(n: int = 420, start: str = "2023-01-01") -> dict[str, pd.DataFrame]:
    return {s: synth_frame(start, n, seed=7 + i, drift=0.004, vol=0.012) for i, s in enumerate(SYMS)}


def seed_cache(cfg, fr: dict[str, pd.DataFrame]) -> None:
    for s, f in fr.items():
        data._save_bars(cfg, Bars(s, "binance_vision", "none", f))


def setup(root: Path, fr=None, key="TSMOM-63-weekly"):
    cfg = make_cfg(root)
    seed_cache(cfg, fr if fr is not None else frames())
    select(cfg, key)
    return cfg


def ledger_path(cfg) -> Path:
    return paper.paper_dir(cfg) / "ledger.jsonl"


def events(cfg) -> list[dict]:
    return Ledger(ledger_path(cfg)).events()


def day(k: int) -> dt.date:
    return D0 + dt.timedelta(days=k)


def run(cfg, k: int):
    return paper.step(cfg, day(k), fetch=False)


def no_torn(s):
    return dataclasses.replace(s, torn_tail=False)


# ------------------------------------------------------------------ refusal

def test_refuses_without_a_selected_variant(tmp_path):
    cfg = make_cfg(tmp_path)
    seed_cache(cfg, frames())
    with pytest.raises(paper.PaperRefused, match="run the backtest first"):
        paper.paper_step("B", cfg=cfg, today=D0, fetch=False)
    assert not ledger_path(cfg).exists()


def test_reads_evaluate_is_selection_file_and_refuses_a_variant_switch(tmp_path):
    cfg = make_cfg(tmp_path)
    seed_cache(cfg, frames())
    select(cfg, "SMA-126-monthly", name="is_selection_B.json")
    r = paper.paper_step("B", cfg=cfg, today=D0, fetch=False)
    assert r.variant == "SMA-126-monthly" and events(cfg)[0]["variant"] == "SMA-126-monthly"
    select(cfg, "TSMOM-63-weekly")                       # selected-B.json takes precedence, and differs
    with pytest.raises(paper.PaperRefused, match="does not switch"):
        paper.paper_step("B", cfg=cfg, today=day(1), fetch=False)


def test_refuses_a_variant_outside_the_grid(tmp_path):
    cfg = setup(tmp_path, key="TSMOM-20-weekly")
    with pytest.raises(paper.PaperRefused, match="grid"):
        paper.paper_step("B", cfg=cfg, today=D0, fetch=False)


# ------------------------------------------------------------------ timing

def test_decision_at_close_fills_at_next_open(tmp_path):
    fr = frames()
    cfg = setup(tmp_path, fr)
    r0, _ = run(cfg, 0)
    ev = events(cfg)
    assert [e["type"] for e in ev] == ["genesis", "decision", "mark"]
    dec = ev[1]
    assert dec["date"] == "2023-12-31" and dec["reason"] == "inception"
    assert {o["kind"] for o in dec["orders"]} == {"entry"} and len(dec["orders"]) == 2
    assert r0.fills == 0 and r0.decisions == 1 and r0.equity == 300.0
    r1, st1 = run(cfg, 1)
    fills = [e for e in events(cfg) if e["type"] == "fill"]
    assert len(fills) == 2 and r1.fills == 2
    for f in fills:
        o = fr[f["symbol"]].loc["2024-01-01", "open"]
        assert f["date"] == "2024-01-01" and f["open_price"] == pytest.approx(o)
        assert f["price"] == pytest.approx(o * (1 + SLIP_B))
        assert f["commission"] == pytest.approx(0.001 * f["qty"] * f["price"])
    assert events(cfg)[-1] == {**events(cfg)[-1], "type": "mark", "date": "2024-01-01"}
    assert st1.pending is None and set(st1.positions) == set(SYMS) and st1.cash >= 0


def test_fill_ignores_a_shock_at_the_fill_bar_close(tmp_path):
    fr = frames()
    shocked = {s: f.copy() for s, f in fr.items()}
    for f in shocked.values():
        f.loc["2024-01-01", "close"] *= 0.5
    a, b = tmp_path / "a", tmp_path / "b"
    ca, cb = setup(a, fr), setup(b, shocked)
    for c in (ca, cb):
        run(c, 0)
        run(c, 1)
    fa = [e for e in events(ca) if e["type"] == "fill"]
    fb = [e for e in events(cb) if e["type"] == "fill"]
    assert fa == fb and fa


# ------------------------------------------------------------------ idempotence

def test_same_day_twice_is_one_set_of_events(tmp_path):
    cfg = setup(tmp_path)
    for k in range(0, 9):
        run(cfg, k)
        before = ledger_path(cfg).read_bytes()
        r, _ = run(cfg, k)
        assert r.new_events == 0 and r.fills == 0 and r.decisions == 0
        assert ledger_path(cfg).read_bytes() == before
    marks = [e["date"] for e in events(cfg) if e["type"] == "mark"]
    assert marks == sorted(set(marks)) and len(marks) == 9
    assert sum(e["type"] == "genesis" for e in events(cfg)) == 1


def test_missed_days_are_caught_up_exactly_like_daily_steps(tmp_path):
    a, b = setup(tmp_path / "a"), setup(tmp_path / "b")
    for k in range(0, 15):
        run(a, k)
    run(b, 0)
    run(b, 6)
    run(b, 14)
    assert ledger_path(a).read_bytes() == ledger_path(b).read_bytes()


# ------------------------------------------------------------------ crash safety

def _reference(root: Path, days: int):
    """Daily steps; returns (cfg, ledger lines, number of lines after each step)."""
    cfg = setup(root)
    counts = []
    for k in range(days):
        run(cfg, k)
        counts.append(len(ledger_path(cfg).read_bytes().splitlines()))
    return cfg, ledger_path(cfg).read_bytes().splitlines(keepends=True), counts


def test_resume_after_crash_between_intent_and_fill(tmp_path):
    ref_cfg, lines, counts = _reference(tmp_path / "ref", 10)
    evs = [json.loads(x) for x in lines]
    # the first scheduled decision after inception that has orders: cut right after it (intent durable, no fills)
    k = next(i for i, e in enumerate(evs) if e["type"] == "decision" and e["orders"])
    cfg = setup(tmp_path / "crash")
    ledger_path(cfg).parent.mkdir(parents=True, exist_ok=True)
    ledger_path(cfg).write_bytes(b"".join(lines[:k + 1]) + lines[k + 1][:7])      # + a torn half line
    s = next(i for i, c in enumerate(counts) if c > k)                             # the step that was running
    r, live = run(cfg, s)
    assert any("torn" in n for n in r.notes)
    assert no_torn(live) == Ledger(ledger_path(cfg)).replay()
    for j in range(s + 1, len(counts)):
        run(cfg, j)
    assert ledger_path(cfg).read_bytes() == b"".join(lines)
    fills_after = [e for e in events(cfg)[k + 1:] if e["type"] == "fill"]
    assert fills_after and fills_after[0]["date"] > evs[k]["date"]               # filled at a later open


def test_resume_from_every_cut_point_reproduces_the_uninterrupted_ledger(tmp_path):
    ref_cfg, lines, counts = _reference(tmp_path / "ref", 8)
    batch_cut = 0
    for k in range(1, len(lines)):
        evs = [json.loads(x) for x in lines[:k]]
        if evs[-1]["type"] == "fill" and json.loads(lines[k])["type"] == "fill":
            batch_cut += 1                                   # crash inside a fill batch
        root = tmp_path / f"cut{k}"
        cfg = setup(root)
        ledger_path(cfg).parent.mkdir(parents=True, exist_ok=True)
        ledger_path(cfg).write_bytes(b"".join(lines[:k]))
        s = next(i for i, c in enumerate(counts) if c >= k + 1)
        run(cfg, s)
        got = ledger_path(cfg).read_bytes().splitlines(keepends=True)
        assert got == lines[:counts[s]], f"cut after line {k}"
        shutil.rmtree(root)
    assert batch_cut >= 1


def test_a_tampered_partial_batch_is_refused_not_overwritten(tmp_path):
    ref_cfg, lines, counts = _reference(tmp_path / "ref", 3)
    evs = [json.loads(x) for x in lines]
    k = next(i for i, e in enumerate(evs) if e["type"] == "fill")
    bad = dict(evs[k], qty=evs[k]["qty"] * 2)
    cfg = setup(tmp_path / "t")
    ledger_path(cfg).parent.mkdir(parents=True, exist_ok=True)
    ledger_path(cfg).write_bytes(b"".join(lines[:k]) + (json.dumps(bad, sort_keys=True) + "\n").encode())
    before = ledger_path(cfg).read_bytes()
    with pytest.raises(paper.PaperError, match="do not match"):
        run(cfg, 1)
    assert ledger_path(cfg).read_bytes() == before


# ------------------------------------------------------------------ stale data

def test_stale_feed_never_starts_a_ledger(tmp_path):
    cfg = setup(tmp_path)                                  # newest bar 2024-02-24 (420 bars from 2023-01-01)
    r = paper.paper_step("B", cfg=cfg, today="2024-03-10", fetch=False)
    assert "stale" in r.halted and r.new_events == 0
    assert not ledger_path(cfg).exists()


def test_stale_feed_halts_new_decisions_but_keeps_the_book(tmp_path):
    fr = frames(n=372)                                     # bars end 2024-01-07
    cfg = setup(tmp_path, fr)
    for k in range(0, 8):
        run(cfg, k)
    n = len(events(cfg))
    r, _ = run(cfg, 10)                                    # no new bar for days: stale, nothing to do
    assert "stale" in r.halted and r.new_events == 0 and len(events(cfg)) == n
    assert Ledger(ledger_path(cfg)).replay().positions     # the book is kept, not liquidated
    log = (paper.paper_dir(cfg) / "paper.log").read_text(encoding="utf-8")
    assert "stale data" in log


def test_stale_latest_bar_gets_no_decision_and_is_taken_late_when_data_resumes(tmp_path):
    fr = frames(n=380)                                     # last bar 2024-01-15 (a Monday)
    cfg = setup(tmp_path, fr)
    run(cfg, 0)
    cut = {s: f.loc[:"2024-01-07"] for s, f in fr.items()}  # Sunday 2024-01-07 is a weekly decision date
    seed_cache(cfg, cut)
    r, _ = run(cfg, 12)                                    # today 2024-01-13: newest bar 01-07 is 6 days old
    assert "stale" in r.halted
    assert not [e for e in events(cfg) if e["type"] == "decision" and e["date"] == "2024-01-07"]
    assert [e for e in events(cfg) if e["type"] == "mark"][-1]["date"] == "2024-01-07"
    seed_cache(cfg, fr)
    r2, _ = run(cfg, 15)                                   # data resumes through 01-15
    assert r2.halted == ""
    late = [e for e in events(cfg) if e["type"] == "decision" and e["reason"].startswith("late:2024-01-07")]
    assert late and late[0]["date"] == "2024-01-08"


# ------------------------------------------------------------------ kill switch

def _crash_frames(crash_day: str = "2024-01-04") -> dict[str, pd.DataFrame]:
    out = {}
    for i, s in enumerate(SYMS):
        f = synth_frame("2023-01-01", 420, seed=11 + i, drift=0.003, vol=0.004)
        c = f["close"].to_numpy().copy()
        c[f.index >= pd.Timestamp(crash_day)] *= 0.3
        f["close"] = c
        f["open"] = np.concatenate([[c[0]], c[:-1]])
        f["high"] = np.maximum(f["open"], f["close"])
        f["low"] = np.minimum(f["open"], f["close"])
        out[s] = f
    return out


def test_kill_switch_exits_everything_and_blocks_entries(tmp_path):
    cfg = setup(tmp_path, _crash_frames())
    reports = [run(cfg, k)[0] for k in range(0, 12)]
    ev = events(cfg)
    kills = [e for e in ev if e["type"] == "kill"]
    assert len(kills) == 1 and kills[0]["date"] == "2024-01-04"
    assert kills[0]["equity"] <= 0.5 * 300.0
    kd = [e for e in ev if e["type"] == "decision" and e["date"] == "2024-01-04"]
    assert kd and kd[0]["reason"] == "kill_switch" and {o["kind"] for o in kd[0]["orders"]} == {"exit"}
    exits = [e for e in ev if e["type"] == "fill" and e["date"] == "2024-01-05"]
    assert {e["symbol"] for e in exits} == set(SYMS) and all(e["side"] == "sell" for e in exits)
    after = ev[ev.index(kills[0]):]
    assert not [e for e in after if e["type"] == "fill" and e["side"] == "buy"]
    assert not [e for e in after if e["type"] == "decision" and e["date"] > "2024-01-04"]
    final = Ledger(ledger_path(cfg)).replay()
    assert final.killed and final.positions == {}
    assert "kill switch" in reports[-1].halted


# ------------------------------------------------------------------ fetch through the (fake) network

def _daily_zip(sym: str, d: pd.Timestamp, row: pd.Series) -> bytes:
    ms = int(d.value // 10**6)
    line = f"{ms},{row.open},{row.high},{row.low},{row.close},{row.volume},{ms + 86399999},0,0,0,0,0\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{sym}-1d-{d.date()}.csv", line)
    return buf.getvalue()


def test_step_fetches_new_public_bars_incrementally(tmp_path):
    fr = frames()
    with FakeServer({}) as srv:
        cfg = make_cfg(tmp_path, srv.url)
        seed_cache(cfg, {s: f.loc[:"2023-12-31"] for s, f in fr.items()})
        select(cfg)
        r0 = paper.paper_step("B", cfg=cfg, today="2024-01-01")
        assert r0.as_of == "2023-12-31"
        for s, f in fr.items():
            for d in f.loc["2024-01-01":"2024-01-03"].index:
                srv.routes[f"/data/spot/daily/klines/{s}/1d/{s}-1d-{d.date()}.zip"] = (200, _daily_zip(s, d, f.loc[d]))
        r1 = paper.paper_step("B", cfg=cfg, today="2024-01-03")
        assert r1.as_of == "2024-01-02" and r1.fills == 2 and r1.halted == ""
        assert all("/api/v3/order" not in h and "?" not in h for h in srv.hits)   # plain public GETs only
    fills = [e for e in events(cfg) if e["type"] == "fill"]
    assert {f["date"] for f in fills} == {"2024-01-01"}
    for f in fills:
        assert f["open_price"] == pytest.approx(fr[f["symbol"]].loc["2024-01-01", "open"])


def test_fetch_failure_falls_back_to_cache_and_is_noted(tmp_path):
    with FakeServer({"/": (500, b"server error")}) as srv:
        cfg = make_cfg(tmp_path, srv.url)
        seed_cache(cfg, {s: f.loc[:"2023-12-31"] for s, f in frames().items()})
        select(cfg)
        r = paper.paper_step("B", cfg=cfg, today=D0)
    assert any("fetch failed" in n for n in r.notes) and r.new_events == 3 and r.halted == ""


# ------------------------------------------------------------------ replayed state == live state

_REF: dict[int, bytes] = {}
MAX_DAY = 20


def _reference_ledgers() -> dict[int, bytes]:
    if not _REF:
        cfg = setup(Path(tempfile.mkdtemp(prefix="paper_ref_")))
        for k in range(MAX_DAY + 1):
            run(cfg, k)
            _REF[k] = ledger_path(cfg).read_bytes()
    return _REF


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(st.tuples(st.integers(0, 3), st.integers(0, 6), st.integers(0, 40)), min_size=1, max_size=7))
def test_replayed_state_equals_live_state_across_random_step_sequences(plan):
    """Random day jumps (0 = same day again), random crashes (drop the last `drop` lines, maybe a torn tail).
    After every step the live state equals a fresh replay; at the end the ledger equals the daily reference."""
    ref = _reference_ledgers()
    with tempfile.TemporaryDirectory() as tmp:
        cfg = setup(Path(tmp))
        k = 0
        run(cfg, k)
        for jump, drop, torn in plan:
            k = min(k + jump, MAX_DAY)
            r, live = run(cfg, k)
            assert no_torn(live) == Ledger(ledger_path(cfg)).replay()
            lines = ledger_path(cfg).read_bytes().splitlines(keepends=True)
            keep = max(1, len(lines) - drop)                        # genesis always survives
            tail = lines[keep][: torn % max(1, len(lines[keep]) - 1)] if keep < len(lines) and torn else b""
            ledger_path(cfg).write_bytes(b"".join(lines[:keep]) + tail)
        r, live = run(cfg, k)
        assert no_torn(live) == Ledger(ledger_path(cfg)).replay()
        assert ledger_path(cfg).read_bytes() == ref[k]
