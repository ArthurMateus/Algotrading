"""RiskGate: caps, no shorts, no leverage, stale-data halt, kill switch; exits never refused (docs/SPEC.md §5)."""
from __future__ import annotations

import datetime as dt
import math

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from algotrade.broker import Order
from algotrade.config import load_config
from algotrade.risk import (BAD_ORDER, BAD_QTY, CAP, CASH, KILLED, NO_PRICE, NO_SHORT, STALE, TOL, UNKNOWN, GateView,
                            RiskGate, Verdict)

CFG = {m: load_config(m) for m in ("A", "B")}
D0 = dt.date(2024, 1, 2)


def day(n: int) -> str:
    return (D0 + dt.timedelta(days=n)).isoformat()


def order(sym: str, side: str = "buy", kind: str = "entry", w: float = 0.2) -> Order:
    return Order(symbol=sym, side=side, kind=kind, target_weight=w, decision_date=day(-1), fill_date=day(0))


def view(cfg, *, cash=300.0, positions=None, prices=None, lag=0, killed=False, equity=None, start=300.0,
         date=None) -> GateView:
    positions = dict(positions or {})
    prices = dict(prices or {s: 100.0 for s in cfg.instruments})
    eq = cash + sum(q * prices[s] for s, q in positions.items()) if equity is None else equity
    date = date or day(10)
    last = {s: (dt.date.fromisoformat(date) - dt.timedelta(days=lag)).isoformat() for s in cfg.instruments}
    return GateView(date=date, equity=eq, start_equity=start, cash=cash, positions=positions, prices=prices,
                    last_bar_date=last, killed=killed)


# ---- config-driven values ---------------------------------------------------------------------------------------

def test_config_values_used_by_gate():
    a, b = RiskGate(CFG["A"]), RiskGate(CFG["B"])
    assert a.instrument_cap == pytest.approx(1 / 5) and b.instrument_cap == pytest.approx(1 / 2)
    assert a.stale_after_days == 5 and b.stale_after_days == 2          # SPEC §11.11, config/A.toml, B.toml
    assert a.kill_fraction == 0.5 and a.max_gross == 1.0                 # config/common.toml [risk]


def test_rejects_leverage_config():
    from dataclasses import replace
    with pytest.raises(ValueError):
        RiskGate(replace(CFG["A"], max_gross_exposure=1.5))
    with pytest.raises(ValueError):
        RiskGate(replace(CFG["A"], kill_loss_fraction=0.0))


# ---- entries ----------------------------------------------------------------------------------------------------

def test_entry_at_exactly_one_over_n_passes_and_above_fails():
    g, cfg = RiskGate(CFG["A"]), CFG["A"]
    v = view(cfg)
    qty = 0.2 * 300.0 / 100.0                     # 1/N of equity at the open
    assert g.check(order("SPY"), qty, v) == Verdict(True, "", qty)
    assert g.check(order("SPY"), qty * 1.001, v).rule == CAP


def test_increase_counts_held_quantity_for_cap():
    cfg = CFG["A"]
    g = RiskGate(cfg)
    v = view(cfg, cash=250.0, positions={"SPY": 0.5})       # SPY worth 50 of 300
    assert g.check(order("SPY", kind="rebalance"), 0.1, v).allowed
    assert g.check(order("SPY", kind="rebalance"), 0.11, v).rule == CAP


def test_cash_rule_includes_costs_and_cost_mult():
    cfg = CFG["B"]                                            # 0.10% commission + 0.05% slippage
    v = view(cfg, cash=100.0, positions={"BTCUSDT": 2.0})     # equity 300, cap 150
    q_ok = 100.0 / (100.0 * (1.0005) * (1.001)) * (1 - 1e-6)
    assert RiskGate(cfg).check(order("ETHUSDT"), q_ok, v).allowed
    assert RiskGate(cfg).check(order("ETHUSDT"), 1.0 * 1.0001, v).rule == CASH   # notional 100 + costs > 100
    q_x2 = 100.0 / (100.0 * (1.001) * (1.002)) * (1 + 1e-6)                        # fits at x1, not at x2
    assert RiskGate(cfg).check(order("ETHUSDT"), q_x2, v).allowed
    assert RiskGate(cfg, cost_mult=2.0).check(order("ETHUSDT"), q_x2, v).rule == CASH


def test_entries_fail_closed_on_bad_inputs():
    cfg = CFG["A"]
    g = RiskGate(cfg)
    v = view(cfg)
    assert g.check(order("TSLA"), 0.1, v).rule == UNKNOWN
    for q in (0.0, -1.0, math.nan, math.inf):
        assert g.check(order("SPY"), q, v).rule == BAD_QTY
    for p in (None, 0.0, -1.0, math.nan):
        prices = dict(v.prices)
        if p is None:
            prices.pop("SPY")
        else:
            prices["SPY"] = p
        assert g.check(order("SPY"), 0.1, view(cfg, prices=prices)).rule == NO_PRICE
    # a held symbol without a price makes equity unknown: refuse
    prices = dict(v.prices)
    prices.pop("GLD")
    vv = GateView(v.date, 300.0, 300.0, 250.0, {"GLD": 0.5}, prices, v.last_bar_date, False)
    assert g.check(order("SPY"), 0.1, vv).rule == NO_PRICE
    assert not g.check(order("SPY"), 0.1, view(cfg, equity=math.nan)).allowed
    assert not g.check(order("SPY"), 0.1, view(cfg, cash=-1.0, positions={"GLD": 0.5})).allowed
    assert g.check(order("SPY", kind="exit"), 0.1, v).rule == BAD_ORDER          # a buy cannot be an exit
    assert g.check(order("SPY", side="hold"), 0.1, v).rule == BAD_ORDER


def test_equity_is_the_conservative_of_view_and_computed():
    cfg = CFG["A"]
    g = RiskGate(cfg)
    v = view(cfg, equity=1000.0)                              # engine claims more than cash + positions (300)
    assert g.check(order("SPY"), 0.6, v).allowed              # 60 = 1/5 of 300
    assert g.check(order("SPY"), 0.61, v).rule == CAP


# ---- stale data -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("market,limit", [("A", 5), ("B", 2)])
def test_stale_data_halt(market, limit):
    cfg = CFG[market]
    g = RiskGate(cfg)
    sym = cfg.instruments[0]
    assert g.check(order(sym), 0.1, view(cfg, lag=limit)).allowed
    assert g.check(order(sym), 0.1, view(cfg, lag=limit + 1)).rule == STALE
    v = view(cfg, lag=0)
    missing = GateView(v.date, v.equity, v.start_equity, v.cash, {}, v.prices,
                       {k: d for k, d in v.last_bar_date.items() if k != sym}, False)
    assert g.check(order(sym), 0.1, missing).rule == STALE
    future = GateView(v.date, v.equity, v.start_equity, v.cash, {}, v.prices, {**v.last_bar_date, sym: day(99)}, False)
    assert g.check(order(sym), 0.1, future).rule == STALE         # a bar after the fill date is impossible
    garbage = GateView(v.date, v.equity, v.start_equity, v.cash, {}, v.prices, {**v.last_bar_date, sym: "n/a"}, False)
    assert g.check(order(sym), 0.1, garbage).rule == STALE


def test_stale_only_blocks_that_symbol_and_never_exits():
    cfg = CFG["B"]
    g = RiskGate(cfg)
    v = view(cfg, cash=200.0, positions={"BTCUSDT": 0.5})
    stale = GateView(v.date, v.equity, v.start_equity, v.cash, v.positions, v.prices,
                     {"BTCUSDT": day(0), "ETHUSDT": v.date}, False)
    assert g.check(order("BTCUSDT"), 0.1, stale).rule == STALE
    assert g.check(order("ETHUSDT"), 0.1, stale).allowed
    assert g.check(order("BTCUSDT", "sell", "exit"), 0.5, stale) == Verdict(True, "", 0.5)


# ---- kill switch ------------------------------------------------------------------------------------------------

def test_kill_switch_triggers_at_half_of_start_equity():
    cfg = CFG["A"]
    g = RiskGate(cfg)
    assert not g.kill_triggered(view(cfg, cash=150.01))
    assert g.kill_triggered(view(cfg, cash=150.0))                # <= 50% (boundary included)
    assert g.check(order("SPY"), 0.1, view(cfg, cash=150.0)).rule == KILLED
    assert g.check(order("SPY"), 0.1, view(cfg, cash=150.01)).allowed


def test_kill_switch_is_sticky_and_fails_closed():
    cfg = CFG["A"]
    g = RiskGate(cfg)
    recovered = view(cfg, cash=400.0, killed=True)
    assert g.kill_triggered(recovered)
    assert g.check(order("SPY"), 0.1, recovered).rule == KILLED
    assert g.kill_triggered(view(cfg, equity=math.nan))
    assert g.kill_triggered(view(cfg, start=0.0))


def test_kill_exit_orders_cover_every_position_and_pass():
    cfg = CFG["A"]
    g = RiskGate(cfg)
    v = view(cfg, cash=10.0, positions={"SPY": 0.4, "GLD": 0.3, "EFA": 0.0})
    assert g.kill_triggered(v)
    exits = g.exit_orders(v, day(9), day(10))
    assert [(o.symbol, o.side, o.kind) for o in exits] == [("GLD", "sell", "exit"), ("SPY", "sell", "exit")]
    assert [g.check(o, 0.0, v) for o in exits] == [Verdict(True, "", 0.3), Verdict(True, "", 0.4)]


# ---- exits and shorts -------------------------------------------------------------------------------------------

def test_exit_sells_whole_position_and_sell_is_clamped():
    cfg = CFG["A"]
    g = RiskGate(cfg)
    v = view(cfg, cash=100.0, positions={"SPY": 1.5})
    assert g.check(order("SPY", "sell", "exit"), 0.2, v) == Verdict(True, "", 1.5)
    assert g.check(order("SPY", "sell", "rebalance"), 0.2, v) == Verdict(True, "", 0.2)
    assert g.check(order("SPY", "sell", "rebalance"), 9.0, v) == Verdict(True, "", 1.5)   # never short
    assert g.check(order("GLD", "sell", "exit"), 0.2, v).rule == NO_SHORT
    assert g.check(order("GLD", "sell", "rebalance"), 0.2, v).rule == NO_SHORT
    assert g.check(order("SPY", "sell", "rebalance"), math.nan, v).rule == BAD_QTY


positions_st = st.dictionaries(st.sampled_from(CFG["A"].instruments + ("XYZ",)),
                               st.floats(1e-6, 1e6, allow_nan=False), min_size=1)


@given(positions=positions_st, cash=st.one_of(st.floats(allow_nan=True), st.none()),
       equity=st.floats(allow_nan=True), killed=st.booleans(), lag=st.integers(-3, 400),
       price=st.one_of(st.floats(allow_nan=True), st.none()), qty=st.floats(allow_nan=True),
       kind=st.sampled_from(["exit", "rebalance", "entry"]), data=st.data())
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_property_sell_of_held_position_is_never_refused(positions, cash, equity, killed, lag, price, qty, kind, data):
    """Whatever the view (killed, stale, NaN equity/cash/prices), selling a held long passes and never shorts."""
    cfg = CFG["A"]
    g = RiskGate(cfg)
    sym = data.draw(st.sampled_from(sorted(positions)))
    prices = {} if price is None else {s: price for s in positions}
    v = GateView(day(10), equity, 300.0, cash, positions, prices, {sym: day(10 - lag)}, killed)
    verdict = g.check(order(sym, "sell", kind), qty, v)
    if kind == "exit":
        assert verdict == Verdict(True, "", positions[sym])
    elif math.isfinite(qty) and qty > 0:
        assert verdict.allowed and 0 < verdict.qty <= positions[sym]
    else:
        assert verdict.rule == BAD_QTY


# ---- the cap property over sequences ----------------------------------------------------------------------------

step_st = st.tuples(
    st.lists(st.floats(0.3, 2.0), min_size=5, max_size=5),                          # price multipliers
    st.lists(st.integers(0, 8), min_size=5, max_size=5),                            # days since last bar
    st.lists(st.tuples(st.integers(0, 4), st.sampled_from(["buy", "sell"]),
                       st.sampled_from(["entry", "exit", "rebalance"]), st.floats(0.0, 1.6)),
             max_size=7),
)


def simulate(market: str, cost_mult: float, steps) -> list[tuple]:
    """Run random order batches through `screen`, fill what is allowed at the gate's own cost estimates, and assert
    the invariants at every fill. Returns the log of (verdict, kind, side) for extra checks."""
    cfg = CFG[market]
    g = RiskGate(cfg, cost_mult=cost_mult)
    syms = list(cfg.instruments)
    n = len(syms)
    cash, pos, killed = cfg.start_equity_usd, {}, False
    prices = {s: 100.0 for s in syms}
    log = []
    for i, (mults, lags, raw_orders) in enumerate(steps):
        date = day(i)
        prices = {s: prices[s] * mults[k % 5] for k, s in enumerate(syms)}
        last = {s: day(i - lags[k % 5]) for k, s in enumerate(syms)}
        equity = cash + sum(q * prices[s] for s, q in pos.items())
        v = GateView(date, equity, cfg.start_equity_usd, cash, dict(pos), prices, last, killed)
        killed = g.kill_triggered(v)
        v = GateView(date, equity, cfg.start_equity_usd, cash, dict(pos), prices, last, killed)
        batch = []
        for k, side, kind, frac in raw_orders:
            sym = syms[k % n]
            if side == "buy":
                qty = frac * equity / prices[sym]
                kind = "rebalance" if kind == "exit" else kind
            else:
                qty = frac * pos.get(sym, 0.0)
            batch.append((Order(sym, side, kind, 0.0, day(i - 1), date), qty))
        if killed:
            batch += [(o, 0.0) for o in g.exit_orders(v, day(i - 1), date)]
        eq0 = equity
        for o, q, verdict in g.screen(batch, v):
            log.append((verdict, o.kind, o.side, killed, pos.get(o.symbol, 0.0)))
            if o.side == "sell" and pos.get(o.symbol, 0.0) > 1e-12 and (o.kind == "exit" or q > 0):
                assert verdict.allowed, verdict                          # exits / reductions always pass
            if not verdict.allowed:
                continue
            p = prices[o.symbol]
            if o.side == "sell":
                assert verdict.qty <= pos[o.symbol]                      # no shorts
                pos[o.symbol] -= verdict.qty
                if pos[o.symbol] <= 1e-12:
                    del pos[o.symbol]
                cash += g.sell_proceeds(verdict.qty, p)
            else:
                assert not killed and lags[syms.index(o.symbol) % 5] <= cfg.stale_after_days
                cash -= g.buy_cost(verdict.qty, p)
                pos[o.symbol] = pos.get(o.symbol, 0.0) + verdict.qty
                held_value = sum(qq * prices[s] for s, qq in pos.items())
                assert cash >= -1e-9 * eq0                               # no leverage
                assert pos[o.symbol] * p <= (1 / n) * eq0 * (1 + TOL) + 1e-9   # per-instrument cap
                assert held_value <= cfg.max_gross_exposure * (held_value + cash) * (1 + TOL) + 1e-9  # gross
        assert all(q > 0 for q in pos.values())
    return log


@given(steps=st.lists(step_st, min_size=1, max_size=25), market=st.sampled_from(["A", "B"]),
       cost_mult=st.sampled_from([1.0, 2.0]))
@settings(max_examples=250, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_property_no_order_sequence_breaches_a_cap(steps, market, cost_mult):
    simulate(market, cost_mult, steps)


def test_simulation_reaches_kill_and_then_only_sells():
    crash = ([0.3] * 5, [0] * 5, [])
    buy_all = ([1.0] * 5, [0] * 5, [(k, "buy", "entry", 0.19) for k in range(5)])
    try_buy = ([1.0] * 5, [0] * 5, [(k, "buy", "entry", 0.05) for k in range(5)])
    log = simulate("A", 1.0, [buy_all, crash, try_buy, ([4.0] * 5, [0] * 5, []), try_buy])
    assert sum(1 for v, kind, side, killed, _ in log if side == "buy" and v.allowed) == 5   # only before the crash
    assert any(v.rule == KILLED for v, *_ in log)
    assert any(kind == "exit" and v.allowed for v, kind, *_ in log)


def test_screen_projects_cash_sells_first():
    cfg = CFG["A"]
    g = RiskGate(cfg)
    v = view(cfg, cash=0.0, positions={"GLD": 0.6})               # fully invested in GLD, 60 of 60 equity
    v = GateView(v.date, 60.0, 60.0, 0.0, v.positions, v.prices, v.last_bar_date, False)  # not killed
    buy = (order("SPY", w=0.1), 0.05)
    sell = (order("GLD", "sell", "exit"), 0.6)
    out = g.screen([buy, sell], v)                                 # buy listed first, executed after the sell
    assert [o.side for o, _, _ in out] == ["sell", "buy"]
    assert all(verdict.allowed for _, _, verdict in out)
    assert not g.check(*buy, v).allowed                             # alone, with no cash, the buy is refused
