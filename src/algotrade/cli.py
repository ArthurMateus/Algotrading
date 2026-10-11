"""Command line: `uv run algotrade <command>`. Owner: data-engineer (wires all commands in step 1).

  algotrade fetch [--market A|B|all]          download/refresh bars + aux series into data/, print integrity issues
  algotrade backtest --market A --split is    12-variant grid on in-sample, walk-forward, selection, DSR
  algotrade backtest --market A --split oos [--force --reason "..."]
                                              the one-time OOS run (refuses a second run unless forced; logged)
  algotrade paper --market B                  one forward paper step (run once a day)
  algotrade status                            what is cached, variants used, whether OOS has run

Exit code 0 on success, 1 on a refused action (cap, OOS already run), 2 on bad arguments.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MARKETS = ("A", "B")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="algotrade", description="Paper / backtest only. No orders, no keys.")
    sub = ap.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch", help="download/refresh bars and aux series into data/")
    f.add_argument("--market", choices=[*MARKETS, "all"], default="all")
    b = sub.add_parser("backtest", help="in-sample grid or the one-time out-of-sample run")
    b.add_argument("--market", choices=MARKETS, required=True)
    b.add_argument("--split", choices=["is", "oos"], required=True)
    b.add_argument("--force", action="store_true", help="allow a second OOS run (logged)")
    b.add_argument("--reason", default="", help="required with --force")
    p = sub.add_parser("paper", help="one forward paper step (once a day)")
    p.add_argument("--market", choices=MARKETS, required=True)
    sub.add_parser("status", help="what is cached, variants used, whether OOS has run")
    return ap


def _fetch(markets: list[str]) -> int:
    from algotrade import data
    from algotrade.config import load_config, verify_criteria

    rc = 0
    for m in markets:
        cfg = load_config(m)
        verify_criteria(cfg)
        print(f"[{m}] fetching {', '.join(cfg.instruments)} up to {cfg.end_date} ...")
        try:
            issues = data.fetch_market(cfg)
            issues += data.fetch_aux(cfg)
        except Exception as e:  # network or source failure: report, keep going with the other market
            print(f"[{m}] FAILED: {e}")
            rc = 1
            continue
        bars = data.load_bars(cfg)
        for sym, b in bars.items():
            fr = b.frame
            print(f"[{m}] {sym:8s} {b.source:15s} {b.adjusted:13s} {fr.index[0].date()} .. {fr.index[-1].date()}  rows={len(fr)}")
        kinds: dict[str, int] = {}
        for i in issues:
            kinds[i.kind] = kinds.get(i.kind, 0) + 1
        print(f"[{m}] issues: " + (", ".join(f"{k}={v}" for k, v in sorted(kinds.items())) or "none"))
        for i in issues[:25]:
            print(f"   {i.kind:13s} {i.symbol:9s} {i.date:10s} {i.detail}")
        if len(issues) > 25:
            print(f"   ... {len(issues) - 25} more (data/bars/{m}/issues.json)")
    return rc


def _status() -> int:
    from algotrade.config import load_config

    for m in MARKETS:
        cfg = load_config(m)
        man_path = Path(cfg.data_dir) / "bars" / m / "manifest.json"
        if not man_path.exists():
            print(f"[{m}] no cached data (run: uv run algotrade fetch --market {m})")
            continue
        man = json.loads(man_path.read_text(encoding="utf-8"))
        for sym in cfg.instruments:
            e = man.get(sym)
            if e is None:
                print(f"[{m}] {sym}: not cached")
            else:
                print(f"[{m}] {sym:8s} {e['source']:15s} {e['adjusted']:13s} {e['first']} .. {e['last']} "
                      f"rows={e['rows']} fetched={e['fetched_at']}")
    aux = Path(load_config("A").data_dir) / "aux" / "manifest.json"
    if aux.exists():
        for name, e in json.loads(aux.read_text(encoding="utf-8")).items():
            print(f"[aux] {name:6s} {e['first']} .. {e['last']} rows={e['rows']} fetched={e['fetched_at']}")
    else:
        print("[aux] nothing cached")
    try:
        from algotrade import evaluate
        print(evaluate.status())
    except NotImplementedError:
        print("[backtest] variants/OOS status: not implemented yet")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 2
    from algotrade.config import ConfigError

    try:
        if args.command == "fetch":
            return _fetch(list(MARKETS) if args.market == "all" else [args.market])
        if args.command == "status":
            return _status()
        from algotrade.config import load_config, verify_criteria
        verify_criteria(load_config(args.market))
        if args.command == "backtest":
            from algotrade import evaluate
            if args.split == "is":
                evaluate.run_is(args.market)
            else:
                if args.force and not args.reason.strip():
                    print("--force needs --reason \"...\"")
                    return 2
                evaluate.run_oos(args.market, force=args.force, reason=args.reason)
            return 0
        if args.command == "paper":
            from algotrade import paper
            paper.paper_step(args.market)
            return 0
    except ConfigError as e:
        print(f"config error: {e}")
        return 1
    except NotImplementedError:
        print(f"'{args.command}' is not implemented yet")
        return 1
    except Exception as e:
        print(f"refused or failed: {type(e).__name__}: {e}")
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
