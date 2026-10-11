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


def build_parser() -> argparse.ArgumentParser:
    raise NotImplementedError


def main(argv: list[str] | None = None) -> int:
    raise NotImplementedError
