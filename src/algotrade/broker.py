"""Pessimistic simulated broker: turns intended orders into fills at the bar open with costs. Paper only.

Owner: backtest-engineer. No network, no venue. Buys fill at open*(1+slip), sells at open*(1-slip). Fees per
docs/success-criteria.md §4, every fee and slippage figure multiplied by `cost_mult` (2.0 in the stress run).
Quantities are fractional (A) or floored to the lot step (B). An order below the minimum notional is skipped,
except an exit, which always trades in full (see docs/SPEC.md, ambiguity 3).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Side = Literal["buy", "sell"]
Kind = Literal["entry", "exit", "rebalance"]


@dataclass(frozen=True)
class CostModel:
    commission_rate: float
    sec_fee_rate_sell: float
    taf_per_share_sell: float
    taf_max_per_trade: float
    slippage_rate: float
    cost_mult: float = 1.0

    def fill_price(self, side: Side, open_price: float) -> float:
        """Open price moved against us by slippage_rate * cost_mult."""
        raise NotImplementedError

    def fees(self, side: Side, qty: float, price: float) -> tuple[float, float]:
        """(commission, regulatory) in USD for one fill, already multiplied by cost_mult."""
        raise NotImplementedError


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


@dataclass(frozen=True)
class Skip:
    symbol: str
    kind: Kind
    reason: str                    # "below_min_order" | "risk_gate:<rule>" | "no_bar" | "no_cash"
    date: str


class PaperBroker:
    """Holds no state of its own: the caller passes cash and positions, gets fills back."""

    def __init__(self, costs: CostModel, min_order_usd: dict[str, float], lot_step: dict[str, float]) -> None:
        raise NotImplementedError

    def execute(self, orders: list[Order], opens: dict[str, float], cash: float,
                positions: dict[str, float]) -> tuple[list[Fill], list[Skip]]:
        """Sells first, then buys (buys scaled down pro rata if cash after costs is short; never negative cash).
        Target quantity = target_weight * equity_at_open / open. Pure: same inputs, same outputs."""
        raise NotImplementedError
