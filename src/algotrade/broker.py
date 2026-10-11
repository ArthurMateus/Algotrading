"""Pessimistic simulated broker: turns intended orders into fills at the bar open with costs. Paper only.

Owner: backtest-engineer. No network, no venue. Buys fill at open*(1+slip), sells at open*(1-slip). Fees per
docs/success-criteria.md §4, every fee and slippage figure multiplied by `cost_mult` (2.0 in the stress run).
Quantities are fractional (A) or floored to the lot step (B). An order below the minimum notional is skipped,
except an exit, which always trades in full (see docs/SPEC.md, ambiguity 3).

Cost formulas (m = cost_mult, P = fill price after slippage, q = quantity):
  commission  = commission_rate * m * q * P                          (both sides; 0 for A, 0.10% for B)
  regulatory  = sells only: sec_fee_rate_sell * m * q * P + min(taf_per_share_sell * q, taf_max_per_trade) * m
  slippage    = q * |P - open|, with P = open * (1 + slippage_rate * m) for buys, open * (1 - slippage_rate * m)
                for sells
No cent rounding is applied to the SEC fee or TAF (the criteria give rates, not a rounding rule).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

Side = Literal["buy", "sell"]
Kind = Literal["entry", "exit", "rebalance"]

_LOT_EPS = 1e-9          # tolerance when flooring q / step (0.00003 / 0.00001 = 2.9999999999999996)
_CASH_EPS = 1e-12        # relative haircut so float rounding can never push cash below zero


@dataclass(frozen=True)
class CostModel:
    commission_rate: float
    sec_fee_rate_sell: float
    taf_per_share_sell: float
    taf_max_per_trade: float
    slippage_rate: float
    cost_mult: float = 1.0

    @classmethod
    def from_config(cls, costs, cost_mult: float = 1.0) -> "CostModel":
        """Build from `config.Costs` (min_order_usd is a broker argument, not a cost rate)."""
        return cls(costs.commission_rate, costs.sec_fee_rate_sell, costs.taf_per_share_sell,
                   costs.taf_max_per_trade, costs.slippage_rate, cost_mult)

    def fill_price(self, side: Side, open_price: float) -> float:
        """Open price moved against us by slippage_rate * cost_mult."""
        s = self.slippage_rate * self.cost_mult
        return open_price * (1.0 + s) if side == "buy" else open_price * (1.0 - s)

    def fees(self, side: Side, qty: float, price: float) -> tuple[float, float]:
        """(commission, regulatory) in USD for one fill, already multiplied by cost_mult."""
        m = self.cost_mult
        notional = qty * price
        commission = self.commission_rate * m * notional
        regulatory = 0.0
        if side == "sell":
            taf = min(self.taf_per_share_sell * qty, self.taf_max_per_trade)
            regulatory = (self.sec_fee_rate_sell * notional + taf) * m
        return commission, regulatory

    def buy_cost_per_unit(self, open_price: float) -> float:
        """Cash consumed per unit bought (fill price plus commission; buys pay no regulatory fee)."""
        p = self.fill_price("buy", open_price)
        return p * (1.0 + self.commission_rate * self.cost_mult)


@dataclass(frozen=True)
class Order:
    """An intended trade, decided at the close of `decision_date`, to fill at the open of `fill_date`."""
    symbol: str
    side: Side
    kind: Kind
    target_weight: float           # the sleeve weight wanted after the fill
    decision_date: str
    fill_date: str


@dataclass(frozen=True)
class Fill:
    symbol: str
    side: Side
    kind: Kind
    qty: float
    price: float                   # after slippage
    open_price: float
    commission: float
    regulatory: float
    slippage_cost: float           # qty * |price - open_price|
    date: str
    below_min: bool = False        # an exit sold in full although below the venue minimum (SPEC 11.3, counted)

    @property
    def notional(self) -> float:
        return self.qty * self.price

    @property
    def cash_delta(self) -> float:
        """Change in cash caused by this fill (negative for a buy)."""
        fees = self.commission + self.regulatory
        return -(self.notional + fees) if self.side == "buy" else self.notional - fees


@dataclass(frozen=True)
class Skip:
    symbol: str
    kind: Kind
    reason: str                    # "below_min_order" | "risk_gate:<rule>" | "no_bar" | "no_cash" | "no_position"
    date: str


def apply_fills(fills: list[Fill], cash: float, positions: dict[str, float]) -> tuple[float, dict[str, float]]:
    """Return (cash, positions) after the fills. Pure: the inputs are not modified. A position sold to zero is
    removed from the dict."""
    pos = dict(positions)
    for f in fills:
        cash += f.cash_delta
        q = pos.get(f.symbol, 0.0) + (f.qty if f.side == "buy" else -f.qty)
        if f.side == "sell" and (f.kind == "exit" or q <= 0.0):
            pos.pop(f.symbol, None)
        else:
            pos[f.symbol] = q
    return cash, pos


def _ok_price(p) -> bool:
    return p is not None and isinstance(p, (int, float)) and math.isfinite(p) and p > 0


class PaperBroker:
    """Holds no state of its own: the caller passes cash and positions, gets fills back."""

    def __init__(self, costs: CostModel, min_order_usd: dict[str, float], lot_step: dict[str, float]) -> None:
        self.costs = costs
        self.min_order_usd = dict(min_order_usd)
        self.lot_step = dict(lot_step)

    # ------------------------------------------------------------ helpers
    def floor_lot(self, symbol: str, qty: float) -> float:
        """Floor to the symbol's lot step (0 or missing = fractional, no rounding)."""
        step = self.lot_step.get(symbol, 0.0)
        if qty <= 0.0:
            return 0.0
        if not step or step <= 0.0:
            return qty
        n = math.floor(qty / step + _LOT_EPS)
        return round(n * step, 12)

    def _min(self, symbol: str) -> float:
        return float(self.min_order_usd.get(symbol, 0.0))

    @staticmethod
    def equity_at_open(cash: float, positions: dict[str, float], opens: dict[str, float],
                       marks: dict[str, float] | None = None) -> float:
        """cash + sum(qty * open). A held symbol with no valid open is valued at `marks` (e.g. its last close)."""
        eq = cash
        for s, q in positions.items():
            p = opens.get(s)
            if not _ok_price(p):
                p = (marks or {}).get(s)
            if not _ok_price(p):
                raise ValueError(f"no open or mark price to value the held position in {s}")
            eq += q * p
        return eq

    def planned_qty(self, order: Order, open_price: float, equity: float, held: float) -> float:
        """Unsigned quantity the broker would trade for `order` before cash scaling and the minimum check
        (for the risk gate). Sells: the full position for an exit, else held - target, floored to the lot step.
        Buys: target - held, floored to the lot step."""
        target = max(order.target_weight, 0.0) * equity / open_price
        if order.side == "sell":
            if order.kind == "exit" or order.target_weight <= 0.0:
                return max(held, 0.0)
            return min(self.floor_lot(order.symbol, held - target), max(held, 0.0))
        return self.floor_lot(order.symbol, target - held)

    # ------------------------------------------------------------ main
    def execute(self, orders: list[Order], opens: dict[str, float], cash: float,
                positions: dict[str, float], marks: dict[str, float] | None = None
                ) -> tuple[list[Fill], list[Skip]]:
        """Sells first, then buys (buys scaled down pro rata if cash after costs is short; never negative cash).
        Target quantity = target_weight * equity_at_open / open. Pure: same inputs, same outputs.

        `marks` (optional, additive) values held positions whose symbol has no open on this bar."""
        c = self.costs
        fills: list[Fill] = []
        skips: list[Skip] = []
        equity = self.equity_at_open(cash, positions, opens, marks)
        pos = dict(positions)

        sells = [o for o in orders if o.side == "sell"]
        buys = [o for o in orders if o.side == "buy"]

        for o in sells:
            p_open = opens.get(o.symbol)
            if not _ok_price(p_open):
                skips.append(Skip(o.symbol, o.kind, "no_bar", o.fill_date))
                continue
            held = pos.get(o.symbol, 0.0)
            if held <= 0.0:
                skips.append(Skip(o.symbol, o.kind, "no_position", o.fill_date))
                continue
            is_exit = o.kind == "exit" or o.target_weight <= 0.0
            qty = self.planned_qty(o, p_open, equity, held)
            price = c.fill_price("sell", p_open)
            below = qty * price < self._min(o.symbol)
            if qty <= 0.0 or (below and not is_exit):
                skips.append(Skip(o.symbol, o.kind, "below_min_order", o.fill_date))
                continue
            com, reg = c.fees("sell", qty, price)
            f = Fill(o.symbol, "sell", o.kind, qty, price, p_open, com, reg, qty * (p_open - price), o.fill_date,
                     below_min=bool(below and is_exit))
            fills.append(f)
            cash += f.cash_delta
            pos[o.symbol] = held - qty

        # buys: desired quantities, then one pro-rata scale if cash is short
        wanted: list[tuple[Order, float, float]] = []      # (order, open, qty)
        for o in buys:
            p_open = opens.get(o.symbol)
            if not _ok_price(p_open):
                skips.append(Skip(o.symbol, o.kind, "no_bar", o.fill_date))
                continue
            held = pos.get(o.symbol, 0.0)
            target = max(o.target_weight, 0.0) * equity / p_open
            q = target - held
            if q <= 0.0:
                skips.append(Skip(o.symbol, o.kind, "below_min_order", o.fill_date))
                continue
            wanted.append((o, p_open, q))
        need = sum(q * c.buy_cost_per_unit(p) for _, p, q in wanted)
        avail = max(cash, 0.0)
        scale = 1.0 if need <= avail else (avail / need if need > 0 else 0.0)
        for o, p_open, q in wanted:
            unit = c.buy_cost_per_unit(p_open)
            q = q * scale
            q = min(q, max(cash, 0.0) / unit * (1.0 - _CASH_EPS))
            q = self.floor_lot(o.symbol, q)
            price = c.fill_price("buy", p_open)
            if q <= 0.0:
                skips.append(Skip(o.symbol, o.kind, "no_cash" if scale < 1.0 else "below_min_order", o.fill_date))
                continue
            if q * price < self._min(o.symbol):
                skips.append(Skip(o.symbol, o.kind, "below_min_order", o.fill_date))
                continue
            com, reg = c.fees("buy", q, price)
            f = Fill(o.symbol, "buy", o.kind, q, price, p_open, com, reg, q * (price - p_open), o.fill_date)
            if cash + f.cash_delta < 0.0:          # cannot happen after the haircut; fail closed anyway
                skips.append(Skip(o.symbol, o.kind, "no_cash", o.fill_date))
                continue
            fills.append(f)
            cash += f.cash_delta
            pos[o.symbol] = pos.get(o.symbol, 0.0) + q
        return fills, skips
