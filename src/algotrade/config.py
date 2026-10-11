"""Load TOML config from `config/` (common.toml + <market>.toml). Unknown keys are an error.

Owner: data-engineer. Stdlib only (tomllib). Values are frozen dataclasses. Nothing here reads the process
environment: every setting comes from the TOML files.
"""
from __future__ import annotations

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


def load_config(market: str, config_dir: Path = CONFIG_DIR) -> MarketConfig:
    """Read `common.toml` and `<market>.toml`, reject unknown or missing keys, return a MarketConfig."""
    raise NotImplementedError
