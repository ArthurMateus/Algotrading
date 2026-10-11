"""Config vs pre-registered criteria (docs/success-criteria.md, read-only here).

Numbers are extracted from the markdown where practical (tables, bullets). Where the prose is not machine-friendly
the expected value sits in an explicit table that cites the criteria section. Either way the config must match.
"""
import re
from pathlib import Path

import pytest

from algotrade.config import load_config, verify_criteria

ROOT = Path(__file__).resolve().parent.parent
TEXT = (ROOT / "docs" / "success-criteria.md").read_text(encoding="utf-8").replace("\r\n", "\n")


def _section(n: int) -> str:
    m = re.search(rf"^## {n}\. .*?(?=^## |\Z)", TEXT, re.S | re.M)
    assert m, f"section {n} not found in criteria"
    return m.group(0)


def _row(section: str, label_prefix: str) -> list[str]:
    """Cells of the markdown table row whose first cell starts with label_prefix."""
    for line in section.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells[0] == label_prefix.strip() if label_prefix.strip().isdigit() else cells[0].startswith(label_prefix):
                return cells
    raise AssertionError(f"table row {label_prefix!r} not found")


def _num(cell: str) -> float:
    m = re.search(r"\*\*(?:[^0-9*]*?)([0-9][0-9.,]*)", cell) or re.search(r"([0-9][0-9.,]*)", cell)
    assert m, f"no number in {cell!r}"
    return float(m.group(1).replace(",", ""))


@pytest.fixture(scope="module")
def A():
    return load_config("A")


@pytest.fixture(scope="module")
def B():
    return load_config("B")


# --- pin ---------------------------------------------------------------------------------------------------

def test_sha256_pin_matches_criteria_file(A, B):
    verify_criteria(A)
    verify_criteria(B)
    assert A.criteria_sha256 == B.criteria_sha256


# --- section 1: universe and period -------------------------------------------------------------------------

def test_universe_tickers_match_section_1(A, B):
    row = _row(_section(1), "Instruments")
    a_tickers = re.findall(r"\b[A-Z]{3,4}\b(?= \()", row[1])          # "SPY (US equity)", ...
    assert tuple(a_tickers) == A.instruments == ("SPY", "EFA", "IEF", "GLD", "DBC")
    b_tickers = re.findall(r"[A-Z]+USDT", row[2])
    assert tuple(b_tickers) == B.instruments == ("BTCUSDT", "ETHUSDT")


def test_period_end_and_warmup_match_sections_1_2(A, B):
    s1 = _section(1)
    assert s1.count("2026-09-30") >= 2          # both markets end on this date
    assert A.end_date == B.end_date == "2026-09-30"
    assert "first 252 bars are indicator warm-up" in _section(2)
    assert A.warmup_bars == B.warmup_bars == 252


def test_sources_are_the_ones_named_in_section_1(A, B):
    row = _row(_section(1), "Source")
    assert "Stooq" in row[1] and "Yahoo" in row[1]
    assert A.sources == ("stooq", "yahoo")      # "Stooq CSV, then the Yahoo chart endpoint" = tried in order
    assert "data.binance.vision" in row[2] and "1d" in row[2]
    assert B.sources == ("binance_vision",)


# --- section 2: split and walk-forward ----------------------------------------------------------------------

def test_split_fractions_match_section_2(A, B):
    s2 = _section(2)
    a = re.search(r"\*\*A:\*\*.*?first (\d+)%.*?last (\d+)%", s2, re.S)
    b = re.search(r"\*\*B:\*\* IS = the first (\d+)%", s2)
    assert a and b
    assert (int(a.group(1)), int(a.group(2))) == (70, 30)
    assert A.is_fraction == int(a.group(1)) / 100 == 0.70
    assert B.is_fraction == int(b.group(1)) / 100 == 0.60
    assert round(1 - B.is_fraction, 10) == 0.40


def test_walk_forward_blocks_match_section_2(A, B):
    s2 = _section(2)
    m = re.search(r"split IS into (\d+) equal consecutive blocks", s2)
    assert m and int(m.group(1)) == 5
    assert A.wf_blocks == B.wf_blocks == 5
    assert "k = 2..5" in s2                      # blocks 2..5 are traded, so 5 blocks


# --- section 3: strategy family, grid, cap, sizing ----------------------------------------------------------

def test_grid_matches_section_3(A, B):
    s3 = _section(3)
    sig = _row(s3, "Signal")[1]
    lb = _row(s3, "Lookback")[1]
    rb = _row(s3, "Rebalance")[1]
    signals = tuple(re.findall(r"[A-Z]{3,}", sig))
    lookbacks = tuple(int(x) for x in re.findall(r"\d+", lb.split("}")[0]))
    rebalance = tuple(re.findall(r"(weekly|monthly)", rb))
    assert signals == ("TSMOM", "SMA")
    assert lookbacks == (63, 126, 252)
    assert rebalance == ("weekly", "monthly")
    for cfg in (A, B):
        assert cfg.grid_signals == signals
        assert cfg.grid_lookbacks == lookbacks
        assert cfg.grid_rebalance == rebalance


def test_variant_cap_is_12_and_equals_grid_size(A, B):
    s3 = _section(3)
    m = re.search(r"Hard cap: (\d+) variants per market \((\d+) in total\)", s3.replace("**", ""))
    assert m and (int(m.group(1)), int(m.group(2))) == (12, 24)
    for cfg in (A, B):
        assert cfg.variant_cap == 12
        assert len(cfg.grid_signals) * len(cfg.grid_lookbacks) * len(cfg.grid_rebalance) == cfg.variant_cap


def test_vol_targets_and_window_match_section_3(A, B):
    s3 = _section(3)
    m = re.search(r"σ\* = \*\*(\d+)%\*\* for A and\s+\*\*(\d+)%\*\* for B", s3)
    assert m
    assert A.sigma_target == int(m.group(1)) / 100 == 0.12
    assert B.sigma_target == int(m.group(2)) / 100 == 0.40
    w = re.search(r"last (\d+) daily log returns", s3)
    assert w and int(w.group(1)) == 60
    assert A.vol_window == B.vol_window == 60
    ann = re.search(r"×√(\d+) for A, ×√(\d+) for B", s3)
    assert ann and (A.periods_per_year, B.periods_per_year) == (int(ann.group(1)), int(ann.group(2))) == (252, 365)


def test_no_leverage_and_idle_cash_earns_zero(A, B):
    s3 = _section(3)
    assert "No leverage" in s3 and "gross exposure is ≤ 100%" in s3
    assert "Idle cash earns 0" in s3
    for cfg in (A, B):
        assert cfg.max_gross_exposure <= 1.0
        assert cfg.idle_cash_yield == 0.0


def test_rebalance_band_and_start_equity_match_section_3(A, B):
    s3 = _section(3)
    band = re.search(r"\|Δweight\| ≥ (\d+)% of equity", s3)
    assert band and int(band.group(1)) == 2
    eq = re.search(r"start equity is \*\*\$(\d+)\*\*", s3)
    assert eq and int(eq.group(1)) == 300
    for cfg in (A, B):
        assert cfg.rebalance_band == 0.02
        assert cfg.start_equity_usd == 300.0


# --- section 4: cost model ----------------------------------------------------------------------------------

def test_commission_matches_section_4(A, B):
    row = _row(_section(4), "Commission")
    assert row[1].startswith("$0") and A.costs.commission_rate == 0.0
    m = re.match(r"([0-9.]+)% per side", row[2])
    assert m and float(m.group(1)) == 0.10
    assert B.costs.commission_rate == pytest.approx(0.0010)


def test_regulatory_fees_match_section_4(A, B):
    row = _row(_section(4), "Regulatory")
    sec = re.search(r"SEC ([0-9.]+)%", row[1])
    taf = re.search(r"TAF \$([0-9.]+)/share, max \$([0-9.]+)", row[1])
    assert sec and taf
    assert A.costs.sec_fee_rate_sell == pytest.approx(float(sec.group(1)) / 100) == pytest.approx(0.0000206)
    assert A.costs.taf_per_share_sell == pytest.approx(float(taf.group(1))) == pytest.approx(0.000119)
    assert A.costs.taf_max_per_trade == pytest.approx(float(taf.group(2))) == pytest.approx(5.95)
    assert row[2].lower() == "none"
    assert (B.costs.sec_fee_rate_sell, B.costs.taf_per_share_sell, B.costs.taf_max_per_trade) == (0.0, 0.0, 0.0)


def test_slippage_matches_section_4(A, B):
    row = _row(_section(4), "Slippage")
    a = re.search(r"\*\*([0-9.]+)% per side\*\*", row[1])
    b = re.search(r"\*\*([0-9.]+)% per side\*\*", row[2])
    assert a and b
    assert A.costs.slippage_rate == pytest.approx(float(a.group(1)) / 100) == pytest.approx(0.0010)
    assert B.costs.slippage_rate == pytest.approx(float(b.group(1)) / 100) == pytest.approx(0.0005)


def test_round_trip_cost_is_consistent_with_section_4(A, B):
    row = _row(_section(4), "Round trip")
    assert "0.20%" in row[1] and "0.30%" in row[2]
    # A: 2 * slippage (commission 0; regulatory sell-side fees are extra and tiny). B: 2 * (commission + slippage).
    assert 2 * A.costs.slippage_rate == pytest.approx(0.0020)
    assert 2 * (B.costs.commission_rate + B.costs.slippage_rate) == pytest.approx(0.0030)


def test_minimum_order_matches_section_4(A, B):
    row = _row(_section(4), "Minimum order")
    assert "**$1**" in row[1] and A.costs.min_order_usd == 1.0
    assert "**$10**" in row[2] and B.costs.min_order_usd == 10.0


def test_doubled_cost_multiplier_is_2_in_criteria_and_round_trips(A, B):
    s4 = _section(4)
    assert "every fee and slippage figure ×2" in s4
    assert "A ≈ 0.40%, B ≈ 0.60%" in s4
    mult = 2.0                                           # §4 stress run: all fee and slippage figures x2
    assert mult * 2 * A.costs.slippage_rate == pytest.approx(0.0040)
    assert mult * 2 * (B.costs.commission_rate + B.costs.slippage_rate) == pytest.approx(0.0060)


# --- section 5: benchmarks ----------------------------------------------------------------------------------

def test_benchmark_definitions_match_section_5(A, B):
    s5 = _section(5)
    assert "equal-weight buy-and-hold of the 5 ETFs, rebalanced at the first open of each month" in s5
    assert len(A.instruments) == 5
    assert "50/50 BTC/ETH, rebalanced monthly" in s5
    assert B.instruments == ("BTCUSDT", "ETHUSDT")
    assert "Both benchmarks start at $300" in s5
    assert A.start_equity_usd == B.start_equity_usd == 300.0


# --- section 6: thresholds ----------------------------------------------------------------------------------

def _thr(label: str) -> tuple[str, str]:
    row = _row(_section(6), label)
    return row[2], row[3]


def test_threshold_1_sharpe(A, B):
    a, b = _thr("1 ")
    assert (_num(a), _num(b)) == (0.40, 0.50)
    assert (A.thresholds.sharpe_min, B.thresholds.sharpe_min) == (0.40, 0.50)


def test_threshold_2_max_drawdown(A, B):
    a, b = _thr("2 ")
    assert (_num(a) / 100, _num(b) / 100) == (0.20, 0.35)
    assert (A.thresholds.max_dd_max, B.thresholds.max_dd_max) == (0.20, 0.35)


def test_threshold_3_underwater_months(A, B):
    a, b = _thr("3 ")
    assert "months" in a and "months" in b
    assert (_num(a), _num(b)) == (18, 18)
    assert A.thresholds.underwater_months_max == B.thresholds.underwater_months_max == 18


def test_threshold_4_round_trips(A, B):
    a, b = _thr("4 ")
    assert (_num(a), _num(b)) == (20, 12)
    assert (A.thresholds.round_trips_min, B.thresholds.round_trips_min) == (20, 12)


def test_threshold_5_doubled_costs_and_7_walk_forward_are_zero_floors():
    a5, b5 = _thr("5 ")
    assert a5 == b5 == "required"
    a7, b7 = _thr("7 ")
    assert a7.startswith("> **0**") and b7.startswith("> **0**")
    # No config keys exist for these: the evaluator hard-codes ">0". If a key is ever added, extend this test.


def test_threshold_6_deflated_sharpe(A, B):
    a, b = _thr("6 ")
    assert (_num(a), _num(b)) == (0.90, 0.90)
    assert (A.thresholds.dsr_min, B.thresholds.dsr_min) == (0.90, 0.90)
    assert "N = variants tried (≤ 12)" in _row(_section(6), "6 ")[1]


def test_threshold_8_benchmark_rule_text():
    a, b = _thr("8 ")
    assert a == b == "required"
    row = _row(_section(6), "8 ")[1]
    assert "Sharpe ≥ benchmark Sharpe" in row and "max drawdown ≤ benchmark max drawdown" in row


def test_all_eight_criteria_exist_and_each_market_needs_all():
    s6 = _section(6)
    assert [int(_row(s6, f"{i} ")[0].split()[0]) for i in range(1, 9)] == list(range(1, 9))
    assert "each market PASSES only if all 8 criteria hold" in s6


# --- cross-checks -------------------------------------------------------------------------------------------

def test_dollar_drawdown_allowances_in_section_7_follow_from_thresholds(A, B):
    s7 = _section(7)
    assert "**$60 (A)**" in s7 and "**$105 (B)**" in s7
    assert A.thresholds.max_dd_max * A.start_equity_usd == pytest.approx(60)
    assert B.thresholds.max_dd_max * B.start_equity_usd == pytest.approx(105)
    assert A.start_equity_usd / len(A.instruments) == 60       # "$300 / 5 = $60 per sleeve"
