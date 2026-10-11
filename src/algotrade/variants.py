"""Variant log and the multiple-testing guards: the 12-per-market cap and the one-time OOS run.

Owner: backtest-engineer. Source of truth: reports/variants.jsonl (append-only, one line per run). Every run also
appends a human-readable row to reports/variants.md (timestamp UTC, git commit, market, variant key, split,
cost_mult, headline metrics). The cap counts DISTINCT variant keys per market (a rerun of an identical config,
a cost multiplier or a split does not add a variant); a variant outside the pre-registered grid is refused.
OOS runs are recorded in reports/oos_runs.jsonl; a second OOS run for a market is refused unless forced, and a
forced run is logged with its reason and flagged in the report.

Benchmark runs are logged with key "benchmark" (BENCHMARK_KEY); that key is not a strategy variant and does not
count towards the cap.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
from pathlib import Path

VARIANTS_JSONL = "variants.jsonl"
VARIANTS_MD = "variants.md"
OOS_JSONL = "oos_runs.jsonl"
BENCHMARK_KEY = "benchmark"

_MD_HEADER = (
    "# Variant log\n\n"
    "Every backtest run, appended automatically by `algotrade.variants.record_run` (source of truth: "
    "`reports/variants.jsonl`). The cap counts distinct variant keys per market (12; the benchmark is not a "
    "variant). Timestamps are UTC.\n\n"
    "| Timestamp (UTC) | Commit | Market | Variant | Split | Cost x | Metrics |\n"
    "|---|---|---|---|---|---|---|\n"
)


class VariantCapError(RuntimeError):
    """A run would exceed the per-market cap or use a variant outside the grid."""


class OOSAlreadyRunError(RuntimeError):
    """The market's OOS window has already been used."""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_jsonl(path: Path) -> list[dict]:
    """Read JSON lines; a torn (unparseable) last line is ignored, a corrupt earlier line raises."""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            if i == len(lines) - 1:
                continue
            raise
    return out


def _append(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())


def _clean(v):
    """JSON-safe value: non-finite floats become null."""
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if isinstance(v, (bool, int, str)) or v is None:
        return v
    if isinstance(v, float):
        return v
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return str(v)


def _fmt(v) -> str:
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return "nan" if not math.isfinite(v) else f"{v:.4g}"
    return str(v)


def runs(reports_dir: Path, market: str | None = None) -> list[dict]:
    """All logged runs (optionally for one market), in log order."""
    rows = _read_jsonl(Path(reports_dir) / VARIANTS_JSONL)
    return [r for r in rows if market is None or r.get("market") == market]


def distinct_variants(reports_dir: Path, market: str) -> set[str]:
    """Distinct strategy variant keys logged for `market` (the benchmark key excluded)."""
    return {r["key"] for r in runs(reports_dir, market) if r.get("key") != BENCHMARK_KEY}


def check_cap(reports_dir: Path, market: str, keys: list[str], allowed: list[str], cap: int) -> None:
    """Raise VariantCapError if any key is not in `allowed` or distinct keys would exceed `cap`."""
    bad = [k for k in keys if k not in set(allowed)]
    if bad:
        raise VariantCapError(f"market {market}: variant(s) outside the pre-registered grid: {sorted(set(bad))}")
    seen = distinct_variants(reports_dir, market)
    total = seen | set(keys)
    if len(total) > cap:
        new = sorted(set(keys) - seen)
        raise VariantCapError(f"market {market}: {len(total)} distinct variants would exceed the cap of {cap} "
                              f"(already logged {len(seen)}; new {new})")


def record_run(reports_dir: Path, market: str, key: str, split: str, cost_mult: float,
               metrics: dict[str, float], git_commit: str) -> None:
    """Append to variants.jsonl and variants.md."""
    reports_dir = Path(reports_dir)
    ts = _now()
    row = {"ts": ts, "git_commit": git_commit, "market": market, "key": key, "split": split,
           "cost_mult": float(cost_mult), "metrics": {str(k): _clean(v) for k, v in metrics.items()}}
    _append(reports_dir / VARIANTS_JSONL, json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")
    md = reports_dir / VARIANTS_MD
    if not md.exists() or md.stat().st_size == 0:
        _append(md, _MD_HEADER)
    mtxt = ", ".join(f"{k}={_fmt(v)}" for k, v in metrics.items()).replace("|", "/")
    _append(md, f"| {ts} | {git_commit[:12]} | {market} | {key} | {split} | {float(cost_mult):g} | {mtxt} |\n")


def oos_runs(reports_dir: Path, market: str) -> list[dict]:
    """Logged OOS runs for `market` (the report flags any run after the first, and every forced one)."""
    return [r for r in _read_jsonl(Path(reports_dir) / OOS_JSONL) if r.get("market") == market]


def check_oos(reports_dir: Path, market: str, force: bool, reason: str = "") -> None:
    """Raise OOSAlreadyRunError if an OOS run exists and not force; with force, require a non-empty reason."""
    prior = oos_runs(reports_dir, market)
    if not prior:
        return
    if not force:
        raise OOSAlreadyRunError(f"market {market}: the OOS window was already used on {prior[0].get('ts')} "
                                 f"({len(prior)} run(s)); rerun only with --force --reason")
    if not reason.strip():
        raise OOSAlreadyRunError(f"market {market}: a forced OOS rerun needs a non-empty --reason")


def record_oos(reports_dir: Path, market: str, key: str, forced: bool, reason: str, git_commit: str) -> None:
    n = len(oos_runs(reports_dir, market)) + 1
    row = {"ts": _now(), "market": market, "key": key, "forced": bool(forced), "reason": reason,
           "git_commit": git_commit, "run_number": n}
    _append(Path(reports_dir) / OOS_JSONL, json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")
