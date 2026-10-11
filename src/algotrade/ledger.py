"""Crash-safe append-only JSONL ledger and the state fold. Used by the forward paper runner; the backtest
writes the same events to an in-memory ledger so replay can be tested.

Owner: risk-engineer. One JSON object per line, UTF-8, `\n`, flush + fsync after every append. Every event has a
`type` and the keys below (extra keys are kept and ignored by the fold):
  genesis  {market, start_equity, config_sha256}      first event, exactly once; cash = start_equity
  decision {date, variant, targets}                   targets: {symbol: weight}; becomes State.pending
  fill     {symbol, side, kind, qty, price, open_price, commission, regulatory, slippage_cost, date}  (broker.Fill)
  skip     {symbol, kind, reason, date}               (broker.Skip)
  settle   {date, decision_date}                      the pending decision has been executed (or dropped)
  kill     {date, equity}                             sticky kill switch
  mark     {date, equity}                             equity at the close
A torn last line (crash mid-write: bytes after the last `\n`) is ignored on replay and reported
(`State.torn_tail`, `Ledger.torn_bytes`); the next append cuts it off first. Any other bad line is an error.

Protocol (event sourcing): `ledger.append(ev)` (durable), then `state.apply(ev)`. A restart's `replay()` folds the
same lines through the same `apply`, so the replayed state equals the live state up to the last durable line.
Stdlib only.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path

REQUIRED: dict[str, tuple[str, ...]] = {
    "genesis": ("market", "start_equity", "config_sha256"),
    "decision": ("date", "variant", "targets"),
    "fill": ("symbol", "side", "kind", "qty", "price", "open_price", "commission", "regulatory", "slippage_cost",
             "date"),
    "skip": ("symbol", "kind", "reason", "date"),
    "settle": ("date", "decision_date"),
    "kill": ("date", "equity"),
    "mark": ("date", "equity"),
}
_QTY_EPS = 1e-12           # a position at or below this is flat
_SHORT_TOL = 1e-9          # relative over-sell tolerated as float noise (then clamped to flat)


class LedgerError(ValueError):
    """A malformed event, an event that breaks a state invariant, or a corrupt (non-tail) ledger line."""


def to_event(type_: str, obj=None, **extra) -> dict:
    """Build an event dict from a dataclass (broker.Fill / broker.Skip) and/or keyword fields."""
    ev: dict = {"type": type_}
    if obj is not None:
        if not is_dataclass(obj):
            raise LedgerError(f"to_event: {type(obj).__name__} is not a dataclass")
        ev.update(asdict(obj))
    ev.update(extra)
    return ev


def _encode(event: dict) -> bytes:
    if not isinstance(event, dict):
        raise LedgerError(f"event must be a dict, got {type(event).__name__}")
    t = event.get("type")
    if t not in REQUIRED:
        raise LedgerError(f"unknown event type {t!r}")
    missing = [k for k in REQUIRED[t] if k not in event]
    if missing:
        raise LedgerError(f"{t} event missing {missing}")
    try:
        text = json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=True)
    except (TypeError, ValueError) as e:
        raise LedgerError(f"{t} event is not JSON-serialisable: {e}") from e
    return (text + "\n").encode("utf-8")


def _num(ev: dict, key: str) -> float:
    v = ev[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise LedgerError(f"{ev.get('type')}.{key} must be a finite number, got {v!r}")
    return float(v)


@dataclass
class State:
    cash: float = 0.0
    positions: dict[str, float] = field(default_factory=dict)
    last_decision_date: str = ""
    pending: dict | None = None          # decision taken at a close, not yet filled at the next open
    killed: bool = False
    torn_tail: bool = False
    # bookkeeping (beyond the skeleton): identity of the run and the latest mark
    market: str = ""
    start_equity: float = 0.0
    config_sha256: str = ""
    last_mark_date: str = ""
    last_equity: float = 0.0
    kill_date: str = ""
    n_events: int = 0
    n_fills: int = 0
    n_skips: int = 0

    def apply(self, event: dict) -> None:
        """Fold one event into the state (pure apart from mutating self). Raises LedgerError on a malformed
        event or one that breaks an invariant (event before genesis, second genesis, a sell beyond the held
        quantity)."""
        if not isinstance(event, dict):
            raise LedgerError(f"event must be a dict, got {type(event).__name__}")
        t = event.get("type")
        if t not in REQUIRED:
            raise LedgerError(f"unknown event type {t!r}")
        missing = [k for k in REQUIRED[t] if k not in event]
        if missing:
            raise LedgerError(f"{t} event missing {missing}")
        if t == "genesis":
            if self.n_events:
                raise LedgerError("genesis must be the first and only genesis event")
            se = _num(event, "start_equity")
            if se <= 0:
                raise LedgerError(f"genesis.start_equity must be > 0, got {se}")
            self.market, self.config_sha256 = str(event["market"]), str(event["config_sha256"])
            self.start_equity = self.cash = self.last_equity = se
        elif not self.n_events:
            raise LedgerError(f"{t} event before genesis")
        elif t == "decision":
            if not isinstance(event["targets"], dict):
                raise LedgerError("decision.targets must be an object {symbol: weight}")
            self.last_decision_date = str(event["date"])
            self.pending = json.loads(json.dumps(event, sort_keys=True))   # same form live and replayed
        elif t == "fill":
            self._fill(event)
        elif t == "skip":
            self.n_skips += 1
        elif t == "settle":
            self.pending = None
        elif t == "kill":
            self.killed = True
            self.kill_date = str(event["date"])
        elif t == "mark":
            self.last_equity = _num(event, "equity")
            self.last_mark_date = str(event["date"])
        self.n_events += 1

    def _fill(self, ev: dict) -> None:
        sym, side = str(ev["symbol"]), ev["side"]
        qty, price = _num(ev, "qty"), _num(ev, "price")
        fees = _num(ev, "commission") + _num(ev, "regulatory")
        if qty <= 0 or price <= 0:
            raise LedgerError(f"fill {sym}: qty and price must be > 0, got {qty}, {price}")
        held = self.positions.get(sym, 0.0)
        if side == "buy":
            self.cash -= qty * price + fees
            self.positions[sym] = held + qty
        elif side == "sell":
            if qty > held * (1 + _SHORT_TOL) + _QTY_EPS:
                raise LedgerError(f"fill {sym}: sell {qty} exceeds held {held} (no shorts)")
            self.cash += qty * price - fees
            left = held - qty
            if left <= max(_QTY_EPS, held * _SHORT_TOL):
                self.positions.pop(sym, None)
            else:
                self.positions[sym] = left
        else:
            raise LedgerError(f"fill {sym}: side must be buy or sell, got {side!r}")
        self.n_fills += 1

    def equity(self, prices: dict[str, float]) -> float:
        """Cash + positions valued at `prices` (KeyError if a held symbol has no price)."""
        return self.cash + sum(q * prices[s] for s, q in self.positions.items())


class Ledger:
    def __init__(self, path: Path | None) -> None:
        """path=None keeps events in memory only (backtest)."""
        self.path = Path(path) if path is not None else None
        self._lines: list[bytes] = []            # memory mode only
        self._fh = None
        self.torn_bytes = 0                      # size of the torn tail found by the last read

    # ---- writing ---------------------------------------------------------------------------------------------
    def append(self, event: dict) -> None:
        """Write one event durably (fsync), then nothing else; the caller applies it to State."""
        line = _encode(event)
        if self.path is None:
            self._lines.append(line)
            return
        if self._fh is None:
            self._open_for_append()
        self._fh.write(line)
        self._fh.flush()
        os.fsync(self._fh.fileno())

    def _open_for_append(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raw = self.path.read_bytes()
            tail = len(raw) - (raw.rfind(b"\n") + 1)
            if tail:                              # cut a torn last line so the new line starts clean
                with open(self.path, "r+b") as f:
                    f.truncate(len(raw) - tail)
                    f.flush()
                    os.fsync(f.fileno())
        self._fh = open(self.path, "ab")

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> "Ledger":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- reading ---------------------------------------------------------------------------------------------
    def _complete_lines(self) -> list[bytes]:
        if self.path is None:
            self.torn_bytes = 0
            return list(self._lines)
        if not self.path.exists():
            self.torn_bytes = 0
            return []
        raw = self.path.read_bytes()
        parts = raw.split(b"\n")
        tail = parts.pop()                        # bytes after the last newline: non-empty only if torn
        self.torn_bytes = len(tail)
        return parts

    def events(self) -> list[dict]:
        out = []
        for i, line in enumerate(self._complete_lines(), 1):
            try:
                ev = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as e:
                raise LedgerError(f"{self.path or '<memory>'}: line {i} is corrupt: {e}") from e
            if not isinstance(ev, dict):
                raise LedgerError(f"{self.path or '<memory>'}: line {i} is not a JSON object")
            out.append(ev)
        return out

    def replay(self) -> State:
        """Rebuild State from the file, tolerating a torn last line."""
        st = State()
        for i, ev in enumerate(self.events(), 1):
            try:
                st.apply(ev)
            except LedgerError as e:
                raise LedgerError(f"{self.path or '<memory>'}: line {i}: {e}") from e
        st.torn_tail = self.torn_bytes > 0
        return st
