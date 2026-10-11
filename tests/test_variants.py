"""Variant log: JSONL + markdown, the 12-per-market cap, grid-only keys, and the one-time OOS guard."""
import json
import re
from pathlib import Path

import pytest

from algotrade.config import load_config
from algotrade.variants import (BENCHMARK_KEY, PREREGISTERED_KEYS, PREREGISTERED_LOOKBACKS,
                                PREREGISTERED_REBALANCE, PREREGISTERED_SIGNALS, OOSAlreadyRunError, VariantCapError,
                                check_cap, check_oos, distinct_variants, oos_evidence, oos_runs, record_oos,
                                record_run, runs)

ROOT = Path(__file__).resolve().parent.parent


def grid_keys():
    cfg = load_config("A")
    return [f"{s}-{l}-{r}" for s in cfg.grid_signals for l in cfg.grid_lookbacks for r in cfg.grid_rebalance]


def test_grid_has_12_keys():
    assert len(grid_keys()) == 12 == load_config("B").variant_cap


def test_record_run_writes_jsonl_and_markdown(tmp_path):
    record_run(tmp_path, "A", "TSMOM-252-monthly", "is", 1.0, {"sharpe": 0.5, "max_dd": float("nan")}, "abc123def4567")
    record_run(tmp_path, "A", "TSMOM-252-monthly", "oos", 2.0, {"sharpe": 0.25}, "abc123def4567")
    rows = [json.loads(line) for line in (tmp_path / "variants.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[0]["market"] == "A" and rows[0]["key"] == "TSMOM-252-monthly" and rows[0]["split"] == "is"
    assert rows[0]["metrics"] == {"sharpe": 0.5, "max_dd": None}        # NaN is stored as null (valid JSON)
    assert rows[1]["cost_mult"] == 2.0 and rows[0]["git_commit"] == "abc123def4567"
    assert rows[0]["ts"].endswith("Z")
    md = (tmp_path / "variants.md").read_text(encoding="utf-8")
    assert md.startswith("# Variant log")
    assert md.count("| A | TSMOM-252-monthly |") == 2
    assert "sharpe=0.5, max_dd=nan" in md
    assert md.isascii()


def test_reruns_splits_and_cost_mults_do_not_add_variants(tmp_path):
    for split in ("is", "oos"):
        for m in (1.0, 2.0):
            record_run(tmp_path, "A", "SMA-63-weekly", split, m, {}, "c")
    record_run(tmp_path, "A", BENCHMARK_KEY, "oos", 1.0, {}, "c")
    record_run(tmp_path, "B", "SMA-126-weekly", "is", 1.0, {}, "c")
    assert distinct_variants(tmp_path, "A") == {"SMA-63-weekly"}
    assert distinct_variants(tmp_path, "B") == {"SMA-126-weekly"}
    assert len(runs(tmp_path, "A")) == 5


def test_cap_allows_full_grid_and_refuses_outside_grid(tmp_path):
    keys = grid_keys()
    check_cap(tmp_path, "A", keys, keys, 12)
    for k in keys:
        record_run(tmp_path, "A", k, "is", 1.0, {}, "c")
    check_cap(tmp_path, "A", keys, keys, 12)                         # identical rerun is fine
    with pytest.raises(VariantCapError, match="outside"):
        check_cap(tmp_path, "A", ["TSMOM-200-monthly"], keys, 12)     # a 13th key (not in the grid)
    with pytest.raises(VariantCapError, match="outside"):
        check_cap(tmp_path, "A", ["benchmark"], keys, 12)
    check_cap(tmp_path, "B", keys, keys, 12)                         # B's count is separate


def test_cap_refuses_13th_distinct_variant(tmp_path):
    allowed = grid_keys() + ["EXTRA-1-weekly"]                       # even if a 13th key were allowed
    for k in grid_keys():
        record_run(tmp_path, "B", k, "is", 1.0, {}, "c")
    with pytest.raises(VariantCapError, match="exceed the cap of 12"):
        check_cap(tmp_path, "B", ["EXTRA-1-weekly"], allowed, 12)


def test_cap_counts_the_batch_itself(tmp_path):
    allowed = [f"K{i}" for i in range(20)]
    with pytest.raises(VariantCapError):
        check_cap(tmp_path, "A", allowed[:13], allowed, 12)


def test_torn_last_line_ignored(tmp_path):
    record_run(tmp_path, "A", "SMA-63-weekly", "is", 1.0, {}, "c")
    with open(tmp_path / "variants.jsonl", "a", encoding="utf-8") as fh:
        fh.write('{"market": "A", "key": "SMA-1')
    assert distinct_variants(tmp_path, "A") == {"SMA-63-weekly"}


def test_oos_runs_once(tmp_path):
    check_oos(tmp_path, "A", force=False)                            # never run: allowed
    record_oos(tmp_path, "A", "TSMOM-252-monthly", False, "", "c1")
    with pytest.raises(OOSAlreadyRunError):
        check_oos(tmp_path, "A", force=False)
    with pytest.raises(OOSAlreadyRunError, match="reason"):
        check_oos(tmp_path, "A", force=True, reason="   ")
    check_oos(tmp_path, "A", force=True, reason="bug fix in the fill price")
    check_oos(tmp_path, "B", force=False)                            # per market
    record_oos(tmp_path, "A", "TSMOM-252-monthly", True, "bug fix in the fill price", "c2")
    rows = oos_runs(tmp_path, "A")
    assert [r["run_number"] for r in rows] == [1, 2]
    assert rows[1]["forced"] is True and rows[1]["reason"] == "bug fix in the fill price"
    assert oos_runs(tmp_path, "B") == []


# ---------------------------------------------------------------- skeptic pre-flight M1 / M2 / m1

def test_preregistered_grid_constant_matches_the_criteria_text():
    text = (ROOT / "docs" / "success-criteria.md").read_text(encoding="utf-8")

    def row(name):
        m = re.search(r"^\| " + name + r"[^|]*\| \{([^}]*)\}", text, re.M)
        return [x.strip() for x in m.group(1).split(",")]
    assert tuple(row("Signal")) == PREREGISTERED_SIGNALS
    assert tuple(int(x) for x in row("Lookback")) == PREREGISTERED_LOOKBACKS
    assert tuple(x.split(" ")[0] for x in row("Rebalance")) == PREREGISTERED_REBALANCE
    assert len(PREREGISTERED_KEYS) == 12 == len(set(PREREGISTERED_KEYS))
    assert sorted(PREREGISTERED_KEYS) == sorted(grid_keys())


def test_check_cap_against_the_fixed_grid_refuses_an_edited_config_grid(tmp_path):
    edited = [f"{s}-{lb}-{r}" for s in ("TSMOM", "SMA") for lb in (50, 100, 200) for r in ("weekly", "monthly")]
    with pytest.raises(VariantCapError, match="outside"):
        check_cap(tmp_path, "A", edited, PREREGISTERED_KEYS, 12)       # refused before anything is logged
    with pytest.raises(VariantCapError, match="outside"):
        check_cap(tmp_path, "A", ["sensitivity:close-fill:TSMOM-252-monthly"], PREREGISTERED_KEYS, 12)


def test_oos_evidence_from_variants_log_or_report_without_oos_runs_file(tmp_path):
    assert oos_evidence(tmp_path, "A") == []
    record_run(tmp_path, "A", "TSMOM-252-monthly", "is", 1.0, {}, "c")
    check_oos(tmp_path, "A", force=False)                            # IS rows are not OOS evidence
    record_run(tmp_path, "A", "TSMOM-252-monthly", "oos", 1.0, {}, "c")
    assert not (tmp_path / "oos_runs.jsonl").exists()
    with pytest.raises(OOSAlreadyRunError, match="variants.jsonl"):
        check_oos(tmp_path, "A", force=False)
    check_oos(tmp_path, "B", force=False)                            # per market
    (tmp_path / "backtest-B-oos.md").write_text("x", encoding="utf-8")
    with pytest.raises(OOSAlreadyRunError, match="backtest-B-oos.md"):
        check_oos(tmp_path, "B", force=False)
    check_oos(tmp_path, "B", force=True, reason="documented reason")


def test_sensitivity_runs_are_not_variants(tmp_path):
    for k in grid_keys():
        record_run(tmp_path, "B", k, "is", 1.0, {}, "c")
    record_run(tmp_path, "B", "sensitivity:close-fill:SMA-63-weekly", "oos", 1.0, {"sharpe": 0.1}, "c",
               kind="sensitivity")
    rows = runs(tmp_path, "B")
    assert rows[-1]["kind"] == "sensitivity" and rows[0]["kind"] == "variant"
    assert len(distinct_variants(tmp_path, "B")) == 12
    check_cap(tmp_path, "B", grid_keys(), PREREGISTERED_KEYS, 12)    # the cap still allows an identical rerun
    with pytest.raises(ValueError):
        record_run(tmp_path, "B", "SMA-63-weekly", "oos", 1.0, {}, "c", kind="sensitivity")
    with pytest.raises(ValueError):
        record_run(tmp_path, "B", "sensitivity:x", "oos", 1.0, {}, "c", kind="variant")


def test_record_oos_stores_the_selection_commit(tmp_path):
    record_oos(tmp_path, "A", "TSMOM-252-monthly", False, "", "c2", selection_commit="c1")
    assert oos_runs(tmp_path, "A")[0]["selection_commit"] == "c1"
