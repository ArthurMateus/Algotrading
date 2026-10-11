"""Splits, walk-forward, selection, the IS and OOS runs, and the pass/fail table (docs/success-criteria.md §2, §6).

Owner: backtest-engineer.
  - E starts at the first date on which every instrument has >= warmup_bars real bars before it (SPEC 11.1).
    E ends at cfg.end_date (the panel is already truncated there).
  - IS = first floor(is_fraction * len(E)) bars of E; OOS = the rest (criteria §2).
  - WF: IS cut into wf_blocks blocks at floor(k * n / wf_blocks); each variant simulated ONCE over IS (SPEC 11.5),
    its daily returns sliced per block; for k = 2..5 pick the best Sharpe on blocks 1..k-1 (expanding), take its
    block-k returns. The concatenation is the WF series (criterion 7).
  - Selection: best full-IS Sharpe; ties -> longer lookback, then monthly (criteria §2). A tie that survives both
    rules (same lookback and rebalance, TSMOM vs SMA, exactly equal Sharpe) goes to the grid order (TSMOM first):
    not pre-registered, only there so the choice is deterministic.
  - Every window (each variant's IS run, the benchmark, each OOS run) starts flat at $300 (SPEC 11.2).
IS writes reports/is_selection_<market>.json (full IS record, read by OOS), reports/selected-<market>.json
({"variant": "<key>", "signal", "lookback", "rebalance", ...}; read by paper.py) and reports/backtest-<market>-is.md.
OOS reads that file (no manual choice possible), is refused a second time unless forced with a reason, and writes
reports/backtest-<market>-oos.md with the 8-criteria PASS/FAIL table.
pandas is imported inside functions only (tests/test_safety.py).
"""
from __future__ import annotations

import datetime as dt
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    import pandas as pd

    from algotrade.config import MarketConfig, Thresholds
    from algotrade.data import Aux, Panel
    from algotrade.engine import RunResult
    from algotrade.strategy import Variant

ROOT = Path(__file__).resolve().parents[2]
SELECTION_FILE = "is_selection_{market}.json"     # full IS record (read by run_oos)
SELECTED_FILE = "selected-{market}.json"          # the chosen variant only (read first by paper.py)
SELECTION_SCHEMA = 1

# Criteria without config keys, hard-coded from docs/success-criteria.md §6 (table rows 5, 7, 8):
CRIT5_X2_SHARPE_ABOVE = 0.0      # §6 row 5: "Doubled costs: excess return > 0 (Sharpe > 0)", strict
CRIT7_WF_SHARPE_ABOVE = 0.0      # §6 row 7: "WF series (IS) Sharpe > 0", strict
# §6 row 8: "Sharpe >= benchmark Sharpe AND max drawdown <= benchmark max drawdown" (both required)


class EvaluationRefused(RuntimeError):
    """An evaluation step refused to run (missing selection, data changed since IS, IS after OOS, ...)."""


@dataclass(frozen=True)
class Split:
    e_start: str
    is_start: str
    is_end: str
    oos_start: str
    oos_end: str
    wf_blocks: list[tuple[str, str]]
    n_e: int = 0
    n_is: int = 0
    n_oos: int = 0

    def to_dict(self) -> dict:
        return {"e_start": self.e_start, "is_start": self.is_start, "is_end": self.is_end,
                "oos_start": self.oos_start, "oos_end": self.oos_end,
                "wf_blocks": [list(b) for b in self.wf_blocks], "n_e": self.n_e, "n_is": self.n_is,
                "n_oos": self.n_oos}


@dataclass(frozen=True)
class Criterion:
    num: int
    name: str
    value: str
    threshold: str
    passed: bool
    where: str                     # "OOS" or "IS"


def _iso(ts) -> str:
    return ts.date().isoformat()


# ---------------------------------------------------------------------------------------------------- split / WF

def make_split(panel: "Panel", cfg: "MarketConfig") -> Split:
    """E start (SPEC 11.1), the IS/OOS split by bars (criteria §2) and the WF blocks inside IS."""
    import pandas as pd
    syms = list(cfg.instruments)
    valid = panel.valid[syms].astype("int64")
    before = valid.cumsum().shift(1).fillna(0)                # real bars strictly before each date
    ok = (before >= cfg.warmup_bars).all(axis=1)
    if not ok.any():
        raise EvaluationRefused(f"market {cfg.name}: no date has {cfg.warmup_bars} real bars for every instrument")
    e_start = ok.index[ok.to_numpy().argmax()]
    idx = pd.DatetimeIndex(panel.close.index)
    E = idx[(idx >= e_start) & (idx <= pd.Timestamp(cfg.end_date))]
    n = len(E)
    n_is = math.floor(n * cfg.is_fraction + 1e-9)            # +1e-9: 0.7 * 10 must give 7, not 6 by float noise
    k = cfg.wf_blocks
    if n_is < k or n - n_is < 2:
        raise EvaluationRefused(f"market {cfg.name}: E has {n} bars, too few for the split")
    cuts = [math.floor(i * n_is / k) for i in range(k + 1)]
    blocks = [(_iso(E[cuts[i]]), _iso(E[cuts[i + 1] - 1])) for i in range(k)]
    return Split(e_start=_iso(E[0]), is_start=_iso(E[0]), is_end=_iso(E[n_is - 1]), oos_start=_iso(E[n_is]),
                 oos_end=_iso(E[-1]), wf_blocks=blocks, n_e=n, n_is=n_is, n_oos=n - n_is)


def _parse_key(key: str) -> "Variant":
    from algotrade.strategy import Variant
    sig, lb, reb = key.split("-")
    return Variant(sig, int(lb), reb)


def _sel_key(item):
    from algotrade.strategy import SIGNALS
    v, s = item
    s = s if (s is not None and math.isfinite(s)) else -math.inf
    return (s, v.lookback, v.rebalance == "monthly", -SIGNALS.index(v.signal))


def select_variant(is_sharpes: dict["Variant", float]) -> "Variant":
    """Highest IS Sharpe; ties -> longer lookback, then monthly (criteria §2); then grid order (TSMOM first).
    A NaN Sharpe ranks last."""
    if not is_sharpes:
        raise ValueError("no variants to select from")
    return max(is_sharpes.items(), key=_sel_key)[0]


def walk_forward(is_returns: dict[str, "pd.Series"], rf_per_bar: "pd.Series", split: Split,
                 periods_per_year: int) -> tuple["pd.Series", list[str]]:
    """(WF return series over blocks 2..5, chosen variant key per block)."""
    import pandas as pd

    from algotrade.metrics import sharpe
    blocks = [(pd.Timestamp(a), pd.Timestamp(b)) for a, b in split.wf_blocks]
    parts, chosen = [], []
    for k in range(1, len(blocks)):
        train0, train1 = blocks[0][0], blocks[k - 1][1]
        sh = {_parse_key(key): sharpe(r.loc[train0:train1], rf_per_bar, periods_per_year)
              for key, r in is_returns.items()}
        best = select_variant(sh)
        chosen.append(best.key)
        parts.append(is_returns[best.key].loc[blocks[k][0]:blocks[k][1]])
    wf = pd.concat(parts) if parts else pd.Series(dtype="float64")
    return wf.rename("wf_returns"), chosen


# ---------------------------------------------------------------------------------------------------- criteria

def evaluate_criteria(th: "Thresholds", *, sharpe: float, max_dd: float, underwater_months: float,
                      round_trips: int, sharpe_x2: float, dsr: float, wf_sharpe: float,
                      bench_sharpe: float, bench_max_dd: float) -> list[Criterion]:
    """The 8 pass/fail criteria of docs/success-criteria.md §6. Any NaN input fails its criterion."""
    def ok(x) -> bool:
        return x is not None and isinstance(x, (int, float)) and math.isfinite(x)

    def f(x, pct=False) -> str:
        if not ok(x):
            return "nan"
        return f"{x * 100:.2f}%" if pct else f"{x:.3f}"

    c8 = ok(sharpe) and ok(bench_sharpe) and ok(max_dd) and ok(bench_max_dd) and \
        sharpe >= bench_sharpe and max_dd <= bench_max_dd
    return [
        Criterion(1, "Annualised Sharpe (excess of T-bill)", f(sharpe), f">= {th.sharpe_min:.2f}",
                  ok(sharpe) and sharpe >= th.sharpe_min, "OOS"),
        Criterion(2, "Max drawdown (daily equity)", f(max_dd, True), f"<= {th.max_dd_max * 100:.0f}%",
                  ok(max_dd) and max_dd <= th.max_dd_max, "OOS"),
        Criterion(3, "Longest underwater period (months)", f(underwater_months),
                  f"<= {th.underwater_months_max}", ok(underwater_months)
                  and underwater_months <= th.underwater_months_max, "OOS"),
        Criterion(4, "Completed round trips", str(round_trips), f">= {th.round_trips_min}",
                  round_trips >= th.round_trips_min, "OOS"),
        Criterion(5, "Doubled costs: Sharpe (excess of T-bill)", f(sharpe_x2), f"> {CRIT5_X2_SHARPE_ABOVE:g}",
                  ok(sharpe_x2) and sharpe_x2 > CRIT5_X2_SHARPE_ABOVE, "OOS"),
        Criterion(6, "Deflated Sharpe ratio of the selected IS variant", f(dsr), f">= {th.dsr_min:.2f}",
                  ok(dsr) and dsr >= th.dsr_min, "IS"),
        Criterion(7, "Walk-forward series Sharpe", f(wf_sharpe), f"> {CRIT7_WF_SHARPE_ABOVE:g}",
                  ok(wf_sharpe) and wf_sharpe > CRIT7_WF_SHARPE_ABOVE, "IS"),
        Criterion(8, "Beats benchmark: Sharpe >= bench AND max DD <= bench",
                  f"Sharpe {f(sharpe)} vs {f(bench_sharpe)}; DD {f(max_dd, True)} vs {f(bench_max_dd, True)}",
                  "both", bool(c8), "OOS"),
    ]


# ---------------------------------------------------------------------------------------------------- helpers

def _git_commit() -> str:
    import subprocess
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT,
                             timeout=20).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True,
                               text=True, cwd=ROOT, timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return (sha or "unknown") + ("-dirty" if dirty else "")


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _inputs(market: str, cfg, panel, aux_fn, min_order, lot):
    from algotrade import data
    from algotrade.config import load_config, verify_criteria
    cfg = cfg or load_config(market)
    if cfg.name != market:
        raise ValueError(f"config is for market {cfg.name}, not {market}")
    verify_criteria(cfg)
    if panel is None:
        panel = data.build_panel(data.load_bars(cfg), cfg.end_date)
    if aux_fn is None:
        aux_fn = lambda index: data.load_aux(cfg, index)      # noqa: E731
    min_order = data.min_order_usd(cfg) if min_order is None else min_order
    lot = data.lot_step(cfg) if lot is None else lot
    return cfg, panel, aux_fn, min_order, lot


def _headline(res: "RunResult", rf: "pd.Series", ppy: int) -> dict:
    from algotrade import metrics as M
    peak, end, months, rec = M.longest_underwater(res.equity)
    costs = M.cost_breakdown(res.fills)
    return {
        "sharpe": M.sharpe(res.returns, rf, ppy),
        "max_dd": M.max_drawdown(res.equity),
        "underwater_months": months,
        "underwater_peak": peak, "underwater_end": end, "underwater_recovered": rec,
        "round_trips": M.round_trips(res.fills),
        "cagr": M.cagr(res.equity),
        "final_equity": float(res.equity.iloc[-1]),
        "turnover": M.turnover(res.fills, res.equity, ppy),
        "exposure": M.exposure(res.weights),
        "underwater_share": M.underwater_share(res.equity),
        "median_dd_days": M.median_drawdown_length(res.equity),
        "n_fills": len(res.fills),
        "n_skips": len(res.skips),
        "below_min_exits": res.below_min_exits,
        "cost_commission": costs["commission"], "cost_regulatory": costs["regulatory"],
        "cost_slippage": costs["slippage"], "cost_total": costs["total"],
        "killed_on": res.killed_on,
    }


_LOG_KEYS = ("sharpe", "max_dd", "underwater_months", "round_trips", "cagr", "final_equity", "cost_total",
             "n_fills", "below_min_exits")


def _log_metrics(h: dict) -> dict:
    return {k: h[k] for k in _LOG_KEYS}


def _simulate(panel, cfg, targets, rebalance, window, cost_mult, band, min_order, lot, label) -> "RunResult":
    from algotrade import engine, strategy
    dd = strategy.decision_dates(panel.close.index, rebalance)
    return engine.run(panel, targets, dd, cfg, start=window[0], end=window[1], cost_mult=cost_mult, band=band,
                      min_order=min_order, lot=lot, label=label)


def _skip_counts(res: "RunResult") -> dict[str, int]:
    out: dict[str, int] = {}
    for s in res.skips:
        out[s.reason] = out.get(s.reason, 0) + 1
    return dict(sorted(out.items()))


def _f(x, nd=3, pct=False) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "nan"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        return f"{x * 100:.2f}%" if pct else f"{x:.{nd}f}"
    return str(x)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = text.replace("§", "s.").encode("ascii", "replace").decode("ascii")   # plain ASCII; section sign -> s.
    path.write_text(text, encoding="utf-8", newline="\n")


def _json_safe(obj):
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def selection_path(cfg: "MarketConfig") -> Path:
    return Path(cfg.reports_dir) / SELECTION_FILE.format(market=cfg.name)


def load_selection(cfg: "MarketConfig") -> dict:
    """Read reports/is_selection_<market>.json (raises EvaluationRefused if missing or for another config)."""
    p = selection_path(cfg)
    if not p.exists():
        raise EvaluationRefused(f"market {cfg.name}: {p.name} not found; run `uv run algotrade backtest "
                                f"--market {cfg.name} --split is` first")
    sel = json.loads(p.read_text(encoding="utf-8"))
    if sel.get("market") != cfg.name or sel.get("schema") != SELECTION_SCHEMA:
        raise EvaluationRefused(f"{p.name}: wrong market or schema")
    if sel.get("criteria_sha256") != cfg.criteria_sha256:
        raise EvaluationRefused(f"{p.name}: made under a different criteria hash")
    return sel


def _flags(cfg, panel, aux, forced_note: str = "") -> list[str]:
    out = []
    if not aux.rf_available:
        out.append("DTB3 unavailable: Sharpe uses raw returns (rf = 0), criteria §5 / SPEC 11.8.")
    if panel.adjusted == "price_only":
        out.append("Price-only bars (no dividends) for at least one instrument; strategy and benchmark both use "
                   "them (criteria §1).")
    if "binance_vision" in cfg.sources:
        out.append("Minimum notional and lot step are today's exchangeInfo applied to all history (SPEC 11.10, "
                   "approximation).")
    out.append("Survivorship/hindsight (Opinion): instruments were chosen today knowing they survived "
               "(criteria §1).")
    if forced_note:
        out.insert(0, forced_note)
    return out


# ---------------------------------------------------------------------------------------------------- IS

def run_is(market: str, *, cfg: "MarketConfig | None" = None, panel: "Panel | None" = None,
           aux_fn: "Callable[[pd.DatetimeIndex], Aux] | None" = None, min_order: dict | None = None,
           lot: dict | None = None, git_commit: str | None = None) -> dict:
    """Run the 12-variant grid on IS (cap enforced, each run logged), WF, selection, DSR (criteria 6, 7).
    Writes reports/is_selection_<market>.json and reports/backtest-<market>-is.md.

    The keyword arguments exist for tests (synthetic panel, temp reports dir); the CLI passes none of them."""
    from algotrade import metrics as M
    from algotrade import strategy
    from algotrade.variants import BENCHMARK_KEY, check_cap, distinct_variants, oos_runs, record_run

    cfg, panel, aux_fn, min_order, lot = _inputs(market, cfg, panel, aux_fn, min_order, lot)
    rd = Path(cfg.reports_dir)
    if oos_runs(rd, market):
        raise EvaluationRefused(f"market {market}: the OOS run already happened; the IS selection is frozen "
                                f"(criteria §2: no re-selection after OOS)")
    commit = git_commit if git_commit is not None else _git_commit()
    split = make_split(panel, cfg)
    aux = aux_fn(panel.close.index)
    rf = aux.rf_per_bar
    ppy = cfg.periods_per_year
    window = (split.is_start, split.is_end)

    variants = strategy.grid(cfg)
    keys = [v.key for v in variants]
    check_cap(rd, market, keys, keys, cfg.variant_cap)

    results: dict[str, dict] = {}
    returns: dict[str, "pd.Series"] = {}
    for v in variants:
        res = _simulate(panel, cfg, strategy.target_weights(panel, v, cfg), v.rebalance, window, 1.0, None,
                        min_order, lot, v.key)
        h = _headline(res, rf, ppy)
        h["per_bar_sharpe"] = M.per_bar_sharpe(res.returns, rf)
        record_run(rd, market, v.key, "is", 1.0, _log_metrics(h), commit)
        results[v.key] = h
        returns[v.key] = res.returns
    bres = _simulate(panel, cfg, strategy.benchmark_weights(panel)[list(cfg.instruments)], "monthly", window, 1.0,
                     0.0, min_order, lot, BENCHMARK_KEY)
    bench = _headline(bres, rf, ppy)
    record_run(rd, market, BENCHMARK_KEY, "is", 1.0, _log_metrics(bench), commit)

    selected = select_variant({v: results[v.key]["sharpe"] for v in variants})
    wf_ret, wf_choices = walk_forward(returns, rf, split, ppy)
    wf_sharpe = M.sharpe(wf_ret, rf, ppy) if len(wf_ret) else float("nan")

    r_sel = returns[selected.key]
    sr_hat = M.per_bar_sharpe(r_sel, rf)
    skew, kurt, n_obs = M.moments(r_sel, rf)
    sr_trials = [results[k]["per_bar_sharpe"] for k in keys]
    n_trials = len(distinct_variants(rd, market))
    dsr = M.deflated_sharpe(sr_hat, sr_trials, n_obs, skew, kurt, n_trials=n_trials)

    sel = {
        "schema": SELECTION_SCHEMA, "market": market, "created_utc": _now(), "git_commit": commit,
        "criteria_sha256": cfg.criteria_sha256,
        "selected": {"key": selected.key, "signal": selected.signal, "lookback": selected.lookback,
                     "rebalance": selected.rebalance},
        "split": split.to_dict(),
        "is_sharpe": {k: results[k]["sharpe"] for k in keys},
        "wf": {"sharpe": wf_sharpe, "block_choices": wf_choices, "n_obs": int(len(wf_ret))},
        "dsr": {"value": dsr, "sr_hat_per_bar": sr_hat, "n_obs": n_obs, "skew": skew, "kurtosis": kurt,
                "n_trials": n_trials, "sr_trials_per_bar": sr_trials},
        "rf_available": bool(aux.rf_available),
    }
    sp = selection_path(cfg)
    _write(sp, json.dumps(_json_safe(sel), indent=2, sort_keys=True) + "\n")
    chosen = {"variant": selected.key, "signal": selected.signal, "lookback": selected.lookback,
              "rebalance": selected.rebalance, "market": market, "created_utc": sel["created_utc"],
              "git_commit": commit, "criteria_sha256": cfg.criteria_sha256, "source": sp.name}
    _write(rd / SELECTED_FILE.format(market=market), json.dumps(chosen, indent=2, sort_keys=True) + "\n")

    th = cfg.thresholds
    c6 = Criterion(6, "Deflated Sharpe ratio of the selected IS variant", _f(dsr), f">= {th.dsr_min:.2f}",
                   math.isfinite(dsr) and dsr >= th.dsr_min, "IS")
    c7 = Criterion(7, "Walk-forward series Sharpe", _f(wf_sharpe), f"> {CRIT7_WF_SHARPE_ABOVE:g}",
                   math.isfinite(wf_sharpe) and wf_sharpe > CRIT7_WF_SHARPE_ABOVE, "IS")
    report = rd / f"backtest-{market}-is.md"
    _write(report, _is_report(cfg, split, keys, results, bench, selected, wf_choices, wf_sharpe, sel["dsr"],
                              [c6, c7], _flags(cfg, panel, aux), commit, sp))
    return {"market": market, "selected": selected.key, "split": split.to_dict(), "wf_sharpe": wf_sharpe,
            "dsr": dsr, "criteria": [c6, c7], "report": str(report), "selection_file": str(sp),
            "is_sharpe": sel["is_sharpe"], "benchmark_sharpe": bench["sharpe"]}


def _is_report(cfg, split, keys, results, bench, selected, wf_choices, wf_sharpe, dsr, crits, flags, commit,
               sel_path) -> str:
    m = cfg.name
    L = [f"# Backtest {m}: in-sample (IS)", "",
         f"Generated {_now()} by `uv run algotrade backtest --market {m} --split is` (commit `{commit}`). "
         f"Pre-registered rules: `docs/success-criteria.md` (sha256 `{cfg.criteria_sha256[:12]}...`). "
         "**Evidence** = numbers computed below; **Opinion** is labelled. Technical analysis, not financial advice.",
         "", "## Split (criteria §2, SPEC 11.1)", "",
         "| E start | IS | OOS | bars E / IS / OOS |", "|---|---|---|---|",
         f"| {split.e_start} | {split.is_start}..{split.is_end} | {split.oos_start}..{split.oos_end} | "
         f"{split.n_e} / {split.n_is} / {split.n_oos} |", "",
         "WF blocks: " + ", ".join(f"{i + 1}: {a}..{b}" for i, (a, b) in enumerate(split.wf_blocks)), "",
         "## Criteria evaluated on IS", "", "| # | Criterion | Value | Threshold | Result |", "|---|---|---|---|---|"]
    L += [f"| {c.num} | {c.name} | {c.value} | {c.threshold} | {'PASS' if c.passed else 'FAIL'} |" for c in crits]
    L += ["", f"Selected variant (highest IS Sharpe; ties: longer lookback, then monthly): **{selected.key}**. "
          f"Saved to `{Path(sel_path).name}` (read by the OOS run) and `{SELECTED_FILE.format(market=m)}` "
          "(read by the paper runner).", "",
          f"Walk-forward choices for blocks 2..{cfg.wf_blocks}: {', '.join(wf_choices)}; WF Sharpe {_f(wf_sharpe)}.",
          f"DSR inputs (per bar): SR {_f(dsr['sr_hat_per_bar'], 4)}, n_obs {dsr['n_obs']}, skew {_f(dsr['skew'])}, "
          f"kurtosis {_f(dsr['kurtosis'])}, N trials {dsr['n_trials']}.", "",
          f"## All {len(keys)} variants on IS (net of x1 costs, start $300 each)", "",
          "| Variant | Sharpe | Max DD | Underwater (mo) | Round trips | CAGR | Costs $ | Final $ |",
          "|---|---|---|---|---|---|---|---|"]
    for k in keys + ["benchmark"]:
        h = bench if k == "benchmark" else results[k]
        name = f"**{k}**" if k == selected.key else k
        L.append(f"| {name} | {_f(h['sharpe'])} | {_f(h['max_dd'], pct=True)} | {_f(h['underwater_months'], 1)} | "
                 f"{h['round_trips']} | {_f(h['cagr'], pct=True)} | {_f(h['cost_total'], 2)} | "
                 f"{_f(h['final_equity'], 2)} |")
    L += ["", "Sharpe: mean(r - rf) / sd(ddof=1) x sqrt(%d), rf = DTB3/100/%d per bar." % (
        cfg.periods_per_year, cfg.periods_per_year), "", "## Flags", ""]
    L += [f"- {x}" for x in flags]
    L += ["", "The OOS window has not been touched by this run."]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------------------------------- OOS

def run_oos(market: str, *, force: bool = False, reason: str = "", cfg: "MarketConfig | None" = None,
            panel: "Panel | None" = None, aux_fn: "Callable[[pd.DatetimeIndex], Aux] | None" = None,
            min_order: dict | None = None, lot: dict | None = None, git_commit: str | None = None) -> dict:
    """The single OOS run: selected variant at cost_mult 1 and 2, plus the benchmark. Evaluates criteria 1-5 and 8,
    the CDI flag and the reported extras; writes reports/backtest-<market>-oos.md with a PASS/FAIL table.
    Criteria 6 and 7 are read from the IS selection file."""
    import pandas as pd

    from algotrade import metrics as M
    from algotrade import strategy
    from algotrade.variants import BENCHMARK_KEY, check_oos, oos_runs, record_oos, record_run

    cfg, panel, aux_fn, min_order, lot = _inputs(market, cfg, panel, aux_fn, min_order, lot)
    rd = Path(cfg.reports_dir)
    sel = load_selection(cfg)
    check_oos(rd, market, force, reason)
    prior = oos_runs(rd, market)
    split = make_split(panel, cfg)
    if split.to_dict() != sel["split"]:
        raise EvaluationRefused(f"market {market}: the split recomputed from the cached data differs from the one "
                                f"in {selection_path(cfg).name} (data changed since IS); refusing")
    variant = _parse_key(sel["selected"]["key"])
    commit = git_commit if git_commit is not None else _git_commit()
    forced = bool(prior)
    # Record the use of the OOS window BEFORE simulating: a crash mid-run still counts as the one OOS look.
    record_oos(rd, market, variant.key, forced, reason, commit)

    aux = aux_fn(panel.close.index)
    rf = aux.rf_per_bar
    ppy = cfg.periods_per_year
    window = (split.oos_start, split.oos_end)
    targets = strategy.target_weights(panel, variant, cfg)
    r1 = _simulate(panel, cfg, targets, variant.rebalance, window, 1.0, None, min_order, lot, variant.key)
    r2 = _simulate(panel, cfg, targets, variant.rebalance, window, 2.0, None, min_order, lot, variant.key)
    rb = _simulate(panel, cfg, strategy.benchmark_weights(panel)[list(cfg.instruments)], "monthly", window, 1.0,
                   0.0, min_order, lot, BENCHMARK_KEY)
    h1, h2, hb = (_headline(r, rf, ppy) for r in (r1, r2, rb))
    record_run(rd, market, variant.key, "oos", 1.0, _log_metrics(h1), commit)
    record_run(rd, market, variant.key, "oos", 2.0, _log_metrics(h2), commit)
    record_run(rd, market, BENCHMARK_KEY, "oos", 1.0, _log_metrics(hb), commit)

    def num(x):
        return float("nan") if x is None else float(x)

    crits = evaluate_criteria(cfg.thresholds, sharpe=h1["sharpe"], max_dd=h1["max_dd"],
                              underwater_months=h1["underwater_months"], round_trips=h1["round_trips"],
                              sharpe_x2=h2["sharpe"], dsr=num(sel["dsr"]["value"]), wf_sharpe=num(sel["wf"]["sharpe"]),
                              bench_sharpe=hb["sharpe"], bench_max_dd=hb["max_dd"])
    passed = all(c.passed for c in crits)

    eq = r1.equity
    cal = aux_fn(pd.date_range(eq.index[0], eq.index[-1], freq="D"))     # keeps BR business days on US holidays
    cdi = M.brl_cdi_flag(eq, cal.ptax, cal.cdi_daily, cal.cdi_business_day)

    forced_note = ""
    if forced:
        forced_note = (f"**FORCED OOS RERUN #{len(prior) + 1}** (reason: {reason!r}). The OOS window had already "
                       f"been used {len(prior)} time(s); treat this result with extra suspicion.")
    report = rd / f"backtest-{market}-oos.md"
    _write(report, _oos_report(cfg, split, variant, sel, crits, passed, h1, h2, hb, r1, r2, rb, cdi,
                               _flags(cfg, panel, aux, forced_note), commit))
    return {"market": market, "selected": variant.key, "passed": passed, "criteria": crits,
            "metrics": {"x1": h1, "x2": h2, "benchmark": hb}, "cdi": cdi, "forced": forced,
            "report": str(report)}


def _oos_report(cfg, split, variant, sel, crits, passed, h1, h2, hb, r1, r2, rb, cdi, flags, commit) -> str:
    m = cfg.name
    verdict = "PASS (all 8 criteria hold)" if passed else \
        f"FAIL (NO-GO for market {m}: criteria {', '.join(str(c.num) for c in crits if not c.passed)} failed)"
    L = [f"# Backtest {m}: out-of-sample (OOS)", "",
         f"Generated {_now()} by `uv run algotrade backtest --market {m} --split oos` (commit `{commit}`). "
         f"Selected on IS (`{SELECTION_FILE.format(market=m)}`, {sel['created_utc']}): **{variant.key}**. "
         f"OOS window {split.oos_start}..{split.oos_end} ({split.n_oos} bars), start $"
         f"{cfg.start_equity_usd:.0f}, flat. Technical analysis, not financial advice.", "",
         f"## Verdict: {verdict}", ""]
    if flags and flags[0].startswith("**FORCED"):
        L += [flags[0], ""]
    L += ["## Pass/fail table (docs/success-criteria.md §6; net of costs)", "",
          "| # | Criterion | Period | Value | Threshold | Result |", "|---|---|---|---|---|---|"]
    L += [f"| {c.num} | {c.name} | {c.where} | {c.value} | {c.threshold} | {'PASS' if c.passed else 'FAIL'} |"
          for c in crits]
    L += ["", "Criteria 5, 7 and 8 have no config keys; their rules are hard-coded from §6 rows 5, 7, 8 "
          "(`evaluate.CRIT5_X2_SHARPE_ABOVE`, `CRIT7_WF_SHARPE_ABOVE`, `evaluate_criteria`).",
          f"Criterion 3: longest spell {h1['underwater_peak']}..{h1['underwater_end']} "
          f"({'recovered' if h1['underwater_recovered'] else 'not recovered, counted to the OOS end'}).", "",
          "## Runs (Evidence)", "",
          "| Metric | Strategy x1 | Strategy x2 costs | Benchmark x1 |", "|---|---|---|---|"]
    rows = [("Sharpe (excess of T-bill)", "sharpe", 3, False), ("Max drawdown", "max_dd", 3, True),
            ("Longest underwater (months)", "underwater_months", 1, False), ("Round trips", "round_trips", 0, False),
            ("CAGR", "cagr", 3, True), ("Final equity $", "final_equity", 2, False),
            ("Share of days under water", "underwater_share", 3, True),
            ("Median drawdown length (days)", "median_dd_days", 1, False),
            ("Turnover (x/yr)", "turnover", 2, False), ("Exposure (mean gross)", "exposure", 3, True),
            ("Fills", "n_fills", 0, False), ("Skipped orders", "n_skips", 0, False),
            ("Exits below the venue minimum (sold anyway)", "below_min_exits", 0, False)]
    for name, k, nd, pct in rows:
        L.append(f"| {name} | {_f(h1[k], nd, pct)} | {_f(h2[k], nd, pct)} | {_f(hb[k], nd, pct)} |")
    L += ["", "## Cost breakdown (USD, whole OOS window)", "",
          "| Component | Strategy x1 | Strategy x2 | Benchmark x1 |", "|---|---|---|---|"]
    for name, k in (("Commission", "cost_commission"), ("Regulatory (SEC + TAF)", "cost_regulatory"),
                    ("Slippage", "cost_slippage")):
        L.append(f"| {name} | {_f(h1[k], 2)} | {_f(h2[k], 2)} | {_f(hb[k], 2)} |")
    L.append("| Funding | 0.00 (spot, none) | 0.00 | 0.00 |")
    L.append(f"| **Total** | {_f(h1['cost_total'], 2)} | {_f(h2['cost_total'], 2)} | {_f(hb['cost_total'], 2)} |")
    sk = ", ".join(f"{k}={v}" for k, v in _skip_counts(r1).items()) or "none"
    L += ["", f"Skipped orders (x1) by reason: {sk}.",
          f"Exits sold in full below the venue minimum (x1): {h1['below_min_exits']} (SPEC 11.3; a real venue "
          "may refuse these).", ""]
    for name, r in (("strategy x1", r1), ("strategy x2", r2), ("benchmark", rb)):
        if r.killed_on:
            L.append(f"Kill switch fired for the {name} on {r.killed_on} (Opinion rule, SPEC §5).")
    L += ["", "## BRL / CDI flag (criteria §5; a flag, not pass/fail)", ""]
    if cdi["available"]:
        L.append(f"Strategy x1 equity converted to BRL at PTAX: CAGR {_f(cdi['brl_cagr'], pct=True)} vs compounded "
                 f"CDI {_f(cdi['cdi_cagr'], pct=True)} over the same dates, before tax. "
                 f"**{'Beats CDI' if cdi['beats_cdi'] else 'Red flag: does not beat CDI'}**.")
    else:
        L.append("insufficient data (PTAX or CDI missing for the window).")
    L += ["", "## Flags", ""] + [f"- {x}" for x in flags if not x.startswith("**FORCED")]
    L += ["", f"IS criteria 6 and 7 come from `{SELECTION_FILE.format(market=m)}` (DSR N = "
          f"{sel['dsr']['n_trials']} distinct variants logged). Sharpe annualised with sqrt({cfg.periods_per_year})."]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------------------------------- status

def status(reports_dir: Path | None = None) -> str:
    """Plain-words summary: variants used per market, the selection, whether OOS has run."""
    from algotrade.config import load_config
    from algotrade.variants import distinct_variants, oos_runs
    lines = []
    for m in ("A", "B"):
        cfg = load_config(m)
        rd = Path(reports_dir) if reports_dir is not None else Path(cfg.reports_dir)
        used = len(distinct_variants(rd, m))
        sp = rd / SELECTION_FILE.format(market=m)
        sel = "none"
        if sp.exists():
            try:
                sel = json.loads(sp.read_text(encoding="utf-8"))["selected"]["key"]
            except (ValueError, KeyError):
                sel = "unreadable"
        oos = oos_runs(rd, m)
        oos_txt = "not run" if not oos else f"run {len(oos)} time(s), first {oos[0].get('ts')}"
        lines.append(f"[{m}] variants used {used}/{cfg.variant_cap}; IS selection: {sel}; OOS: {oos_txt}")
    return "\n".join(lines)
