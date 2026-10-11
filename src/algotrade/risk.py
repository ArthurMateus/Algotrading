"""The ONE risk gate every simulated order passes (backtest and paper). Exits are never refused; entries and
increases fail closed.

Owner: risk-engineer. Rules (config [risk] and market config):
  - no shorts: a sell may not exceed the held quantity;
  - no leverage: buy notional + costs <= cash; gross exposure after the fill <= max_gross_exposure (1.0);
  - per-instrument cap: weight after a buy <= 1/N (+1e-9);
  - stale data: no entry/increase in a symbol whose last real bar is older than stale_after_days;
  - total-loss kill switch: once equity <= kill_loss_fraction * start equity, refuse every entry/increase for
    good and emit exits for all positions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from algotrade.broker import Order
    from algotrade.config import MarketConfig


@dataclass(frozen=True)
class GateView:
    """What the gate sees at fill time (all known at that moment)."""
    date: str
    equity: float
    start_equity: float
    cash: float
    positions: dict[str, float]          # symbol -> qty
    prices: dict[str, float]             # symbol -> open price of the fill bar
    last_bar_date: dict[str, str]        # symbol -> date of the latest real bar
    killed: bool


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    rule: str                            # "" if allowed, else the rule name


class RiskGate:
    def __init__(self, cfg: "MarketConfig") -> None:
        raise NotImplementedError

    def check(self, order: "Order", qty: float, view: GateView) -> Verdict:
        """Allow or refuse one order. A sell that reduces or closes a long position is always allowed."""
        raise NotImplementedError

    def kill_triggered(self, view: GateView) -> bool:
        """True once equity <= kill_loss_fraction * start_equity (sticky via GateView.killed)."""
        raise NotImplementedError
