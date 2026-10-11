"""Bar-by-bar backtest loop: decide at close t, gate, fill at open t+1 through the paper broker, mark at close.

Owner: backtest-engineer. The backtest and the forward paper runner (paper.py) share the same decision and fill
code (`paper.classify_orders`, `paper.book_value`, `engine.fill_batch`) and the same per-bar protocol, so the same
bars give the same fills in both.

Every window starts flat with start equity (cash) at its first bar. Inception: the first decision is taken at the
close of the window's first bar and filled at the second bar's open (SPEC 11.2); after that, decisions follow
`decisions` (from `strategy.decision_dates`). A decision on the window's last bar has no fill bar inside the window
and is not taken.

Per bar D:
  a. OPEN: the pending decision's orders are executed by `fill_batch` (risk gate + paper broker) at D's open.
     Events: skip/fill ..., then `settle`. Orders for a symbol with no bar on D -> Skip("no_bar").
  b. CLOSE: book valued at the last known closes. If equity <= kill_loss_fraction x start, the sticky `kill` event
     is written. Then a decision is taken if due: killed -> exit every held position (no strategy decision ever
     again); else a schedule date (or inception) -> the strategy targets (NaN = hold); plus, for a held symbol whose
     exit was skipped for lack of a bar today, an exit is re-issued (retried at the next open). Classification
     (`paper.classify_orders`) uses close-t weights: entry, exit, or a rebalance only if |target - w| >= band
     (cfg.rebalance_band = 2%; the benchmark passes 0). Entries and exits always trade.
  c. `mark` {date, equity}.
All events go through an in-memory `ledger.Ledger` and are folded into a `ledger.State`, the single source of truth
for cash and positions, so replaying the ledger reproduces the engine state exactly.
pandas is imported inside functions only (tests/test_safety.py).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, fields
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

    from algotrade.broker import Fill, PaperBroker, Skip
    from algotrade.config import MarketConfig
    from algotrade.data import Panel
    from algotrade.ledger import Ledger, State
    from algotrade.risk import RiskGate

_QTY_EPS = 1e-12           # a position at or below this is flat (same as ledger/risk)
_CAP_HAIRCUT = 1e-9        # relative haircut on the cap clamp so float noise never trips the gate


@dataclass(frozen=True)
class RunResult:
    equity: "pd.Series"            # daily equity at close (USD), indexed by panel date over the window
    returns: "pd.Series"           # simple daily returns of equity (first bar = 0)
    weights: "pd.DataFrame"        # held weight per symbol at each close
    fills: list["Fill"]
    skips: list["Skip"]
    ledger: "Ledger"
    cost_mult: float
    killed_on: str = ""            # date (close) the kill switch fired ("" if never)

    @property
    def below_min_exits(self) -> int:
        """Exits sold in full although below the venue minimum (SPEC 11.3; real venues may refuse these)."""
        return sum(1 for f in self.fills if f.below_min)


def _finite(x) -> bool:
    try:
        return x is not None and math.isfinite(x)
    except TypeError:
        return False


def _iso(ts) -> str:
    return ts.date().isoformat()


# ---------------------------------------------------------------------------------------------------- fill batch

def _clamp_to_gate_cap(gate: "RiskGate", broker: "PaperBroker", orders: list, opens: dict[str, float],
                       cash: float, pos: dict[str, float], equity_open: float) -> list:
    """Buys whose target is within the 1/N cap are clamped to the base the gate measures the cap against.

    RiskGate.screen projects the batch (sells first) and measures the cap on min(equity at open, projected cash +
    positions at the open), which is lower than the equity at open by the costs of the earlier orders of the batch.
    A target of exactly 1/N (the benchmark; any sleeve whose vol is below sigma*) would then be refused outright.
    The clamp uses an upper bound of every order's cost, so the clamped buy passes; it trims a buy by at most the
    batch's costs (conservative). A target ABOVE the cap is left alone so the gate refuses it."""
    from dataclasses import replace
    if equity_open <= 0:
        return orders
    costs = 0.0
    for o in orders:
        p, h = opens[o.symbol], pos.get(o.symbol, 0.0)
        q = broker.planned_qty(o, p, equity_open, h)
        if q <= 0:
            continue
        if o.side == "sell":
            costs += q * p - gate.sell_proceeds(q, p)
        else:
            costs += gate.buy_cost(q, p) - q * p
    w_max = gate.instrument_cap * (equity_open - max(costs, 0.0)) / equity_open * (1.0 - _CAP_HAIRCUT)
    out = []
    for o in orders:
        if o.side == "buy" and w_max < o.target_weight <= gate.instrument_cap * (1 + 1e-12):
            o = replace(o, target_weight=w_max)
        out.append(o)
    return out


def fill_batch(gate: "RiskGate", broker: "PaperBroker", state: "State", orders: list[dict], decision_date: str,
               fill_date: str, opens: dict[str, float], marks: dict[str, float],
               last_bar_date: dict[str, str]) -> list[dict]:
    """Ledger events (skip/fill, no settle) for executing `orders` at the open of `fill_date`. Pure.
    Shared by the backtest engine and the paper runner (paper.py imports it from here).

    Orders without a bar -> Skip no_bar. Buys within the 1/N cap are clamped to the gate's cap base
    (`_clamp_to_gate_cap`). The rest go to PaperBroker.execute (sells first, buys scaled pro rata to the cash);
    every quantity the broker would trade is then screened by RiskGate.screen (sells first, projected
    cash/positions). Refused orders become Skip "risk_gate:<rule>" and the broker is re-run without them, until
    every executed fill is one the gate allowed with exactly that quantity (the set only shrinks, so this ends)."""
    from algotrade.broker import Order, Skip
    from algotrade.ledger import to_event
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
    allowed = _clamp_to_gate_cap(gate, broker, allowed, opens, cash, pos, equity_open)
    prices = {**{s: marks[s] for s in pos if s in marks}, **opens}
    view = GateView(date=fill_date, equity=equity_open, start_equity=state.start_equity, cash=cash, positions=pos,
                    prices=prices, last_bar_date=dict(last_bar_date), killed=state.killed)
    refused: list[dict] = []
    while True:
        fills, skips = broker.execute(allowed, opens, cash, pos, marks)
        qty = {f.symbol: f.qty for f in fills}
        verdicts = gate.screen([(o, qty[o.symbol]) for o in allowed if o.symbol in qty], view)
        bad = {o.symbol: v for o, _q, v in verdicts
               if not v.allowed or abs(v.qty - qty[o.symbol]) > 1e-12 * max(1.0, v.qty)}
        if not bad:
            break
        for o in allowed:
            if o.symbol in bad:
                rule = bad[o.symbol].rule or "qty_mismatch"
                refused.append(to_event("skip", Skip(o.symbol, o.kind, f"risk_gate:{rule}", fill_date)))
        allowed = [o for o in allowed if o.symbol not in bad]
    return no_bar + refused + [to_event("fill", f) for f in fills] + [to_event("skip", s) for s in skips]


# ---------------------------------------------------------------------------------------------------- the loop

def run(panel: "Panel", targets: "pd.DataFrame", decisions: "pd.DatetimeIndex", cfg: "MarketConfig", *,
        start: str, end: str, cost_mult: float = 1.0, band: float | None = None,
        min_order: dict[str, float] | None = None, lot: dict[str, float] | None = None,
        label: str = "") -> RunResult:
    """Simulate one window [start, end] inclusive. `band=None` uses cfg.rebalance_band; the benchmark passes 0.0.

    Additive keywords: `min_order` / `lot` (per-symbol minimum notional and lot step; default
    `data.min_order_usd(cfg)` / `data.lot_step(cfg)`), `label` (variant key written to the ledger)."""
    import numpy as np
    import pandas as pd

    from algotrade.broker import CostModel, Fill, PaperBroker, Skip
    from algotrade.ledger import Ledger, State
    from algotrade.paper import book_value, classify_orders
    from algotrade.risk import GateView, RiskGate

    if not (isinstance(cost_mult, (int, float)) and math.isfinite(cost_mult) and cost_mult > 0):
        raise ValueError(f"cost_mult must be > 0, got {cost_mult!r}")
    band = float(cfg.rebalance_band if band is None else band)
    if min_order is None or lot is None:
        from algotrade import data
        min_order = data.min_order_usd(cfg) if min_order is None else min_order
        lot = data.lot_step(cfg) if lot is None else lot

    syms = list(targets.columns)
    missing = [s for s in syms if s not in panel.close.columns]
    if missing:
        raise ValueError(f"panel lacks symbols {missing}")
    idx = pd.DatetimeIndex(panel.close.index)
    t0, t1 = pd.Timestamp(start), pd.Timestamp(end)
    in_win = (idx >= t0) & (idx <= t1)
    win = idx[in_win]
    if len(win) == 0:
        raise ValueError(f"no bars in window {start}..{end}")

    opens = panel.open.loc[win, syms].to_numpy(dtype="float64")
    closes = panel.close.loc[win, syms].to_numpy(dtype="float64")
    valid = panel.valid.loc[win, syms].to_numpy(dtype=bool)
    tg = targets.reindex(index=win, columns=syms).to_numpy(dtype="float64")
    dec_set = set(pd.DatetimeIndex(decisions))
    is_dec = np.array([d in dec_set for d in win], dtype=bool)
    is_dec[0] = True                                   # SPEC 11.2: first decision at the window's first close

    # Known before the window opens (no look-ahead): the latest real bar of each symbol before `start`.
    last_bar_date: dict[str, str] = {}
    last_price: dict[str, float] = {}
    before = idx < t0
    if before.any():
        hv = panel.valid.loc[before, syms]
        hc = panel.close.loc[before, syms]
        for s in syms:
            v = hv[s].to_numpy(dtype=bool)
            if v.any():
                k = int(np.flatnonzero(v)[-1])
                last_bar_date[s] = _iso(hv.index[k])
                last_price[s] = float(hc[s].iloc[k])

    broker = PaperBroker(CostModel.from_config(cfg.costs, cost_mult), min_order, lot)
    gate = RiskGate(cfg, cost_mult=cost_mult)
    ledger = Ledger(None)
    state = State()
    fill_names = [f.name for f in fields(Fill)]
    skip_names = [f.name for f in fields(Skip)]
    all_fills: list = []
    all_skips: list = []

    def emit(ev: dict) -> None:
        ledger.append(ev)
        state.apply(ev)
        if ev["type"] == "fill":
            all_fills.append(Fill(**{k: ev[k] for k in fill_names}))
        elif ev["type"] == "skip":
            all_skips.append(Skip(**{k: ev[k] for k in skip_names}))

    emit({"type": "genesis", "market": cfg.name, "start_equity": float(cfg.start_equity_usd),
          "config_sha256": cfg.criteria_sha256, "variant": label, "cost_mult": float(cost_mult),
          "start_date": _iso(win[0]), "end_date": _iso(win[-1])})

    killed_on = ""
    eq_out = np.empty(len(win))
    w_out = np.zeros((len(win), len(syms)))

    for i, d in enumerate(win):
        ds = _iso(d)
        bar_open = {s: float(opens[i, j]) for j, s in enumerate(syms) if valid[i, j]}
        for s in bar_open:
            last_bar_date[s] = ds

        # ---- a. open: execute the pending decision ------------------------------------------------------------
        no_bar_exits: set[str] = set()
        if state.pending is not None:
            pend = state.pending
            evs = fill_batch(gate, broker, state, pend["orders"], str(pend["date"]), ds, bar_open,
                             dict(last_price), dict(last_bar_date))
            for ev in evs:
                emit(ev)
                if ev["type"] == "skip" and ev["kind"] == "exit" and ev["reason"] == "no_bar":
                    no_bar_exits.add(ev["symbol"])
            emit({"type": "settle", "date": ds, "decision_date": str(pend["date"])})

        # ---- b. close: value, kill switch, decision ----------------------------------------------------------
        for j, s in enumerate(syms):
            if valid[i, j]:
                last_price[s] = float(closes[i, j])
        equity = book_value(state.cash, state.positions, last_price)
        view = GateView(date=ds, equity=equity, start_equity=state.start_equity, cash=state.cash,
                        positions=dict(state.positions), prices=dict(last_price),
                        last_bar_date=dict(last_bar_date), killed=state.killed)
        if not state.killed and gate.kill_triggered(view):
            emit({"type": "kill", "date": ds, "equity": float(equity)})
            killed_on = ds
        if i < len(win) - 1:
            held = {s for s, q in state.positions.items() if q > _QTY_EPS}
            tdict: dict[str, float] = {}
            reasons: list[str] = []
            if state.killed:
                if held:
                    tdict = {s: 0.0 for s in sorted(held)}
                    reasons.append("kill_switch")
            else:
                if is_dec[i]:
                    tdict = {s: float(tg[i, j]) for j, s in enumerate(syms) if _finite(tg[i, j])}
                    reasons.append("inception" if i == 0 else "schedule")
                for s in sorted(no_bar_exits & held):
                    if s not in tdict:
                        tdict[s] = 0.0
                        reasons.append(f"retry_exit:{s}")
            if reasons:
                orders = classify_orders(tdict, state.positions, last_price, equity, band, syms)
                emit({"type": "decision", "date": ds, "variant": label, "targets": tdict, "orders": orders,
                      "reason": ",".join(reasons), "equity": float(equity)})

        # ---- c. mark ------------------------------------------------------------------------------------------
        emit({"type": "mark", "date": ds, "equity": float(equity)})
        eq_out[i] = equity
        if equity > 0:
            for j, s in enumerate(syms):
                q = state.positions.get(s, 0.0)
                if q > _QTY_EPS:
                    w_out[i, j] = q * last_price[s] / equity

    equity_s = pd.Series(eq_out, index=win, name="equity")
    returns = equity_s.pct_change().fillna(0.0).rename("returns")
    weights = pd.DataFrame(w_out, index=win, columns=syms)
    return RunResult(equity=equity_s, returns=returns, weights=weights, fills=all_fills, skips=all_skips,
                     ledger=ledger, cost_mult=float(cost_mult), killed_on=killed_on)
