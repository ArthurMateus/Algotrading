"""Ledger: append-only JSONL with fsync, torn-tail tolerant replay, replayed state == live state (docs/SPEC.md §5)."""
from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from algotrade.broker import Fill, Skip
from algotrade.ledger import Ledger, LedgerError, State, to_event

GENESIS = {"type": "genesis", "market": "B", "start_equity": 300.0, "config_sha256": "ab" * 32}


def fill(sym="BTCUSDT", side="buy", qty=0.5, price=100.1, date="2024-01-03", kind="entry", com=0.05, reg=0.0):
    return to_event("fill", Fill(symbol=sym, side=side, kind=kind, qty=qty, price=price, open_price=100.0,
                                 commission=com, regulatory=reg, slippage_cost=qty * 0.1, date=date))


def script() -> list[dict]:
    return [
        GENESIS,
        {"type": "decision", "date": "2024-01-02", "variant": "TSMOM-63-weekly", "targets": {"BTCUSDT": 0.4,
                                                                                            "ETHUSDT": 0.0}},
        fill(),
        to_event("skip", Skip(symbol="ETHUSDT", kind="entry", reason="below_min_order", date="2024-01-03")),
        {"type": "settle", "date": "2024-01-03", "decision_date": "2024-01-02"},
        {"type": "mark", "date": "2024-01-03", "equity": 299.9},
        fill(side="sell", qty=0.2, price=99.9, date="2024-01-10", kind="rebalance"),
        {"type": "kill", "date": "2024-01-11", "equity": 140.0},
    ]


def run_live(ledger: Ledger, events: list[dict]) -> State:
    st_ = State()
    for ev in events:
        ledger.append(ev)
        st_.apply(ev)
    return st_


def test_fold_by_hand(tmp_path):
    live = run_live(Ledger(tmp_path / "l.jsonl"), script())
    assert live.cash == pytest.approx(300.0 - (0.5 * 100.1 + 0.05) + (0.2 * 99.9 - 0.05))
    assert live.positions == {"BTCUSDT": pytest.approx(0.3)}
    assert live.pending is None and live.last_decision_date == "2024-01-02"
    assert live.killed and live.kill_date == "2024-01-11"
    assert (live.last_mark_date, live.last_equity) == ("2024-01-03", 299.9)
    assert (live.n_events, live.n_fills, live.n_skips) == (8, 2, 1)
    assert (live.market, live.start_equity) == ("B", 300.0)


def test_replay_equals_live_file_and_memory(tmp_path):
    led = Ledger(tmp_path / "sub" / "l.jsonl")
    live = run_live(led, script())
    led.close()
    replayed = Ledger(tmp_path / "sub" / "l.jsonl").replay()
    assert replayed == live and not replayed.torn_tail
    mem = Ledger(None)
    assert run_live(mem, script()) == mem.replay() == live
    assert mem.events() == Ledger(tmp_path / "sub" / "l.jsonl").events()


def test_file_format_one_json_object_per_line(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    run_live(led, script())
    led.close()
    raw = (tmp_path / "l.jsonl").read_bytes()
    assert raw.endswith(b"\n") and b"\r" not in raw
    lines = raw.decode("utf-8").splitlines()
    assert len(lines) == len(script())
    assert [json.loads(x)["type"] for x in lines] == [e["type"] for e in script()]


def test_every_append_is_fsynced(tmp_path, monkeypatch):
    calls = []
    real = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (calls.append(fd), real(fd))[1])
    led = Ledger(tmp_path / "l.jsonl")
    run_live(led, script()[:3])
    led.close()
    assert len(calls) == 3


def test_append_only_reopen_appends(tmp_path):
    p = tmp_path / "l.jsonl"
    with Ledger(p) as a:
        run_live(a, script()[:4])
    with Ledger(p) as b:
        for ev in script()[4:]:
            b.append(ev)
    assert Ledger(p).replay() == run_live(Ledger(None), script())


def test_torn_last_line_is_ignored_reported_and_repaired(tmp_path):
    p = tmp_path / "l.jsonl"
    with Ledger(p) as led:
        live = run_live(led, script()[:5])
    whole = p.read_bytes()
    nxt = json.dumps(script()[5]).encode()
    p.write_bytes(whole + nxt[: len(nxt) // 2])               # crash mid-write
    led2 = Ledger(p)
    rep = led2.replay()
    assert rep.torn_tail and led2.torn_bytes == len(nxt) // 2
    rep.torn_tail = False
    assert rep == live
    # the next append cuts the torn bytes first, so the file stays valid
    led2.append(script()[5])
    live.apply(script()[5])
    led2.close()
    assert p.read_bytes().startswith(whole) and p.read_bytes().count(b"\n") == 6
    again = Ledger(p).replay()
    assert not again.torn_tail and again == live


def test_complete_json_without_newline_is_still_torn(tmp_path):
    """The append was not acknowledged (no newline fsynced), so the caller never applied it."""
    p = tmp_path / "l.jsonl"
    with Ledger(p) as led:
        live = run_live(led, script()[:2])
    p.write_bytes(p.read_bytes() + json.dumps(script()[2]).encode())
    rep = Ledger(p).replay()
    assert rep.torn_tail and rep.n_events == 2 and rep.positions == {} == live.positions


def test_corrupt_middle_line_is_an_error(tmp_path):
    p = tmp_path / "l.jsonl"
    with Ledger(p) as led:
        run_live(led, script()[:3])
    lines = p.read_bytes().split(b"\n")
    lines[1] = lines[1][:10]
    p.write_bytes(b"\n".join(lines))
    with pytest.raises(LedgerError, match="line 2"):
        Ledger(p).replay()
    p.write_bytes(b"[1,2]\n")
    with pytest.raises(LedgerError, match="not a JSON object"):
        Ledger(p).replay()


def test_missing_file_replays_empty(tmp_path):
    led = Ledger(tmp_path / "none.jsonl")
    assert led.replay() == State() and led.events() == []


@pytest.mark.parametrize("bad", [
    {"type": "nope", "date": "x"},
    {"type": "mark", "date": "2024-01-03"},                                     # missing equity
    {"type": "mark", "date": "2024-01-03", "equity": math.nan},                 # NaN is not JSON
    {"type": "mark", "date": "2024-01-03", "equity": object()},
    ["not", "a", "dict"],
])
def test_bad_events_are_refused_before_writing(tmp_path, bad):
    p = tmp_path / "l.jsonl"
    led = Ledger(p)
    led.append(GENESIS)
    with pytest.raises(LedgerError):
        led.append(bad)
    led.close()
    assert len(Ledger(p).events()) == 1


def test_fold_invariants():
    s = State()
    with pytest.raises(LedgerError, match="before genesis"):
        s.apply({"type": "mark", "date": "d", "equity": 1.0})
    s.apply(GENESIS)
    with pytest.raises(LedgerError, match="genesis"):
        s.apply(GENESIS)
    with pytest.raises(LedgerError, match="no shorts"):
        s.apply(fill(side="sell", qty=0.1))
    s.apply(fill(qty=0.5))
    with pytest.raises(LedgerError, match="no shorts"):
        s.apply(fill(side="sell", qty=0.51))
    s.apply(fill(side="sell", qty=0.5 * (1 + 1e-12)))          # float noise: clamps to flat
    assert s.positions == {}
    for bad in (fill(qty=-1.0), fill(price=0.0), fill(side="short"), {**fill(), "qty": "1"}):
        with pytest.raises(LedgerError):
            s.apply(bad)
    with pytest.raises(LedgerError, match="targets"):
        s.apply({"type": "decision", "date": "d", "variant": "v", "targets": [0.5]})
    with pytest.raises(LedgerError):
        State().apply({"type": "genesis", "market": "A", "start_equity": 0.0, "config_sha256": ""})


def test_state_equity_and_kill_is_sticky():
    s = State()
    for ev in script():
        s.apply(ev)
    assert s.equity({"BTCUSDT": 200.0}) == pytest.approx(s.cash + 0.3 * 200.0)
    s.apply({"type": "mark", "date": "2024-02-01", "equity": 1000.0})
    assert s.killed                                           # recovery does not un-kill


# ---- property: random event streams, crash at any byte --------------------------------------------------------

@st.composite
def event_streams(draw):
    """A valid stream: genesis, then decisions / fills that never oversell / skips / settles / marks / kill."""
    evs = [{"type": "genesis", "market": draw(st.sampled_from(["A", "B"])),
            "start_equity": draw(st.floats(1.0, 1e6)), "config_sha256": "0" * 64}]
    held: dict[str, float] = {}
    syms = ["SPY", "GLD", "BTCUSDT"]
    num = st.floats(1e-6, 1e4, allow_nan=False, allow_infinity=False)
    for i in range(draw(st.integers(0, 40))):
        date = f"2024-{1 + i // 28:02d}-{1 + i % 28:02d}"
        kind = draw(st.sampled_from(["decision", "buy", "sell", "skip", "settle", "mark", "kill"]))
        sym = draw(st.sampled_from(syms))
        if kind == "decision":
            evs.append({"type": "decision", "date": date, "variant": "SMA-126-monthly",
                        "targets": draw(st.dictionaries(st.sampled_from(syms), st.floats(0, 1)))})
        elif kind == "buy" or (kind == "sell" and not held.get(sym)):
            q = draw(num)
            held[sym] = held.get(sym, 0.0) + q
            evs.append(fill(sym, "buy", q, draw(num), date, com=draw(st.floats(0, 5)), reg=0.0))
        elif kind == "sell":
            q = held[sym] * draw(st.floats(0.01, 1.0))
            left = held[sym] - q
            if left <= max(1e-12, held[sym] * 1e-9):
                held.pop(sym)
            else:
                held[sym] = left
            evs.append(fill(sym, "sell", q, draw(num), date, "exit", com=draw(st.floats(0, 5)),
                            reg=draw(st.floats(0, 1))))
        elif kind == "skip":
            evs.append({"type": "skip", "symbol": sym, "kind": "entry", "reason": "risk_gate:stale_data",
                        "date": date})
        elif kind == "settle":
            evs.append({"type": "settle", "date": date, "decision_date": date})
        elif kind == "mark":
            evs.append({"type": "mark", "date": date, "equity": draw(st.floats(0, 1e6))})
        else:
            evs.append({"type": "kill", "date": date, "equity": draw(st.floats(0, 1e6))})
    return evs


@given(evs=event_streams(), cut=st.floats(0.0, 1.0))
@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_property_replay_equals_live_and_crash_at_any_byte(evs, cut):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "l.jsonl"
        led = Ledger(p)
        lives = [State()]                                     # live state after k events, k = 0..n
        live = State()
        for ev in evs:
            led.append(ev)
            live.apply(ev)
            snap = State()
            for e in evs[: len(lives)]:
                snap.apply(e)
            lives.append(snap)
        led.close()
        assert Ledger(p).replay() == live
        # crash: keep only a prefix of the bytes; replay equals the live state after the last complete line
        raw = p.read_bytes()
        n = int(len(raw) * cut)
        p.write_bytes(raw[:n])
        k = raw[:n].count(b"\n")
        rep = Ledger(p).replay()
        assert rep.torn_tail == (n > 0 and raw[n - 1:n] != b"\n")
        rep.torn_tail = False
        assert rep == lives[k]
