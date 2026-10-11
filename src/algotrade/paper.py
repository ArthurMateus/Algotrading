"""Forward paper runner (phase 6). Simulated fills only; no venue, no account, no keys.

Owner: risk-engineer. Run once a day (idempotent). Each step: replay the ledger at data/paper/<market>/ledger.jsonl;
fetch the newest public bars; if a pending decision exists and the next bar's open is now known, fill it through
RiskGate + PaperBroker at that open; if a new bar has closed and it is a decision date for the selected variant
(read from reports/is_selection_<market>.json), append a decision. Mark equity at the latest close. A stale feed
(no new bar for stale_after_days) halts entries and is logged.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StepReport:
    market: str
    as_of: str
    equity: float
    fills: int
    decisions: int
    halted: str                    # "" or the reason (stale data, kill switch)


def paper_step(market: str) -> StepReport:
    raise NotImplementedError
