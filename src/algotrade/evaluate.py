"""Splits, walk-forward, selection, the IS and OOS runs, and the pass/fail table (docs/success-criteria.md §2, §6).

Owner: backtest-engineer.
  - E starts at the first date on which every instrument has >= warmup_bars real bars before it.
  - IS = first floor(is_fraction * len(E)) bars of E; OOS = the rest.
  - WF: IS cut into wf_blocks blocks at floor(k * n / 5); each variant simulated ONCE over IS, its daily returns
    sliced per block; for k = 2..5 pick the best Sharpe on blocks 1..k-1, take its block-k returns.
  - Selection: best full-IS Sharpe; ties -> longer lookback, then monthly.
IS writes reports/is_selection_<market>.json; OOS reads it (no manual choice possible).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

    from algotrade.config import MarketConfig
    from algotrade.data import Panel
    from algotrade.strategy import Variant


@dataclass(frozen=True)
class Split:
    e_start: str
    is_start: str
    is_end: str
    oos_start: str
    oos_end: str
    wf_blocks: list[tuple[str, str]]


def make_split(panel: "Panel", cfg: "MarketConfig") -> Split:
    raise NotImplementedError


def walk_forward(is_returns: dict[str, "pd.Series"], rf_per_bar: "pd.Series", split: Split,
                 periods_per_year: int) -> tuple["pd.Series", list[str]]:
    """(WF return series over blocks 2..5, chosen variant key per block)."""
    raise NotImplementedError


def select_variant(is_sharpes: dict["Variant", float]) -> "Variant":
    """Highest IS Sharpe; ties -> longer lookback, then monthly."""
    raise NotImplementedError


def run_is(market: str) -> dict:
    """Run the 12-variant grid on IS (cap enforced, each run logged), WF, selection, DSR (criteria 6, 7).
    Writes reports/is_selection_<market>.json and reports/backtest-<market>-is.md."""
    raise NotImplementedError


def run_oos(market: str, *, force: bool = False, reason: str = "") -> dict:
    """The single OOS run: selected variant at cost_mult 1 and 2, plus the benchmark. Evaluates criteria 1-5 and 8,
    the CDI flag and the reported extras; writes reports/backtest-<market>-oos.md with a PASS/FAIL table."""
    raise NotImplementedError


def status() -> str:
    """Plain-words summary: cache coverage, variants used per market, whether OOS has run."""
    raise NotImplementedError
