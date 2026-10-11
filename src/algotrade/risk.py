"""The ONE risk gate every simulated order passes (backtest and paper). Exits are never refused; entries and
increases fail closed.

Owner: risk-engineer. Rules (config [risk] and market config, docs/SPEC.md §5 and §11.11):
  - no shorts: a sell may not exceed the held quantity (it is clamped to the held quantity; a sell with nothing
    held is refused as `no_short`);
  - no leverage: buy notional + estimated costs <= cash; gross exposure after the fill <= max_gross_exposure (1.0);
  - per-instrument cap: weight after a buy <= 1/N (+1e-9);
  - stale data: no entry/increase in a symbol whose last real bar is older than stale_after_days (5 A, 2 B);
  - total-loss kill switch: once equity <= kill_loss_fraction * start equity, refuse every entry/increase for
    good and emit exits for all positions (`exit_orders`).

Weights are measured against the equity at the open of the fill bar BEFORE the trade (the same base the broker
uses for `target_weight * equity_at_open / open`), so a target of exactly 1/N passes despite costs. Gross
exposure is measured after the fill (positions at the open + cash after the estimated buy cost), which is <= 1
whenever cash stays >= 0. Equity for the caps is min(view.equity, cash + sum(qty * price)): the conservative one.

Cost estimate for a buy (pessimistic, same formulas as docs/success-criteria.md §4 and broker.CostModel):
qty * open * (1 + slippage * m) * (1 + commission * m), m = cost_mult. Regulatory fees apply to sells only.

Every input is checked; anything missing, non-finite or non-positive refuses an entry ("fail closed"). A sell
that reduces or closes a held long position is always allowed, whatever the state (killed, stale, bad view).
Stdlib only: no pandas at import time (tests/test_safety.py imports every module in a clean interpreter).
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from algotrade.broker import Order
    from algotrade.config import MarketConfig

TOL = 1e-9                               # relative tolerance on caps (float noise only)
_QTY_EPS = 1e-12                         # a position at or below this is flat


@dataclass(frozen=True)
class GateView:
    """What the gate sees at fill time (all known at that moment)."""
    date: str
    equity: float
    start_equity: float
    cash: float
    positions: dict[str, float]          # symbol -> qty
    prices: dict[str, float]             # symbol -> open price of the fill bar (latest known price for held symbols)
    last_bar_date: dict[str, str]        # symbol -> date of the latest real bar
    killed: bool


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    rule: str                            # "" if allowed, else the rule name
    qty: float = 0.0                     # quantity allowed (a sell is clamped to the held quantity); 0 if refused


# Rule names (Skip.reason = "risk_gate:<rule>").
KILLED = "kill_switch"
STALE = "stale_data"
NO_SHORT = "no_short"
CASH = "no_leverage_cash"
GROSS = "gross_exposure"
CAP = "instrument_cap"
NO_PRICE = "no_price"
BAD_QTY = "bad_qty"
BAD_VIEW = "bad_view"
BAD_ORDER = "bad_order"
UNKNOWN = "unknown_symbol"


def _finite_pos(x) -> bool:
    try:
        return math.isfinite(x) and x > 0
    except TypeError:
        return False


def _days_between(earlier: str, later: str) -> int | None:
    try:
        a = dt.date.fromisoformat(str(earlier)[:10])
        b = dt.date.fromisoformat(str(later)[:10])
    except ValueError:
        return None
    return (b - a).days


class RiskGate:
    def __init__(self, cfg: "MarketConfig", cost_mult: float = 1.0) -> None:
        if not cfg.instruments:
            raise ValueError("risk gate: no instruments")
        if not (0 < cfg.max_gross_exposure <= 1.0):
            raise ValueError(f"risk gate: max_gross_exposure must be in (0, 1] (no leverage), got {cfg.max_gross_exposure}")
        if not (0 < cfg.kill_loss_fraction < 1.0):
            raise ValueError(f"risk gate: kill_loss_fraction must be in (0, 1), got {cfg.kill_loss_fraction}")
        if cfg.stale_after_days < 1:
            raise ValueError(f"risk gate: stale_after_days must be >= 1, got {cfg.stale_after_days}")
        if not _finite_pos(cost_mult):
            raise ValueError(f"risk gate: cost_mult must be > 0, got {cost_mult}")
        self.instruments = frozenset(cfg.instruments)
        self.instrument_cap = 1.0 / len(cfg.instruments)
        self.max_gross = float(cfg.max_gross_exposure)
        self.kill_fraction = float(cfg.kill_loss_fraction)
        self.stale_after_days = int(cfg.stale_after_days)
        c = cfg.costs
        self.cost_mult = float(cost_mult)
        self.slippage = c.slippage_rate * self.cost_mult
        self.commission = c.commission_rate * self.cost_mult
        self.sec_sell = c.sec_fee_rate_sell * self.cost_mult
        self.taf_share = c.taf_per_share_sell * self.cost_mult
        self.taf_max = c.taf_max_per_trade * self.cost_mult

    # ---- cost estimates (pessimistic; used for the cash rule and for projecting a batch) --------------------
    def buy_cost(self, qty: float, open_price: float) -> float:
        """Cash a buy consumes: notional at open*(1+slip) plus commission on it."""
        return qty * open_price * (1 + self.slippage) * (1 + self.commission)

    def sell_proceeds(self, qty: float, open_price: float) -> float:
        """Cash a sell returns: notional at open*(1-slip) minus commission, SEC and TAF."""
        notional = qty * open_price * (1 - self.slippage)
        return notional * (1 - self.commission - self.sec_sell) - min(qty * self.taf_share, self.taf_max)

    # ---- the gate ---------------------------------------------------------------------------------------------
    def kill_triggered(self, view: GateView) -> bool:
        """True once equity <= kill_loss_fraction * start_equity (sticky via GateView.killed). Fails closed: a
        missing or non-finite equity or start equity counts as triggered."""
        if view.killed:
            return True
        if not (_finite_pos(view.start_equity) and isinstance(view.equity, (int, float))
                and math.isfinite(view.equity)):
            return True
        return view.equity <= self.kill_fraction * view.start_equity

    def check(self, order: "Order", qty: float, view: GateView) -> Verdict:
        """Allow or refuse one order. A sell that reduces or closes a long position is always allowed."""
        if order.side == "sell":
            return self._sell(order, qty, view)
        if order.side != "buy" or order.kind == "exit":
            return Verdict(False, BAD_ORDER)
        return self._buy(order, qty, view)

    def _sell(self, order: "Order", qty: float, view: GateView) -> Verdict:
        held = view.positions.get(order.symbol, 0.0)
        if not (isinstance(held, (int, float)) and held > _QTY_EPS):
            return Verdict(False, NO_SHORT)
        if order.kind == "exit":                       # an exit always sells the whole position (SPEC §11.3)
            return Verdict(True, "", float(held))
        if not _finite_pos(qty):
            return Verdict(False, BAD_QTY)
        return Verdict(True, "", float(min(qty, held)))

    def _buy(self, order: "Order", qty: float, view: GateView) -> Verdict:
        sym = order.symbol
        if self.kill_triggered(view):
            return Verdict(False, KILLED)
        if sym not in self.instruments:
            return Verdict(False, UNKNOWN)
        if not _finite_pos(qty):
            return Verdict(False, BAD_QTY)
        age = _days_between(view.last_bar_date.get(sym, ""), view.date)
        if age is None or age < 0 or age > self.stale_after_days:
            return Verdict(False, STALE)
        price = view.prices.get(sym)
        if not _finite_pos(price):
            return Verdict(False, NO_PRICE)
        cash = view.cash
        if not (isinstance(cash, (int, float)) and math.isfinite(cash) and cash >= 0):
            return Verdict(False, BAD_VIEW)
        held_value = 0.0
        for s, q in view.positions.items():
            if not (isinstance(q, (int, float)) and math.isfinite(q) and q >= 0):
                return Verdict(False, BAD_VIEW)
            if q <= _QTY_EPS:
                continue
            p = view.prices.get(s)
            if not _finite_pos(p):
                return Verdict(False, NO_PRICE)
            held_value += q * p
        equity = min(view.equity, cash + held_value)
        if not _finite_pos(equity):
            return Verdict(False, BAD_VIEW)
        cost = self.buy_cost(qty, price)
        if cost > cash * (1 + TOL):
            return Verdict(False, CASH)
        held = view.positions.get(sym, 0.0)
        if (held + qty) * price > self.instrument_cap * equity * (1 + TOL):
            return Verdict(False, CAP)
        after_positions = held_value + qty * price
        after_equity = after_positions + max(cash - cost, 0.0)
        if after_positions > self.max_gross * after_equity * (1 + TOL):
            return Verdict(False, GROSS)
        return Verdict(True, "", float(qty))

    # ---- helpers for the engine and the paper runner ---------------------------------------------------------
    def screen(self, orders: list[tuple["Order", float]], view: GateView
               ) -> list[tuple["Order", float, Verdict]]:
        """Check a batch the way the broker executes it: sells first, then buys, each against the view projected
        after the earlier allowed orders of the batch (estimated cash, updated positions). Returns
        (order, requested qty, verdict) in execution order."""
        sells = [(o, q) for o, q in orders if o.side == "sell"]
        buys = [(o, q) for o, q in orders if o.side != "sell"]
        out: list[tuple[Order, float, Verdict]] = []
        cash, pos = view.cash, dict(view.positions)
        for o, q in sells + buys:
            v = self.check(o, q, replace(view, cash=cash, positions=dict(pos)))
            out.append((o, q, v))
            if not v.allowed:
                continue
            price = view.prices.get(o.symbol)
            if o.side == "sell":
                pos[o.symbol] = pos.get(o.symbol, 0.0) - v.qty
                if pos[o.symbol] <= _QTY_EPS:
                    pos.pop(o.symbol)
                if _finite_pos(price):
                    cash += max(self.sell_proceeds(v.qty, price), 0.0)
            else:
                pos[o.symbol] = pos.get(o.symbol, 0.0) + v.qty
                cash -= self.buy_cost(v.qty, price)
        return out

    def exit_orders(self, view: GateView, decision_date: str, fill_date: str) -> list["Order"]:
        """Exit orders for every held position (used when the kill switch fires)."""
        from algotrade.broker import Order  # runtime import kept local (broker is stdlib only)
        return [Order(symbol=s, side="sell", kind="exit", target_weight=0.0, decision_date=decision_date,
                      fill_date=fill_date)
                for s, q in sorted(view.positions.items()) if q > _QTY_EPS]
