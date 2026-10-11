"""Forward paper runner (phase 6). Simulated fills only; no venue, no account, no keys, no order endpoint.

Owner: risk-engineer. Run once a day (`uv run algotrade paper --market B`); every step is idempotent and
crash-safe. State lives ONLY in the append-only ledger `data/paper/<market>/ledger.jsonl` (ledger.py: fsync per
line, torn last line ignored). A human-readable `paper.log` next to it gets one line per step (not state).

One step:
  1. Refuse unless evaluate wrote a selected variant (`reports/selected-<m>.json`, else
     `reports/is_selection_<m>.json`): paper never chooses a variant. The variant is pinned in the genesis event;
     a different selection later is refused (no switching mid-run).
  2. Fetch the newest public bars (keyless, read-only, `data.fetch_market(cfg, end_date=today-1)`; only bars dated
     before today's UTC date are used, so an unfinished session is never read). A failed fetch is noted and the
     cache is used; the stale-data check below then decides.
  3. Replay the ledger. Process, in order, every bar D with D >= start_date and D > last mark:
       a. OPEN of D: if a decision is pending (taken at an earlier close), its recorded orders go through the risk
          gate (RiskGate.screen, sells first) and the PaperBroker at D's open with the pre-registered base costs
          (cost_mult 1). Events: skip/fill ..., then `settle`. Orders for a symbol with no bar on D are skipped
          (`no_bar`); an exit skipped that way is re-issued at D's close (retried at the next open).
       b. CLOSE of D: value the book at the last known closes. If equity <= kill_loss_fraction x start, append the
          sticky `kill` event. Then, if a decision is due, append ONE `decision` event (the intent: targets and the
          classified orders). Due = inception (the first paper bar), a schedule date
          (`strategy.decision_dates` with the next bar known, or expected for the newest bar), a schedule date that
          was missed (late), a retried exit, or (killed) any held position (exit everything).
       c. `mark` {date, equity, cash, positions}: the bar is done.
  4. Stale feed: if the newest real bar is older than `stale_after_days` (calendar days, vs today's UTC date), no
     strategy decision is taken on it (exits still are), the step reports `halted`, and the log says so. A new
     ledger is never started on stale data.

Idempotence: everything is keyed on bar dates already in the ledger (last mark, last decision, pending, killed),
so re-running the same day appends nothing. Crash safety: the decision (intent) is durable before any fill; a
crash inside a fill batch is resumed by recomputing the batch from the state before it, checking that the durable
prefix matches, and appending only the rest. A file lock stops two steps running at once.

Decision rules mirror docs/SPEC.md §3-5 and the engine docstring: classification at the decision close with
close-t weights (target>0 & flat = entry; target==0 & held = exit; else a rebalance only if |target - w| >= band;
NaN target = hold). `classify_orders`, `fill_batch` and `book_value` are pure helpers meant to be shared with
engine.py. pandas/numpy are imported inside functions only (tests/test_safety.py imports every module).
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from algotrade.ledger import Ledger, LedgerError, State, to_event

if TYPE_CHECKING:
    from algotrade.broker import PaperBroker
    from algotrade.config import MarketConfig
    from algotrade.data import Panel
    from algotrade.risk import RiskGate
    from algotrade.strategy import Variant

# Files evaluate.py may write, tried in order (the first one found wins). Paper never picks a variant itself.
SELECTED_FILES = ("selected-{m}.json", "is_selection_{m}.json")
_QTY_EPS = 1e-12


class PaperRefused(RuntimeError):
    """The step refused to run (no selected variant, variant changed, no data, another step running)."""


class PaperError(RuntimeError):
    """The ledger disagrees with a deterministic recomputation (needs a human look; nothing was written)."""


@dataclass(frozen=True)
class StepReport:
    market: str
    as_of: str                     # newest bar date used ("" if none)
    equity: float                  # equity at the last mark
    fills: int                     # fills appended by this step
    decisions: int                 # decisions appended by this step
    halted: str                    # "" or the reason (stale data, kill switch)
    # additive fields
    variant: str = ""
    new_events: int = 0
    notes: tuple[str, ...] = ()


# ---------------------------------------------------------------- selected variant

def selected_variant(cfg: "MarketConfig") -> "Variant":
    """The variant chosen by evaluate (IS selection). Raises PaperRefused if none was written."""
    from algotrade.strategy import Variant, grid

    paths = [Path(cfg.reports_dir) / f.format(m=cfg.name) for f in SELECTED_FILES]
    path = next((p for p in paths if p.exists()), None)
    if path is None:
        raise PaperRefused(
            f"no selected variant for market {cfg.name} (looked for {', '.join(p.name for p in paths)} in "
            f"{cfg.reports_dir}). Paper never chooses a variant: run the backtest first "
            f"(uv run algotrade backtest --market {cfg.name} --split is).")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise PaperRefused(f"{path.name} is not valid JSON: {e}") from e
    raw = doc
    if isinstance(doc, dict):
        for k in ("selected", "variant", "selected_variant"):
            if k in doc:
                raw = doc[k]
                break
    try:
        if isinstance(raw, dict) and {"signal", "lookback", "rebalance"} <= set(raw):
            v = Variant(raw["signal"], int(raw["lookback"]), raw["rebalance"])
        elif isinstance(raw, dict) and isinstance(raw.get("key"), str):
            sig, lb, reb = raw["key"].split("-")
            v = Variant(sig, int(lb), reb)  # type: ignore[arg-type]
        elif isinstance(raw, str):
            sig, lb, reb = raw.split("-")
            v = Variant(sig, int(lb), reb)  # type: ignore[arg-type]
        else:
            raise ValueError("no variant field")
    except (ValueError, TypeError) as e:
        raise PaperRefused(f"{path.name}: cannot read the selected variant ({e})") from e
    if v not in grid(cfg):
        raise PaperRefused(f"{path.name}: variant {v.key} is not in the pre-registered grid")
    return v


# ---------------------------------------------------------------- pure helpers (shareable with engine.py)

def _finite(x) -> bool:
    try:
        return x is not None and math.isfinite(x)
    except TypeError:
        return False


def book_value(cash: float, positions: dict[str, float], prices: dict[str, float]) -> float:
    """cash + sum(qty * price). Raises if a held symbol has no finite price."""
    eq = float(cash)
    for s, q in positions.items():
        p = prices.get(s)
        if not (_finite(p) and p > 0):
            raise PaperError(f"no price to value the held position in {s}")
        eq += q * p
    return eq


def classify_orders(targets: dict[str, float], positions: dict[str, float], closes: dict[str, float],
                    equity: float, band: float, symbols: list[str]) -> list[dict]:
    """Orders decided at a close (SPEC §4, engine docstring). `targets` holds only decided symbols (absent = hold).
    target>0 & flat -> buy entry; target<=0 & held -> sell exit; else a rebalance if |target - w| >= band."""
    out = []
    for s in symbols:
        t = targets.get(s)
        if not _finite(t):
            continue
        held = positions.get(s, 0.0)
        is_held = held > _QTY_EPS
        if t > 0 and not is_held:
            if equity > 0:
                out.append({"symbol": s, "side": "buy", "kind": "entry", "target_weight": float(t)})
        elif t <= 0 and is_held:
            out.append({"symbol": s, "side": "sell", "kind": "exit", "target_weight": 0.0})
        elif t > 0 and is_held and equity > 0:
            w = held * closes[s] / equity
            if abs(t - w) >= band:
                out.append({"symbol": s, "side": "buy" if t > w else "sell", "kind": "rebalance",
                            "target_weight": float(t)})
    return out


def fill_batch(gate: "RiskGate", broker: "PaperBroker", state: State, orders: list[dict], decision_date: str,
               fill_date: str, opens: dict[str, float], marks: dict[str, float],
               last_bar_date: dict[str, str]) -> list[dict]:
    """Ledger events (skip/fill, no settle) for executing `orders` at the open of `fill_date`. Pure.

    Orders without a bar -> Skip no_bar. The rest go to PaperBroker.execute (sells first, buys scaled pro rata to
    the cash); every quantity the broker would trade is then screened by RiskGate.screen (sells first, projected
    cash/positions). Refused orders become Skip "risk_gate:<rule>" and the broker is re-run without them, until
    every executed fill is one the gate allowed with exactly that quantity (the set only shrinks, so this ends)."""
    from algotrade.broker import Order, Skip
    from algotrade.risk import GateView

    cash, pos = float(state.cash), dict(state.positions)
    equity_open = broker.equity_at_open(cash, pos, opens, marks)
    no_bar: list[dict] = []
    allowed: list[Order] = []
    for od in orders:
        o = Order(symbol=od["symbol"], side=od["side"], kind=od["kind"], target_weight=float(od["target_weight"]),
                  decision_date=decision_date, fill_date=fill_date)
        p = opens.get(o.symbol)
        if not (_finite(p) and p > 0):
            no_bar.append(to_event("skip", Skip(o.symbol, o.kind, "no_bar", fill_date)))
        else:
            allowed.append(o)
    prices = {**{s: marks[s] for s in pos if s in marks}, **opens}
    view = GateView(date=fill_date, equity=equity_open, start_equity=state.start_equity, cash=cash, positions=pos,
                    prices=prices, last_bar_date=dict(last_bar_date), killed=state.killed)
    refused: list[dict] = []
    while True:
        fills, skips = broker.execute(allowed, opens, cash, pos, marks)
        qty = {f.symbol: f.qty for f in fills}
        verdicts = gate.screen([(o, qty[o.symbol]) for o in allowed if o.symbol in qty], view)
        bad = {o.symbol: v for o, _q, v in verdicts if not v.allowed or abs(v.qty - qty[o.symbol]) > 1e-12 * max(1.0, v.qty)}
        if not bad:
            break
        for o in allowed:
            if o.symbol in bad:
                rule = bad[o.symbol].rule or "qty_mismatch"
                refused.append(to_event("skip", Skip(o.symbol, o.kind, f"risk_gate:{rule}", fill_date)))
        allowed = [o for o in allowed if o.symbol not in bad]
    return no_bar + refused + [to_event("fill", f) for f in fills] + [to_event("skip", s) for s in skips]


# ---------------------------------------------------------------- plumbing

def paper_dir(cfg: "MarketConfig") -> Path:
    return Path(cfg.data_dir) / "paper" / cfg.name


def _as_date(today) -> dt.date:
    if today is None:
        return dt.datetime.now(dt.timezone.utc).date()
    if isinstance(today, dt.datetime):
        return today.date()
    if isinstance(today, dt.date):
        return today
    return dt.date.fromisoformat(str(today)[:10])


def _norm(ev: dict) -> dict:
    """The form an event has after a ledger round trip (for comparisons)."""
    return json.loads(json.dumps(ev, sort_keys=True))


@contextmanager
def _lock(path: Path):
    """Non-blocking exclusive lock, released by the OS if the process dies (so a crash never blocks a resume)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "a+b")
    locked = False
    try:
        try:
            if os.name == "nt":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as e:
            raise PaperRefused(f"another paper step for this market is running ({path})") from e
        yield
    finally:
        if locked:
            try:
                if os.name == "nt":
                    import msvcrt
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        fh.close()


def _expected_next(cfg: "MarketConfig", last: dt.date) -> dt.date:
    """Next bar date from the calendar: every UTC day (B) or the next weekday (A; US holidays are not known, a
    decision missed because of one is taken late at the next close)."""
    nxt = last + dt.timedelta(days=1)
    if "binance_vision" not in cfg.sources:
        while nxt.weekday() >= 5:
            nxt += dt.timedelta(days=1)
    return nxt


def format_report(r: StepReport) -> str:
    lines = [f"[{r.market}] paper step: variant {r.variant}, newest bar {r.as_of or 'none'}, equity "
             f"{r.equity:.2f} USD, +{r.new_events} ledger events ({r.decisions} decisions, {r.fills} fills)"]
    if r.halted:
        lines.append(f"[{r.market}] HALTED: {r.halted}")
    lines += [f"[{r.market}] note: {n}" for n in r.notes]
    return "\n".join(lines)


def _log(pdir: Path, r: StepReport) -> None:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = (f"{stamp} as_of={r.as_of} equity={r.equity:.4f} new_events={r.new_events} decisions={r.decisions} "
            f"fills={r.fills} halted={r.halted!r} notes={list(r.notes)!r}\n")
    with open(pdir / "paper.log", "a", encoding="utf-8") as fh:
        fh.write(line)


# ---------------------------------------------------------------- the step

def paper_step(market: str, *, cfg: "MarketConfig | None" = None, today=None, fetch: bool = True) -> StepReport:
    """One idempotent forward paper step for `market` ("A" or "B"). `cfg`/`today`/`fetch` exist for tests."""
    return step(cfg if cfg is not None else _load_cfg(market), today, fetch=fetch)[0]


def _load_cfg(market: str) -> "MarketConfig":
    from algotrade.config import load_config
    return load_config(market)


def step(cfg: "MarketConfig", today=None, *, fetch: bool = True) -> tuple[StepReport, State]:
    """paper_step, also returning the live State (tests compare it with a fresh replay)."""
    from algotrade import data

    today_d = _as_date(today)
    variant = selected_variant(cfg)
    notes: list[str] = []
    last_complete = (today_d - dt.timedelta(days=1)).isoformat()
    if fetch:
        try:
            data.fetch_market(cfg, end_date=last_complete)
        except Exception as e:  # network/source failure: keep the cache, the stale check decides
            notes.append(f"fetch failed, using the cached bars: {type(e).__name__}: {e}"[:300])
    try:
        bars = data.load_bars(cfg)
        panel = data.build_panel(bars, last_complete)
    except (data.DataError, IndexError, ValueError) as e:
        raise PaperRefused(f"no usable bars for market {cfg.name}: {e}") from e
    pdir = paper_dir(cfg)
    with _lock(pdir / "ledger.lock"):
        ledger = Ledger(pdir / "ledger.jsonl")
        try:
            report, state = _advance(cfg, variant, panel, today_d, ledger, notes)
        finally:
            ledger.close()
    _log(pdir, report)
    return report, state


def _advance(cfg: "MarketConfig", variant: "Variant", panel: "Panel", today: dt.date, ledger: Ledger,
             notes: list[str]) -> tuple[StepReport, State]:
    import pandas as pd

    from algotrade import data
    from algotrade.broker import CostModel, PaperBroker
    from algotrade.risk import GateView, RiskGate
    from algotrade.strategy import decision_dates, target_weights

    events = ledger.events()
    state = State()
    for i, ev in enumerate(events, 1):
        try:
            state.apply(ev)
        except LedgerError as e:
            raise PaperError(f"{ledger.path}: line {i}: {e}") from e
    if ledger.torn_bytes:
        notes.append(f"ignored a torn last ledger line ({ledger.torn_bytes} bytes, crash mid-write); resuming")

    genesis = events[0] if events else None
    if genesis is not None:
        if genesis.get("market") != cfg.name:
            raise PaperRefused(f"{ledger.path} belongs to market {genesis.get('market')!r}, not {cfg.name}")
        if genesis.get("variant") != variant.key:
            raise PaperRefused(f"the ledger trades {genesis.get('variant')} but the selected variant is now "
                               f"{variant.key}; paper does not switch variants mid-run (start a new ledger "
                               f"directory deliberately if this is intended)")

    syms = list(cfg.instruments)
    valid = panel.valid[syms]
    index = panel.close.index
    has_bar = valid.any(axis=1)
    if not bool(has_bar.any()):
        raise PaperRefused(f"no bars before {today} for market {cfg.name}")
    latest_ts = index[has_bar.to_numpy()][-1]
    latest = latest_ts.date().isoformat()
    age = (today - latest_ts.date()).days
    stale = age > cfg.stale_after_days
    halted = ""
    if stale:
        halted = (f"stale data: newest bar {latest} is {age} days old (limit {cfg.stale_after_days}); "
                  f"no new strategy decision on it")

    new: list[dict] = []

    def emit(ev: dict) -> None:
        ledger.append(ev)                 # durable first (fsync), then folded into the live state
        state.apply(ev)
        events.append(ev)
        new.append(ev)

    def report() -> tuple[StepReport, State]:
        h = halted
        if state.killed:
            h = (h + "; " if h else "") + f"kill switch fired on {state.kill_date} (sticky: exits only)"
        return (StepReport(cfg.name, latest, float(state.last_equity), sum(e["type"] == "fill" for e in new),
                           sum(e["type"] == "decision" for e in new), h, variant.key, len(new), tuple(notes)),
                state)

    if genesis is None:
        if stale:
            notes.append("no paper ledger started on stale data")
            return report()
        emit({"type": "genesis", "market": cfg.name, "start_equity": float(cfg.start_equity_usd),
              "config_sha256": cfg.criteria_sha256, "variant": variant.key, "start_date": latest,
              "cost_mult": 1.0})
        genesis = new[0]
    start = str(genesis["start_date"])

    # Panel views (only bars before today, closes forward-filled for valuation, last real bar date per symbol).
    close_ff = panel.close[syms].ffill()
    bar_dates = pd.DataFrame({s: pd.Series(index.where(valid[s].to_numpy()), index=index) for s in syms}).ffill()
    targets_df = target_weights(panel, variant, cfg)
    sched = {d.date().isoformat() for d in decision_dates(index, variant.rebalance)}
    # The newest bar is a decision date only if the expected next bar starts a new week/month.
    nxt = pd.Timestamp(_expected_next(cfg, index[-1].date()))
    last_is_sched = index[-1] in decision_dates(index, variant.rebalance, next_bar=nxt)
    gate = RiskGate(cfg, cost_mult=1.0)
    broker = PaperBroker(CostModel.from_config(cfg.costs, 1.0), data.min_order_usd(cfg), data.lot_step(cfg))

    def prices_at(i: int) -> dict[str, float]:
        row = close_ff.iloc[i]
        return {s: float(row[s]) for s in syms if _finite(row[s])}

    def last_bars_at(i: int) -> dict[str, str]:
        row = bar_dates.iloc[i]
        return {s: row[s].date().isoformat() for s in syms if not pd.isna(row[s])}

    for i, ts in enumerate(index):
        ds = ts.date().isoformat()
        if ds < start or (state.last_mark_date and ds <= state.last_mark_date):
            continue
        is_last = i == len(index) - 1

        # ---- a. open of D: execute the pending decision -------------------------------------------------------
        if state.pending is not None and str(state.pending["date"]) < ds:
            pend = state.pending
            if "orders" not in pend:
                raise PaperError(f"pending decision {pend['date']} has no recorded orders")
            n_tail = 0
            while n_tail < len(events) and events[len(events) - 1 - n_tail]["type"] in ("fill", "skip"):
                n_tail += 1
            base = state
            if n_tail:                     # a crash inside a fill batch: recompute it from the state before it
                base = State()
                for ev in events[:len(events) - n_tail]:
                    base.apply(ev)
            opens = {s: float(panel.open.at[ts, s]) for s in syms if bool(valid.at[ts, s])}
            marks = prices_at(i - 1) if i > 0 else {}
            batch = fill_batch(gate, broker, base, pend["orders"], str(pend["date"]), ds, opens, marks,
                               last_bars_at(i))
            done = [_norm(e) for e in events[len(events) - n_tail:]]
            if done != [_norm(e) for e in batch[:n_tail]]:
                raise PaperError(f"the durable fill events for {ds} do not match a recomputation (data revised?); "
                                 f"inspect {ledger.path} by hand")
            if n_tail:
                notes.append(f"resumed a fill batch interrupted after {n_tail} events on {ds}")
            for ev in batch[n_tail:]:
                emit(ev)
            emit({"type": "settle", "date": ds, "decision_date": str(pend["date"])})

        # ---- b. close of D: kill switch, decision ------------------------------------------------------------
        closes = prices_at(i)
        equity = book_value(state.cash, state.positions, closes)
        view = GateView(date=ds, equity=equity, start_equity=state.start_equity, cash=state.cash,
                        positions=dict(state.positions), prices=closes, last_bar_date=last_bars_at(i),
                        killed=state.killed)
        if not state.killed and gate.kill_triggered(view):
            emit({"type": "kill", "date": ds, "equity": equity})
        if state.last_decision_date != ds:
            held = {s for s, q in state.positions.items() if q > _QTY_EPS}
            retry = sorted({e["symbol"] for e in events if e["type"] == "skip" and e.get("date") == ds
                            and e.get("kind") == "exit" and e.get("reason") == "no_bar"} & held)
            tg: dict[str, float] = {}
            reasons: list[str] = []
            if state.killed:
                if held:
                    tg = {s: 0.0 for s in sorted(held)}
                    reasons.append("kill_switch")
            else:
                hold_off = stale and is_last
                due = ds == start or ds in sched or (is_last and last_is_sched)
                late = sorted(d for d in sched if state.last_decision_date < d < ds and d >= start)
                if hold_off and (due or late):
                    notes.append(f"decision due at {ds} not taken: stale data")
                elif due or late:
                    row = targets_df.loc[ts]
                    tg = {s: float(row[s]) for s in syms if _finite(row[s])}
                    reasons.append("inception" if ds == start else ("schedule" if due else f"late:{late[-1]}"))
                    if late and not due:
                        notes.append(f"decision for {late[-1]} taken late at the {ds} close")
                for s in retry:
                    if s not in tg:
                        tg[s] = 0.0
                        reasons.append(f"retry_exit:{s}")
            if reasons:
                orders = classify_orders(tg, state.positions, closes, equity, cfg.rebalance_band, syms)
                emit({"type": "decision", "date": ds, "variant": variant.key, "targets": tg, "orders": orders,
                      "reason": ",".join(reasons), "equity": equity})

        # ---- c. mark ----------------------------------------------------------------------------------------------
        emit({"type": "mark", "date": ds, "equity": equity, "cash": float(state.cash),
              "positions": {s: float(q) for s, q in sorted(state.positions.items())}})
    return report()
