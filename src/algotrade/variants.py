"""Variant log and the multiple-testing guards: the 12-per-market cap and the one-time OOS run.

Owner: backtest-engineer. Source of truth: reports/variants.jsonl (append-only, one line per run). Every run also
appends a human-readable row to reports/variants.md (timestamp UTC, git commit, market, variant key, split,
cost_mult, headline metrics). The cap counts DISTINCT variant keys per market (a rerun of an identical config,
a cost multiplier or a split does not add a variant); a variant outside the pre-registered grid is refused.
OOS runs are recorded in reports/oos_runs.jsonl; a second OOS run for a market is refused unless forced, and a
forced run is logged with its reason and flagged in the report.
"""
from __future__ import annotations

from pathlib import Path


class VariantCapError(RuntimeError):
    """A run would exceed the per-market cap or use a variant outside the grid."""


class OOSAlreadyRunError(RuntimeError):
    """The market's OOS window has already been used."""


def distinct_variants(reports_dir: Path, market: str) -> set[str]:
    raise NotImplementedError


def check_cap(reports_dir: Path, market: str, keys: list[str], allowed: list[str], cap: int) -> None:
    """Raise VariantCapError if any key is not in `allowed` or distinct keys would exceed `cap`."""
    raise NotImplementedError


def record_run(reports_dir: Path, market: str, key: str, split: str, cost_mult: float,
               metrics: dict[str, float], git_commit: str) -> None:
    """Append to variants.jsonl and variants.md."""
    raise NotImplementedError


def check_oos(reports_dir: Path, market: str, force: bool, reason: str = "") -> None:
    """Raise OOSAlreadyRunError if an OOS run exists and not force; with force, require a non-empty reason."""
    raise NotImplementedError


def record_oos(reports_dir: Path, market: str, key: str, forced: bool, reason: str, git_commit: str) -> None:
    raise NotImplementedError
