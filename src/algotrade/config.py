"""Load TOML config from `config/` (common.toml + <market>.toml). Unknown keys are an error.

Owner: data-engineer. Stdlib only (tomllib). Values are frozen dataclasses. Nothing here reads the process
environment: every setting comes from the TOML files.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


class ConfigError(ValueError):
    """Raised for a missing file, an unknown key, a missing key or a value of the wrong type."""


@dataclass(frozen=True)
class Costs:
    commission_rate: float
    sec_fee_rate_sell: float
    taf_per_share_sell: float
    taf_max_per_trade: float
    slippage_rate: float
    min_order_usd: float


@dataclass(frozen=True)
class Thresholds:
    sharpe_min: float
    max_dd_max: float
    underwater_months_max: int
    round_trips_min: int
    dsr_min: float


@dataclass(frozen=True)
class MarketConfig:
    """Everything one market run needs: common.toml merged with A.toml or B.toml."""
    name: str                      # "A" or "B"
    instruments: tuple[str, ...]
    sources: tuple[str, ...]
    periods_per_year: int          # 252 (A) or 365 (B)
    sigma_target: float
    is_fraction: float
    stale_after_days: int
    costs: Costs
    thresholds: Thresholds
    criteria_sha256: str
    end_date: str                  # ISO date, inclusive
    start_equity_usd: float
    rebalance_band: float
    vol_window: int
    warmup_bars: int
    wf_blocks: int
    variant_cap: int
    idle_cash_yield: float
    grid_signals: tuple[str, ...]
    grid_lookbacks: tuple[int, ...]
    grid_rebalance: tuple[str, ...]
    max_gross_exposure: float
    kill_loss_fraction: float
    data_dir: Path
    reports_dir: Path
    urls: dict[str, str]


_FLOAT, _INT, _STR = "float", "int", "str"
_STR_LIST, _INT_LIST = "list[str]", "list[int]"

_SPEC: dict[str, dict[str, str]] = {
    "criteria": {"sha256": _STR, "end_date": _STR},
    "sim": {"start_equity_usd": _FLOAT, "rebalance_band": _FLOAT, "vol_window": _INT, "warmup_bars": _INT,
            "wf_blocks": _INT, "variant_cap": _INT, "idle_cash_yield": _FLOAT},
    "grid": {"signals": _STR_LIST, "lookbacks": _INT_LIST, "rebalance": _STR_LIST},
    "risk": {"max_gross_exposure": _FLOAT, "kill_loss_fraction": _FLOAT},
    "paths": {"data_dir": _STR, "reports_dir": _STR},
    "urls": {k: _STR for k in ("binance_vision", "binance_api", "stooq", "yahoo", "fred", "bcb_sgs")},
}
_MARKET_SPEC: dict[str, dict[str, str]] = {
    "market": {"name": _STR, "instruments": _STR_LIST, "sources": _STR_LIST, "periods_per_year": _INT,
               "sigma_target": _FLOAT, "is_fraction": _FLOAT, "stale_after_days": _INT},
    "costs": {"commission_rate": _FLOAT, "sec_fee_rate_sell": _FLOAT, "taf_per_share_sell": _FLOAT,
              "taf_max_per_trade": _FLOAT, "slippage_rate": _FLOAT, "min_order_usd": _FLOAT},
    "thresholds": {"sharpe_min": _FLOAT, "max_dd_max": _FLOAT, "underwater_months_max": _INT,
                   "round_trips_min": _INT, "dsr_min": _FLOAT},
}


def _type_ok(value, kind: str) -> bool:
    if kind == _FLOAT:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == _INT:
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == _STR:
        return isinstance(value, str)
    if kind == _STR_LIST:
        return isinstance(value, list) and bool(value) and all(isinstance(v, str) for v in value)
    if kind == _INT_LIST:
        return isinstance(value, list) and bool(value) and all(isinstance(v, int) and not isinstance(v, bool) for v in value)
    return False


def _read(path: Path) -> dict:
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError as e:
        raise ConfigError(f"config file not found: {path}") from e
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path.name}: invalid TOML: {e}") from e


def _validate(doc: dict, spec: dict[str, dict[str, str]], fname: str) -> None:
    for section in doc:
        if section not in spec:
            raise ConfigError(f"{fname}: unknown section [{section}]")
    for section, keys in spec.items():
        if section not in doc:
            raise ConfigError(f"{fname}: missing section [{section}]")
        table = doc[section]
        if not isinstance(table, dict):
            raise ConfigError(f"{fname}: [{section}] must be a table")
        for k in table:
            if k not in keys:
                raise ConfigError(f"{fname}: unknown key [{section}].{k}")
        for k, kind in keys.items():
            if k not in table:
                raise ConfigError(f"{fname}: missing key [{section}].{k}")
            if not _type_ok(table[k], kind):
                raise ConfigError(f"{fname}: [{section}].{k} must be {kind}, got {table[k]!r}")


def load_config(market: str, config_dir: Path = CONFIG_DIR) -> MarketConfig:
    """Read `common.toml` and `<market>.toml`, reject unknown or missing keys, return a MarketConfig."""
    if market not in ("A", "B"):
        raise ConfigError(f"unknown market {market!r} (expected 'A' or 'B')")
    config_dir = Path(config_dir)
    common = _read(config_dir / "common.toml")
    mk = _read(config_dir / f"{market}.toml")
    _validate(common, _SPEC, "common.toml")
    _validate(mk, _MARKET_SPEC, f"{market}.toml")
    m, c = mk["market"], common
    if m["name"] != market:
        raise ConfigError(f"{market}.toml: [market].name is {m['name']!r}")
    try:
        end = dt.date.fromisoformat(c["criteria"]["end_date"])
    except ValueError as e:
        raise ConfigError(f"common.toml: [criteria].end_date is not an ISO date: {e}") from e
    if len(c["criteria"]["sha256"]) != 64:
        raise ConfigError("common.toml: [criteria].sha256 must be 64 hex characters")
    root = config_dir.parent
    s, g, r, p = c["sim"], c["grid"], c["risk"], c["paths"]
    return MarketConfig(
        name=market,
        instruments=tuple(m["instruments"]), sources=tuple(m["sources"]),
        periods_per_year=m["periods_per_year"], sigma_target=float(m["sigma_target"]),
        is_fraction=float(m["is_fraction"]), stale_after_days=m["stale_after_days"],
        costs=Costs(**{k: float(v) for k, v in mk["costs"].items()}),
        thresholds=Thresholds(sharpe_min=float(mk["thresholds"]["sharpe_min"]),
                              max_dd_max=float(mk["thresholds"]["max_dd_max"]),
                              underwater_months_max=mk["thresholds"]["underwater_months_max"],
                              round_trips_min=mk["thresholds"]["round_trips_min"],
                              dsr_min=float(mk["thresholds"]["dsr_min"])),
        criteria_sha256=c["criteria"]["sha256"], end_date=end.isoformat(),
        start_equity_usd=float(s["start_equity_usd"]), rebalance_band=float(s["rebalance_band"]),
        vol_window=s["vol_window"], warmup_bars=s["warmup_bars"], wf_blocks=s["wf_blocks"],
        variant_cap=s["variant_cap"], idle_cash_yield=float(s["idle_cash_yield"]),
        grid_signals=tuple(g["signals"]), grid_lookbacks=tuple(g["lookbacks"]), grid_rebalance=tuple(g["rebalance"]),
        max_gross_exposure=float(r["max_gross_exposure"]), kill_loss_fraction=float(r["kill_loss_fraction"]),
        data_dir=(root / p["data_dir"]), reports_dir=(root / p["reports_dir"]),
        urls=dict(c["urls"]),
    )


def criteria_sha256(path: Path | None = None) -> str:
    """sha256 of docs/success-criteria.md with CRLF normalised to LF (the form pinned in common.toml)."""
    path = path or (CONFIG_DIR.parent / "docs" / "success-criteria.md")
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def verify_criteria(cfg: MarketConfig, path: Path | None = None) -> None:
    """Raise ConfigError if the criteria file no longer matches the pinned hash."""
    actual = criteria_sha256(path)
    if actual != cfg.criteria_sha256:
        raise ConfigError(f"docs/success-criteria.md hash {actual} != pinned {cfg.criteria_sha256}")
