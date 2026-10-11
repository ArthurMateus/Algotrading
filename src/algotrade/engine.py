"""Bar-by-bar backtest loop: decide at close t, gate, fill at open t+1 through the paper broker, mark at close.

Owner: backtest-engineer. Every window starts flat with start equity (cash) at its first bar. Inception: the first
decision is taken at the close of the window's first bar and filled at the second bar's open; after that, decisions
follow `strategy.decision_dates`. Classification at decision time using close-t weights: target>0 and held==0 is an
entry, target==0 and held>0 is an exit, otherwise a rebalance traded only if |target - current| >= band.
Exits that cannot fill (no bar) are retried at each next open; other orders are dropped until the next decision.
All events go through a `ledger.Ledger` (in memory) so the final state can be replayed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

    from algotrade.broker import Fill, Skip
    from algotrade.config import MarketConfig
    from algotrade.data import Panel
    from algotrade.ledger import Ledger


@dataclass(frozen=True)
class RunResult:
    equity: "pd.Series"            # daily equity at close (USD), indexed by panel date over the window
    returns: "pd.Series"           # simple daily returns of equity (first bar = 0)
    weights: "pd.DataFrame"        # held weight per symbol at each close
    fills: list["Fill"]
    skips: list["Skip"]
    ledger: "Ledger"
    cost_mult: float


def run(panel: "Panel", targets: "pd.DataFrame", decisions: "pd.DatetimeIndex", cfg: "MarketConfig", *,
        start: str, end: str, cost_mult: float = 1.0, band: float | None = None) -> RunResult:
    """Simulate one window [start, end] inclusive. `band=None` uses cfg.rebalance_band; the benchmark passes 0.0."""
    raise NotImplementedError
