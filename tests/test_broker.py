"""Paper broker: hand-computed costs (x1 and x2), fills at the open, min-order skips, lot steps, cash safety."""
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from algotrade.broker import CostModel, Fill, Order, PaperBroker, apply_fills
from algotrade.config import load_config

# Criteria §4 (config/A.toml, config/B.toml)
A = dict(commission_rate=0.0, sec_fee_rate_sell=0.0000206, taf_per_share_sell=0.000119,
         taf_max_per_trade=5.95, slippage_rate=0.0010)
B = dict(commission_rate=0.0010, sec_fee_rate_sell=0.0, taf_per_share_sell=0.0, taf_max_per_trade=0.0,
         slippage_rate=0.0005)
# reports/data-quality.md §1: exchangeInfo NOTIONAL 5 USDT, LOT_SIZE BTC 0.00001, ETH 0.0001
B_MIN = {"BTCUSDT": 5.0, "ETHUSDT": 5.0}
B_LOT = {"BTCUSDT": 0.00001, "ETHUSDT": 0.0001}


def order(sym, side, kind, w):
    return Order(sym, side, kind, w, "2024-01-05", "2024-01-08")


def test_cost_model_matches_config():
    for m, ref in (("A", A), ("B", B)):
        cm = CostModel.from_config(load_config(m).costs, 2.0)
        assert cm.cost_mult == 2.0
        for k, v in ref.items():
            assert getattr(cm, k) == pytest.approx(v)


# ---------------------------------------------------------------- slippage (fill price)

@pytest.mark.parametrize("mult, buy, sell", [(1.0, 100.10, 99.90), (2.0, 100.20, 99.80)])
def test_fill_price_A(mult, buy, sell):
    cm = CostModel(**A, cost_mult=mult)
    assert cm.fill_price("buy", 100.0) == pytest.approx(buy)
    assert cm.fill_price("sell", 100.0) == pytest.approx(sell)


@pytest.mark.parametrize("mult, buy, sell", [(1.0, 50025.0, 49975.0), (2.0, 50050.0, 49950.0)])
def test_fill_price_B(mult, buy, sell):
    cm = CostModel(**B, cost_mult=mult)
    assert cm.fill_price("buy", 50000.0) == pytest.approx(buy)
    assert cm.fill_price("sell", 50000.0) == pytest.approx(sell)


# ---------------------------------------------------------------- fees

def test_A_buy_pays_no_fee():
    assert CostModel(**A).fees("buy", 10.0, 100.1) == (0.0, 0.0)


def test_A_sell_sec_and_taf_x1():
    # 10 shares at 99.90: notional 999.00; SEC 999 * 0.0000206 = 0.0205794; TAF 10 * 0.000119 = 0.00119
    com, reg = CostModel(**A).fees("sell", 10.0, 99.9)
    assert com == 0.0
    assert reg == pytest.approx(0.0205794 + 0.00119, abs=1e-12)


def test_A_sell_sec_and_taf_x2():
    # 10 shares at 99.80 (x2 slippage): SEC 998 * 0.0000206 * 2 = 0.0411176; TAF 0.00119 * 2 = 0.00238
    com, reg = CostModel(**A, cost_mult=2.0).fees("sell", 10.0, 99.8)
    assert com == 0.0
    assert reg == pytest.approx(0.0411176 + 0.00238, abs=1e-12)


@pytest.mark.parametrize("mult, taf", [(1.0, 5.95), (2.0, 11.90)])
def test_A_taf_cap(mult, taf):
    # 100000 shares * 0.000119 = 11.90 > cap 5.95; price 1 -> SEC = 100000 * 0.0000206 * mult = 2.06 * mult
    _, reg = CostModel(**A, cost_mult=mult).fees("sell", 100000.0, 1.0)
    assert reg == pytest.approx(taf + 2.06 * mult)


@pytest.mark.parametrize("mult, com", [(1.0, 50.025), (2.0, 100.10)])
def test_B_commission_buy(mult, com):
    cm = CostModel(**B, cost_mult=mult)
    p = cm.fill_price("buy", 50000.0)
    assert cm.fees("buy", 1.0, p) == (pytest.approx(com), 0.0)


@pytest.mark.parametrize("mult, com", [(1.0, 49.975), (2.0, 99.90)])
def test_B_commission_sell(mult, com):
    cm = CostModel(**B, cost_mult=mult)
    p = cm.fill_price("sell", 50000.0)
    assert cm.fees("sell", 1.0, p) == (pytest.approx(com), 0.0)


# ---------------------------------------------------------------- execute: A

def test_A_entry_fill():
    br = PaperBroker(CostModel(**A), {"SPY": 1.0}, {"SPY": 0.0})
    fills, skips = br.execute([order("SPY", "buy", "entry", 0.2)], {"SPY": 100.0}, 300.0, {})
    assert skips == []
    (f,) = fills
    # target qty = 0.2 * 300 / 100 = 0.6 (fractional), price 100.1, slippage 0.6 * 0.1 = 0.06
    assert f.qty == pytest.approx(0.6)
    assert f.price == pytest.approx(100.1)
    assert f.open_price == 100.0
    assert (f.commission, f.regulatory) == (0.0, 0.0)
    assert f.slippage_cost == pytest.approx(0.06)
    assert f.date == "2024-01-08"
    cash, pos = apply_fills(fills, 300.0, {})
    assert cash == pytest.approx(300.0 - 60.06)
    assert pos == {"SPY": pytest.approx(0.6)}


def test_A_exit_fill_x1():
    br = PaperBroker(CostModel(**A), {"SPY": 1.0}, {"SPY": 0.0})
    fills, _ = br.execute([order("SPY", "sell", "exit", 0.0)], {"SPY": 110.0}, 239.94, {"SPY": 0.6})
    (f,) = fills
    # price 110 * 0.999 = 109.89; notional 65.934; SEC 0.0013582404; TAF 0.6 * 0.000119 = 0.0000714
    assert f.qty == 0.6 and f.price == pytest.approx(109.89)
    assert f.regulatory == pytest.approx(0.0013582404 + 0.0000714, abs=1e-13)
    assert f.slippage_cost == pytest.approx(0.066)
    cash, pos = apply_fills(fills, 239.94, {"SPY": 0.6})
    assert cash == pytest.approx(239.94 + 65.934 - 0.0014296404)
    assert pos == {}


def test_A_exit_fill_x2():
    br = PaperBroker(CostModel(**A, cost_mult=2.0), {"SPY": 1.0}, {"SPY": 0.0})
    (f,), _ = br.execute([order("SPY", "sell", "exit", 0.0)], {"SPY": 110.0}, 0.0, {"SPY": 0.6})
    # price 110 * 0.998 = 109.78; notional 65.868; SEC 65.868 * 0.0000206 * 2; TAF 0.0000714 * 2
    assert f.price == pytest.approx(109.78)
    assert f.regulatory == pytest.approx(65.868 * 0.0000206 * 2 + 0.0001428, abs=1e-13)
    assert f.slippage_cost == pytest.approx(0.132)


def test_A_entry_below_one_dollar_is_skipped():
    br = PaperBroker(CostModel(**A), {"SPY": 1.0}, {"SPY": 0.0})
    fills, skips = br.execute([order("SPY", "buy", "entry", 0.003)], {"SPY": 100.0}, 300.0, {})
    assert fills == [] and [s.reason for s in skips] == ["below_min_order"]   # 0.9 USD < 1 USD


def test_sells_fund_buys_sells_go_first():
    br = PaperBroker(CostModel(**A), {"SPY": 1.0, "IEF": 1.0}, {})
    orders = [order("IEF", "buy", "entry", 0.2), order("SPY", "sell", "exit", 0.0)]
    fills, skips = br.execute(orders, {"SPY": 100.0, "IEF": 50.0}, 0.0, {"SPY": 0.6})
    assert [f.symbol for f in fills] == ["SPY", "IEF"] and skips == []
    cash, _ = apply_fills(fills, 0.0, {"SPY": 0.6})
    assert cash >= 0.0


def test_missing_open_is_no_bar():
    br = PaperBroker(CostModel(**A), {}, {})
    fills, skips = br.execute([order("SPY", "buy", "entry", 0.2)], {"SPY": float("nan")}, 300.0, {})
    assert fills == [] and skips[0].reason == "no_bar"


def test_held_position_without_open_uses_mark():
    br = PaperBroker(CostModel(**A), {}, {})
    with pytest.raises(ValueError):
        br.execute([], {}, 100.0, {"GLD": 1.0})
    fills, _ = br.execute([order("SPY", "buy", "entry", 0.2)], {"SPY": 100.0}, 100.0, {"GLD": 1.0},
                          marks={"GLD": 200.0})
    assert fills[0].qty == pytest.approx(0.2 * 300.0 / 100.0)


def test_rebalance_trim():
    br = PaperBroker(CostModel(**A), {"SPY": 1.0}, {})
    # equity = 0 + 1 * 100 = 100; target 0.5 -> 0.5 shares -> sell 0.5
    (f,), _ = br.execute([order("SPY", "sell", "rebalance", 0.5)], {"SPY": 100.0}, 0.0, {"SPY": 1.0})
    assert f.qty == pytest.approx(0.5) and f.kind == "rebalance"


# ---------------------------------------------------------------- execute: B (min notional, lot step)

def test_B_lot_floor_and_pro_rata():
    br = PaperBroker(CostModel(**B), B_MIN, B_LOT)
    orders = [order("BTCUSDT", "buy", "entry", 0.5), order("ETHUSDT", "buy", "entry", 0.5)]
    fills, skips = br.execute(orders, {"BTCUSDT": 30000.0, "ETHUSDT": 1234.0}, 300.0, {})
    assert skips == []
    # wanted 150 USD each at open; cost per USD of open = 1.0005 * 1.001, need = 300.45015 > 300
    # scale = 300 / 300.45015; BTC 0.005 * scale = 0.0049925 -> 0.00499; ETH 0.121556 * scale = 0.121374 -> 0.1213
    assert [f.qty for f in fills] == [0.00499, 0.1213]
    btc = fills[0]
    assert btc.price == 30015.0
    assert btc.commission == pytest.approx(0.00499 * 30015.0 * 0.001)
    assert btc.slippage_cost == pytest.approx(0.00499 * 15.0)
    cash, _ = apply_fills(fills, 300.0, {})
    assert 0.0 <= cash < 1.0


def test_B_entry_below_min_notional_skipped():
    br = PaperBroker(CostModel(**B), B_MIN, B_LOT)
    fills, skips = br.execute([order("BTCUSDT", "buy", "entry", 0.01)], {"BTCUSDT": 30000.0}, 300.0, {})
    assert fills == [] and skips[0].reason == "below_min_order"     # 3 USD < 5 USDT


def test_B_rebalance_below_min_skipped_but_exit_sells_in_full_and_is_flagged():
    br = PaperBroker(CostModel(**B), B_MIN, B_LOT)
    held = {"BTCUSDT": 0.00005}                                       # 2.50 USD at 50000
    fills, skips = br.execute([order("BTCUSDT", "sell", "rebalance", 0.001)], {"BTCUSDT": 50000.0}, 300.0, held)
    assert fills == [] and skips[0].reason == "below_min_order"
    fills, skips = br.execute([order("BTCUSDT", "sell", "exit", 0.0)], {"BTCUSDT": 50000.0}, 300.0, held)
    (f,) = fills
    assert skips == [] and f.qty == 0.00005 and f.below_min is True
    assert f.commission == pytest.approx(0.00005 * 49975.0 * 0.001)


def test_B_exit_off_lot_grid_sells_everything():
    br = PaperBroker(CostModel(**B), B_MIN, B_LOT)
    held = {"ETHUSDT": 0.123456789}
    (f,), _ = br.execute([order("ETHUSDT", "sell", "exit", 0.0)], {"ETHUSDT": 2000.0}, 0.0, held)
    assert f.qty == 0.123456789 and f.below_min is False


def test_B_doubled_costs_exact_ratio():
    q = dict(orders=[order("BTCUSDT", "buy", "entry", 0.5)], opens={"BTCUSDT": 20000.0}, cash=300.0, positions={})
    (f1,), _ = PaperBroker(CostModel(**B), B_MIN, B_LOT).execute(**q)
    (f2,), _ = PaperBroker(CostModel(**B, cost_mult=2.0), B_MIN, B_LOT).execute(**q)
    assert f1.qty == f2.qty == 0.0075                                  # 150 / 20000, not cash-constrained
    assert f2.slippage_cost == pytest.approx(2 * f1.slippage_cost)
    assert f1.commission == pytest.approx(0.0075 * 20010 * 0.001)
    assert f2.commission == pytest.approx(0.0075 * 20020 * 0.002)


def test_no_position_exit_is_skipped():
    br = PaperBroker(CostModel(**B), B_MIN, B_LOT)
    _, skips = br.execute([order("BTCUSDT", "sell", "exit", 0.0)], {"BTCUSDT": 1.0}, 10.0, {})
    assert skips[0].reason == "no_position"


def test_execute_is_pure():
    br = PaperBroker(CostModel(**B), B_MIN, B_LOT)
    pos = {"ETHUSDT": 0.1}
    args = ([order("BTCUSDT", "buy", "entry", 0.5), order("ETHUSDT", "sell", "exit", 0.0)],
            {"BTCUSDT": 30000.0, "ETHUSDT": 2000.0}, 50.0, pos)
    assert br.execute(*args) == br.execute(*args)
    assert pos == {"ETHUSDT": 0.1}


# ---------------------------------------------------------------- properties

SYMS = ["S0", "S1", "S2"]
price = st.floats(min_value=1.0, max_value=100000.0, allow_nan=False)
weights = st.floats(min_value=0.0, max_value=1 / 3, allow_nan=False)


@st.composite
def scenario(draw, lot=True, min_order=True):
    opens = {s: draw(price) for s in SYMS}
    positions = {s: q for s in SYMS if (q := draw(st.floats(0.0, 5.0))) > 0}
    cash = draw(st.floats(0.0, 10000.0))
    orders = []
    for s in SYMS:
        w = draw(weights)
        kind = draw(st.sampled_from(["entry", "exit", "rebalance"]))
        side = "sell" if kind == "exit" else draw(st.sampled_from(["buy", "sell"]))
        orders.append(order(s, side, kind, 0.0 if kind == "exit" else w))
    orders = draw(st.permutations(orders))
    mins = {s: draw(st.sampled_from([0.0, 1.0, 5.0, 10.0])) if min_order else 0.0 for s in SYMS}
    lots = {s: draw(st.sampled_from([0.0, 0.00001, 0.0001, 0.01])) if lot else 0.0 for s in SYMS}
    cost = {k: draw(st.floats(0.0, 0.01)) for k in ("commission_rate", "sec_fee_rate_sell", "slippage_rate")}
    cost |= {"taf_per_share_sell": draw(st.floats(0.0, 0.001)), "taf_max_per_trade": draw(st.floats(0.0, 10.0))}
    return orders, opens, cash, positions, mins, lots, cost


def _equity_at_open(cash, pos, opens):
    return cash + sum(q * opens[s] for s, q in pos.items())


@settings(max_examples=300, deadline=None)
@given(scenario(), st.sampled_from([1.0, 2.0]))
def test_property_cash_never_negative_costs_non_negative(sc, mult):
    orders, opens, cash, positions, mins, lots, cost = sc
    br = PaperBroker(CostModel(**cost, cost_mult=mult), mins, lots)
    fills, skips = br.execute(orders, opens, cash, positions)
    new_cash, new_pos = apply_fills(fills, cash, positions)
    assert new_cash >= 0.0
    assert all(q >= -1e-12 for q in new_pos.values())                # no shorts
    for f in fills:
        assert f.qty > 0 and f.commission >= 0 and f.regulatory >= 0 and f.slippage_cost >= 0
        if f.side == "buy":
            assert f.price >= f.open_price
        else:
            assert f.price <= f.open_price
    assert len(fills) + len(skips) == len(orders)
    sides = [f.side for f in fills]
    assert sides == sorted(sides, key=lambda s: s != "sell")           # every sell before every buy


@settings(max_examples=300, deadline=None)
@given(scenario(lot=False, min_order=False))
def test_property_doubled_costs_never_improve_the_result(sc):
    """Mark-to-open equity right after the fills. With no lot step and no minimum (so the same orders trade),
    doubling costs can only lower it. (With minimums a doubled cost can make a trade skip and so avoid its cost;
    that is not an improvement of the strategy, so it is excluded from the property.)"""
    orders, opens, cash, positions, mins, lots, cost = sc
    out = []
    for m in (1.0, 2.0):
        fills, _ = PaperBroker(CostModel(**cost, cost_mult=m), mins, lots).execute(orders, opens, cash, positions)
        c, p = apply_fills(fills, cash, positions)
        out.append(_equity_at_open(c, p, opens))
    assert out[1] <= out[0] + 1e-9 * max(1.0, abs(out[0]))
    assert out[0] <= _equity_at_open(cash, positions, opens) + 1e-9 * max(1.0, out[0])


def test_fill_cash_delta_signs():
    f = Fill("X", "buy", "entry", 2.0, 10.1, 10.0, 0.5, 0.0, 0.2, "d")
    assert f.cash_delta == pytest.approx(-20.7)
    g = Fill("X", "sell", "exit", 2.0, 9.9, 10.0, 0.5, 0.1, 0.2, "d")
    assert g.cash_delta == pytest.approx(19.2)
    assert math.isclose(f.notional, 20.2)
