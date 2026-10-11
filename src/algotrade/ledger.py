"""Crash-safe append-only JSONL ledger and the state fold. Used by the forward paper runner; the backtest
writes the same events to an in-memory ledger so replay can be tested.

Owner: risk-engineer. One JSON object per line, UTF-8, `\n`, flush + fsync after every append. Event types:
genesis {market, start_equity, config_sha256}, decision {date, variant, targets}, fill {...broker.Fill},
skip {...broker.Skip}, kill {date, equity}, mark {date, equity}. A torn last line (crash mid-write) is ignored on
replay and reported; any other bad line is an error.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class State:
    cash: float = 0.0
    positions: dict[str, float] = field(default_factory=dict)
    last_decision_date: str = ""
    pending: dict | None = None          # decision taken at a close, not yet filled at the next open
    killed: bool = False
    torn_tail: bool = False

    def apply(self, event: dict) -> None:
        """Fold one event into the state (pure apart from mutating self)."""
        raise NotImplementedError


class Ledger:
    def __init__(self, path: Path | None) -> None:
        """path=None keeps events in memory only (backtest)."""
        raise NotImplementedError

    def append(self, event: dict) -> None:
        """Write one event durably (fsync), then nothing else; the caller applies it to State."""
        raise NotImplementedError

    def events(self) -> list[dict]:
        raise NotImplementedError

    def replay(self) -> State:
        """Rebuild State from the file, tolerating a torn last line."""
        raise NotImplementedError
