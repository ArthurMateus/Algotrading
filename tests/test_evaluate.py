"""Evaluate: split/WF boundaries, selection tie rules, criteria 1-8 logic (5, 7, 8 hard-coded), the IS grid run and
the one-time OOS run end to end. Synthetic data and temp report dirs only: nothing reads data/ or writes reports/."""
import dataclasses
import json

import numpy as np
import pandas as pd
import pytest

from algotrade import cli, evaluate
from algotrade.config import CONFIG_DIR, config_files_sha256, load_config
from algotrade.data import Aux, Panel, build_panel
from algotrade.evaluate import (CRIT5_X2_SHARPE_ABOVE, CRIT7_WF_SHARPE_ABOVE, EvaluationRefused, Split,
                                evaluate_criteria, make_split, select_variant, walk_forward)
from algotrade.paper import selected_variant
from algotrade.strategy import Variant
from algotrade.variants import (PREREGISTERED_KEYS, OOSAlreadyRunError, VariantCapError, distinct_variants,
                                oos_runs, runs)
from tests.synth import synth_market


def small_cfg(tmp_path, market="B", **kw):
    """The real config (real pre-registered grid) with a temp reports dir and a scaled-down warm-up so tests are
    fast. The grid cannot be scaled down: run_is checks it against the fixed variants.PREREGISTERED_KEYS."""
    base = dict(reports_dir=tmp_path, data_dir=tmp_path / "data", warmup_bars=60, vol_window=10)
    base.update(kw)
    return dataclasses.replace(load_config(market), **base)


def synth_aux(index):
    idx = pd.DatetimeIndex(index)
    bday = pd.Series(idx.dayofweek < 5, index=idx)
    return Aux(rf_per_bar=pd.Series(0.0001, index=idx), rf_available=True, ptax=pd.Series(5.0, index=idx),
               cdi_daily=pd.Series(0.0004, index=idx), cdi_business_day=bday)


def synth_panel(cfg, n=700, seed=11):
    return build_panel(synth_market(list(cfg.instruments), "2020-01-01", n, seed=seed, daily=True), "2030-01-01")


def kw(cfg, panel):
    return dict(cfg=cfg, panel=panel, aux_fn=synth_aux, min_order={s: 5.0 for s in cfg.instruments},
                lot={s: 0.00001 for s in cfg.instruments}, git_commit="test")


# ---------------------------------------------------------------- split

def test_make_split_hand_checked(tmp_path):
    cfg = small_cfg(tmp_path, warmup_bars=5, is_fraction=0.7)
    idx = pd.date_range("2024-01-01", periods=30, freq="D", name="date")
    v = pd.DataFrame({"BTCUSDT": True, "ETHUSDT": [False] * 3 + [True] * 27}, index=idx)
    px = pd.DataFrame(1.0, index=idx, columns=v.columns).where(v)
    sp = make_split(Panel(open=px, close=px, valid=v, adjusted="none"), cfg)
    # ETH's first bar is row 3; 5 real bars before -> row 8 (2024-01-09). E = rows 8..29 = 22 bars.
    assert sp.e_start == sp.is_start == "2024-01-09"
    assert (sp.n_e, sp.n_is, sp.n_oos) == (22, 15, 7)                 # floor(0.7 * 22) = 15
    assert sp.is_end == "2024-01-23" and sp.oos_start == "2024-01-24" and sp.oos_end == "2024-01-30"
    # blocks cut at floor(k * 15 / 5) = 0, 3, 6, 9, 12, 15
    assert sp.wf_blocks[0] == ("2024-01-09", "2024-01-11")
    assert sp.wf_blocks[-1] == ("2024-01-21", "2024-01-23")
    assert len(sp.wf_blocks) == 5


def test_make_split_float_floor(tmp_path):
    cfg = small_cfg(tmp_path, warmup_bars=0, is_fraction=0.7)
    idx = pd.date_range("2024-01-01", periods=10, freq="D", name="date")
    v = pd.DataFrame({"BTCUSDT": True, "ETHUSDT": True}, index=idx)
    px = pd.DataFrame(1.0, index=idx, columns=v.columns)
    assert make_split(Panel(open=px, close=px, valid=v, adjusted="none"), cfg).n_is == 7


# ---------------------------------------------------------------- selection and walk-forward

def test_select_variant_tie_rules():
    a, b = Variant("TSMOM", 126, "weekly"), Variant("SMA", 252, "weekly")
    assert select_variant({a: 0.5, b: 0.4}) == a
    assert select_variant({a: 0.5, b: 0.5}) == b                         # tie -> longer lookback
    c = Variant("SMA", 252, "monthly")
    assert select_variant({b: 0.5, c: 0.5}) == c                         # then monthly
    d = Variant("TSMOM", 252, "monthly")
    assert select_variant({c: 0.5, d: 0.5}) == d                         # then grid order (TSMOM first)
    assert select_variant({a: float("nan"), b: -3.0}) == b               # NaN ranks last


def test_walk_forward_expanding_choice_and_concatenation():
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    blocks = [(str(idx[2 * i].date()), str(idx[2 * i + 1].date())) for i in range(5)]
    split = Split("", "", "", "", "", blocks)
    x, y = "TSMOM-63-weekly", "SMA-63-weekly"
    rx = pd.Series([0.01, 0.02, -0.01, -0.03, 0.0, 0.01, 0.02, 0.0, 0.01, -0.01], index=idx)
    ry = pd.Series([0.00, 0.01, 0.03, 0.04, 0.02, 0.03, 0.01, 0.02, 0.02, 0.01], index=idx)
    rf = pd.Series(0.0, index=idx)
    wf, chosen = walk_forward({x: rx, y: ry}, rf, split, 365)
    # block 1 only: x has mean 0.015 (sd .007), y mean .005 (sd .007) -> x; afterwards y dominates
    assert chosen == [x, y, y, y]
    expected = pd.concat([rx.iloc[2:4], ry.iloc[4:10]])
    pd.testing.assert_series_equal(wf, expected, check_names=False)
    assert wf.index[0] == idx[2] and len(wf) == 8                        # blocks 2..5 only


# ---------------------------------------------------------------- criteria (§6), incl. hard-coded 5, 7, 8

def crit(th, **over):
    base = dict(sharpe=1.0, max_dd=0.10, underwater_months=6.0, round_trips=30, sharpe_x2=0.8, dsr=0.95,
                wf_sharpe=0.4, bench_sharpe=0.5, bench_max_dd=0.30)
    base.update(over)
    return {c.num: c.passed for c in evaluate_criteria(th, **base)}


def test_all_pass_baseline():
    assert all(crit(load_config("A").thresholds).values())


@pytest.mark.parametrize("market", ["A", "B"])
def test_criteria_thresholds_and_boundaries(market):
    th = load_config(market).thresholds
    assert crit(th, sharpe=th.sharpe_min)[1] and not crit(th, sharpe=th.sharpe_min - 1e-9)[1]
    assert crit(th, max_dd=th.max_dd_max, bench_max_dd=0.9)[2] and not crit(th, max_dd=th.max_dd_max + 1e-9)[2]
    assert crit(th, underwater_months=18.0)[3] and not crit(th, underwater_months=18.01)[3]
    assert crit(th, round_trips=th.round_trips_min)[4] and not crit(th, round_trips=th.round_trips_min - 1)[4]
    assert crit(th, dsr=th.dsr_min)[6] and not crit(th, dsr=0.8999)[6]


def test_criterion5_doubled_costs_strictly_positive():
    th = load_config("A").thresholds
    assert CRIT5_X2_SHARPE_ABOVE == 0.0
    assert crit(th, sharpe_x2=0.001)[5]
    assert not crit(th, sharpe_x2=0.0)[5]
    assert not crit(th, sharpe_x2=-0.2)[5]
    assert not crit(th, sharpe_x2=float("nan"))[5]


def test_criterion7_wf_sharpe_strictly_positive():
    th = load_config("B").thresholds
    assert CRIT7_WF_SHARPE_ABOVE == 0.0
    assert crit(th, wf_sharpe=1e-6)[7]
    assert not crit(th, wf_sharpe=0.0)[7]
    assert not crit(th, wf_sharpe=float("nan"))[7]


def test_criterion8_beats_benchmark_needs_both():
    th = load_config("B").thresholds
    assert crit(th, sharpe=0.6, bench_sharpe=0.6, max_dd=0.2, bench_max_dd=0.2)[8]     # equal is enough
    assert not crit(th, sharpe=0.59, bench_sharpe=0.6, max_dd=0.1, bench_max_dd=0.2)[8]
    assert not crit(th, sharpe=0.9, bench_sharpe=0.6, max_dd=0.21, bench_max_dd=0.2)[8]
    assert not crit(th, bench_sharpe=float("nan"))[8]


# ---------------------------------------------------------------- IS + OOS end to end (synthetic, temp dirs)

def test_is_then_oos_once(tmp_path):
    cfg = small_cfg(tmp_path)
    panel = synth_panel(cfg)
    with pytest.raises(EvaluationRefused):                               # OOS before IS: no selection yet
        evaluate.run_oos("B", **kw(cfg, panel))

    out = evaluate.run_is("B", **kw(cfg, panel))
    logged = runs(tmp_path, "B")
    assert len(logged) == 13 and {r["split"] for r in logged} == {"is"}  # 12 variants + benchmark
    assert sum(r["key"] == "benchmark" for r in logged) == 1
    sel = json.loads((tmp_path / "is_selection_B.json").read_text(encoding="utf-8"))
    assert sel["selected"]["key"] == out["selected"]
    assert sel["dsr"]["n_trials"] == 12 and len(sel["dsr"]["sr_trials_per_bar"]) == 12
    best = max(sel["is_sharpe"].values())
    assert sel["is_sharpe"][out["selected"]] == best
    chosen = json.loads((tmp_path / "selected-B.json").read_text(encoding="utf-8"))
    assert chosen["variant"] == out["selected"]
    assert selected_variant(cfg).key == out["selected"]                  # paper.py reads it
    is_md = (tmp_path / "backtest-B-is.md").read_text(encoding="utf-8")
    assert "| 6 |" in is_md and "| 7 |" in is_md and is_md.isascii()

    res = evaluate.run_oos("B", **kw(cfg, panel))
    assert [c.num for c in res["criteria"]] == list(range(1, 9))
    assert res["passed"] == all(c.passed for c in res["criteria"]) and not res["forced"]
    assert res["metrics"]["x2"]["cost_total"] > res["metrics"]["x1"]["cost_total"]
    assert res["metrics"]["x2"]["sharpe"] < res["metrics"]["x1"]["sharpe"]
    assert res["cdi"]["available"]
    md = (tmp_path / "backtest-B-oos.md").read_text(encoding="utf-8")
    assert md.isascii()
    for n in range(1, 9):
        assert f"| {n} | " in md
    assert "Cost breakdown" in md and "below the venue minimum" in md and "FORCED" not in md
    oos_logged = [r for r in runs(tmp_path, "B") if r["split"] == "oos" and r["kind"] != "sensitivity"]
    assert sorted((r["key"] == "benchmark", r["cost_mult"]) for r in oos_logged) == \
        [(False, 1.0), (False, 2.0), (True, 1.0)]
    # B latency sensitivity: logged once as a non-variant run, reported, not in the cap or the selection
    sens = [r for r in runs(tmp_path, "B") if r.get("kind") == "sensitivity"]
    assert len(sens) == 1 and sens[0]["key"] == f"sensitivity:close-fill:{out['selected']}"
    assert sens[0]["split"] == "oos" and sens[0]["cost_mult"] == 1.0
    assert len(distinct_variants(tmp_path, "B")) == 12
    assert res["sensitivity"]["key"] == sens[0]["key"]
    assert "sensitivity, reported only, not a criterion" in md
    for text in (is_md, md):
        assert "not pre-registered" in text and "Kill switch at 50%" in text and "Stale-data halt" in text
        assert "TSMOM-first final tie-break" in text and "cannot change a verdict" in text
        assert "Idle cash earns 0" in text and "subtracts the T-bill" in text
        assert "Spread of the 12 IS Sharpes" in text and "highly correlated" in text and "stdev" in text

    # the OOS window is touched once
    with pytest.raises(OOSAlreadyRunError):
        evaluate.run_oos("B", **kw(cfg, panel))
    with pytest.raises(OOSAlreadyRunError):
        evaluate.run_oos("B", force=True, reason="  ", **kw(cfg, panel))
    with pytest.raises(EvaluationRefused):                               # no re-selection after OOS
        evaluate.run_is("B", **kw(cfg, panel))
    forced = evaluate.run_oos("B", force=True, reason="bug fix in report formatting", **kw(cfg, panel))
    assert forced["forced"]
    assert "FORCED OOS RERUN #2" in (tmp_path / "backtest-B-oos.md").read_text(encoding="utf-8")
    assert len(oos_runs(tmp_path, "B")) == 2
    # the forced rerun gives the same numbers (deterministic)
    assert forced["metrics"]["x1"]["sharpe"] == res["metrics"]["x1"]["sharpe"]


def test_is_rerun_is_deterministic_and_does_not_add_variants(tmp_path):
    cfg = small_cfg(tmp_path)
    panel = synth_panel(cfg, seed=4)
    a = evaluate.run_is("B", **kw(cfg, panel))
    b = evaluate.run_is("B", **kw(cfg, panel))
    assert a["selected"] == b["selected"] and a["is_sharpe"] == b["is_sharpe"]
    assert a["dsr"] == b["dsr"] or (np.isnan(a["dsr"]) and np.isnan(b["dsr"]))
    assert len({r["key"] for r in runs(tmp_path, "B") if r["key"] != "benchmark"}) == 12


def test_oos_refuses_if_the_data_changed_since_is(tmp_path):
    cfg = small_cfg(tmp_path)
    evaluate.run_is("B", **kw(cfg, synth_panel(cfg)))
    longer = synth_panel(cfg, n=730)
    with pytest.raises(EvaluationRefused):
        evaluate.run_oos("B", **kw(cfg, longer))
    assert oos_runs(tmp_path, "B") == []                                 # a refused run does not use the window


def test_variant_cap_refuses_a_new_grid(tmp_path):
    cfg = small_cfg(tmp_path)
    panel = synth_panel(cfg)
    evaluate.run_is("B", **kw(cfg, panel))
    other = dataclasses.replace(cfg, grid_lookbacks=(63, 126, 200))      # a 13th+ distinct variant
    with pytest.raises(VariantCapError):
        evaluate.run_is("B", **kw(other, panel))


# ---------------------------------------------------------------- skeptic pre-flight M1: the OOS lock has 3 traces

def _is_and_oos(tmp_path, market="B"):
    cfg = small_cfg(tmp_path, market)
    panel = synth_panel(cfg)
    evaluate.run_is(market, **kw(cfg, panel))
    evaluate.run_oos(market, **kw(cfg, panel))
    return cfg, panel


def test_deleting_oos_runs_jsonl_still_refuses_oos_and_is(tmp_path):
    cfg, panel = _is_and_oos(tmp_path)
    (tmp_path / "oos_runs.jsonl").unlink()
    with pytest.raises(OOSAlreadyRunError, match="variants.jsonl"):
        evaluate.run_oos("B", **kw(cfg, panel))
    with pytest.raises(EvaluationRefused, match="OOS run already happened"):
        evaluate.run_is("B", **kw(cfg, panel))
    # with the OOS report also gone, the split=oos rows in variants.jsonl alone still lock it
    (tmp_path / "backtest-B-oos.md").unlink()
    with pytest.raises(OOSAlreadyRunError):
        evaluate.run_oos("B", **kw(cfg, panel))
    with pytest.raises(EvaluationRefused):
        evaluate.run_is("B", **kw(cfg, panel))
    assert "OOS: used" in evaluate.status(tmp_path)
    # a forced rerun is still possible, and is flagged as forced although oos_runs.jsonl was deleted
    forced = evaluate.run_oos("B", force=True, reason="test", **kw(cfg, panel))
    assert forced["forced"]
    assert "FORCED OOS RERUN #2" in (tmp_path / "backtest-B-oos.md").read_text(encoding="utf-8")


def test_the_oos_report_alone_locks_oos_and_is(tmp_path):
    cfg, panel = _is_and_oos(tmp_path)
    for f in ("oos_runs.jsonl", "variants.jsonl"):
        (tmp_path / f).unlink()
    with pytest.raises(OOSAlreadyRunError, match="backtest-B-oos.md"):
        evaluate.run_oos("B", **kw(cfg, panel))
    with pytest.raises(EvaluationRefused):
        evaluate.run_is("B", **kw(cfg, panel))


# ---------------------------------------------------------------- M2: fixed grid, pinned config files

def test_run_is_refuses_a_config_grid_outside_the_preregistered_one(tmp_path):
    cfg = small_cfg(tmp_path, grid_lookbacks=(5, 10, 20))               # 12 keys, all outside criteria s.3
    with pytest.raises(VariantCapError, match="outside the pre-registered grid"):
        evaluate.run_is("B", **kw(cfg, synth_panel(cfg)))
    assert runs(tmp_path, "B") == [] and not (tmp_path / "is_selection_B.json").exists()


def test_selection_pins_config_hashes_and_line_endings_do_not_matter(tmp_path):
    cfg = small_cfg(tmp_path)
    evaluate.run_is("B", **kw(cfg, synth_panel(cfg)))
    sel = json.loads((tmp_path / "is_selection_B.json").read_text(encoding="utf-8"))
    assert sel["config_sha256"] == config_files_sha256("B", CONFIG_DIR)
    assert set(sel["config_sha256"]) == {"common.toml", "B.toml"}
    lf, crlf = tmp_path / "lf", tmp_path / "crlf"
    for d, nl in ((lf, b"\n"), (crlf, b"\r\n")):
        d.mkdir()
        for name in ("common.toml", "B.toml"):
            raw = (CONFIG_DIR / name).read_bytes().replace(b"\r\n", b"\n")
            (d / name).write_bytes(raw.replace(b"\n", nl))
    assert config_files_sha256("B", lf) == config_files_sha256("B", crlf) == sel["config_sha256"]


def test_oos_refuses_an_edited_config(tmp_path):
    cdir = tmp_path / "config"
    cdir.mkdir()
    for name in ("common.toml", "B.toml"):
        (cdir / name).write_bytes((CONFIG_DIR / name).read_bytes())
    cfg = small_cfg(tmp_path)
    panel = synth_panel(cfg)
    evaluate.run_is("B", config_dir=cdir, **kw(cfg, panel))
    txt = (cdir / "B.toml").read_text(encoding="utf-8")
    assert "sigma_target = 0.40" in txt
    (cdir / "B.toml").write_text(txt.replace("sigma_target = 0.40", "sigma_target = 0.30"), encoding="utf-8")
    with pytest.raises(EvaluationRefused, match=r"config file\(s\) \['B.toml'\] changed since IS"):
        evaluate.run_oos("B", config_dir=cdir, **kw(cfg, panel))
    assert oos_runs(tmp_path, "B") == [] and not [r for r in runs(tmp_path, "B") if r["split"] == "oos"]


# ---------------------------------------------------------------- M3: data, venue filters, selection re-derived

def _write_manifest(cfg, shas):
    d = cfg.data_dir / "bars" / cfg.name
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps({s: {"sha256": h} for s, h in shas.items()}), encoding="utf-8")


def test_oos_refuses_if_the_cached_bar_files_changed(tmp_path):
    cfg = small_cfg(tmp_path)
    panel = synth_panel(cfg)
    _write_manifest(cfg, {"BTCUSDT": "a" * 64, "ETHUSDT": "b" * 64})
    evaluate.run_is("B", **kw(cfg, panel))
    sel = json.loads((tmp_path / "is_selection_B.json").read_text(encoding="utf-8"))
    assert sel["data"]["bars_manifest_sha256"] == {"BTCUSDT": "a" * 64, "ETHUSDT": "b" * 64}
    _write_manifest(cfg, {"BTCUSDT": "a" * 64, "ETHUSDT": "c" * 64})        # e.g. a re-fetch
    with pytest.raises(EvaluationRefused, match="cached bar files"):
        evaluate.run_oos("B", **kw(cfg, panel))
    assert oos_runs(tmp_path, "B") == []


def test_oos_refuses_if_prices_changed_with_the_same_dates(tmp_path):
    cfg = small_cfg(tmp_path)
    panel = synth_panel(cfg)
    evaluate.run_is("B", **kw(cfg, panel))
    close = panel.close.copy()
    close.iloc[-5, 0] *= 1.01                                           # rewritten history, same calendar
    changed = Panel(open=panel.open, close=close, valid=panel.valid, adjusted=panel.adjusted)
    assert make_split(changed, cfg) == make_split(panel, cfg)
    with pytest.raises(EvaluationRefused, match="panel content"):
        evaluate.run_oos("B", **kw(cfg, changed))
    assert oos_runs(tmp_path, "B") == []


def test_oos_refuses_if_the_venue_filters_changed(tmp_path):
    cfg = small_cfg(tmp_path)
    panel = synth_panel(cfg)
    evaluate.run_is("B", **kw(cfg, panel))
    k = kw(cfg, panel)
    k["min_order"] = {s: 10.0 for s in cfg.instruments}                 # exchangeInfo NOTIONAL changed
    with pytest.raises(EvaluationRefused, match="venue filters"):
        evaluate.run_oos("B", **k)
    assert oos_runs(tmp_path, "B") == []


def _edit_selection(tmp_path, fn):
    p = tmp_path / "is_selection_B.json"
    sel = json.loads(p.read_text(encoding="utf-8"))
    fn(sel)
    p.write_text(json.dumps(sel), encoding="utf-8")


def _set_selected_file(tmp_path, key):
    sp = tmp_path / "selected-B.json"
    chosen = json.loads(sp.read_text(encoding="utf-8"))
    chosen["variant"] = key
    sp.write_text(json.dumps(chosen), encoding="utf-8")


def test_oos_refuses_a_hand_edited_selection(tmp_path):
    cfg = small_cfg(tmp_path)
    panel = synth_panel(cfg)
    out = evaluate.run_is("B", **kw(cfg, panel))
    other = next(k for k in PREREGISTERED_KEYS if k != out["selected"])
    v = evaluate._parse_key(other)

    def swap(sel):
        sel["selected"] = {"key": other, "signal": v.signal, "lookback": v.lookback, "rebalance": v.rebalance}
    _edit_selection(tmp_path, swap)
    _set_selected_file(tmp_path, other)
    with pytest.raises(EvaluationRefused, match="re-applying the selection rule"):
        evaluate.run_oos("B", **kw(cfg, panel))
    assert oos_runs(tmp_path, "B") == []


def test_oos_refuses_edited_is_sharpes(tmp_path):
    cfg = small_cfg(tmp_path)
    panel = synth_panel(cfg)
    out = evaluate.run_is("B", **kw(cfg, panel))
    other = next(k for k in PREREGISTERED_KEYS if k != out["selected"])
    _edit_selection(tmp_path, lambda sel: sel["is_sharpe"].__setitem__(other, 99.0))
    with pytest.raises(EvaluationRefused, match=f"gives {other}"):
        evaluate.run_oos("B", **kw(cfg, panel))
    _edit_selection(tmp_path, lambda sel: sel["is_sharpe"].pop(other))  # only 11 Sharpes: refused too
    with pytest.raises(EvaluationRefused, match="pre-registered"):
        evaluate.run_oos("B", **kw(cfg, panel))
    assert oos_runs(tmp_path, "B") == []


def test_oos_refuses_if_the_selected_file_disagrees(tmp_path):
    cfg = small_cfg(tmp_path)
    panel = synth_panel(cfg)
    out = evaluate.run_is("B", **kw(cfg, panel))
    _set_selected_file(tmp_path, next(k for k in PREREGISTERED_KEYS if k != out["selected"]))
    with pytest.raises(EvaluationRefused, match="selected-B.json"):
        evaluate.run_oos("B", **kw(cfg, panel))
    assert oos_runs(tmp_path, "B") == []


def test_rederive_selection_and_sharpe_spread():
    sh = {k: 0.1 for k in PREREGISTERED_KEYS}
    sh["SMA-126-weekly"] = 0.5
    assert evaluate.rederive_selection(sh) == "SMA-126-weekly"
    sh["SMA-126-weekly"] = None                                         # NaN last; tie -> 252, monthly, TSMOM
    assert evaluate.rederive_selection(sh) == "TSMOM-252-monthly"
    with pytest.raises(EvaluationRefused):
        evaluate.rederive_selection({"TSMOM-252-monthly": 0.1})
    sp = evaluate.sharpe_spread({"a": 1.0, "b": 3.0, "c": 2.0, "d": None, "e": float("nan")})
    assert sp == {"n": 3, "min": 1.0, "median": 2.0, "max": 3.0, "stdev": 1.0}


def test_market_a_has_no_latency_sensitivity_run(tmp_path):
    _is_and_oos(tmp_path, "A")
    assert not [r for r in runs(tmp_path, "A") if r.get("kind") == "sensitivity"]
    md = (tmp_path / "backtest-A-oos.md").read_text(encoding="utf-8")
    assert "Latency sensitivity" not in md and "not pre-registered" in md


def test_status_reports_temp_dir(tmp_path):
    txt = evaluate.status(tmp_path)
    assert "[A] variants used 0/12" in txt and "OOS: not run" in txt


# ---------------------------------------------------------------- CLI argument handling (returns before any run)

def test_cli_backtest_bad_arguments():
    assert cli.main(["backtest", "--market", "A", "--split", "is", "--force"]) == 2
    assert cli.main(["backtest", "--market", "B", "--split", "oos", "--force"]) == 2
    assert cli.main(["backtest", "--market", "C", "--split", "is"]) == 2
