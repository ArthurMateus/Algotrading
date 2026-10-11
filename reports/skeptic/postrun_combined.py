"""Combined sensitivities (reported only). A: T-bill cash + GLD 2026-01-30 neutralised.
B: T-bill cash + fills at next close (one-day latency). Run: uv run python -X utf8 reports/skeptic/postrun_combined.py"""
import dataclasses
import runpy
import sys
from pathlib import Path

import pandas as pd

here = Path(__file__).parent
for m in ("A", "B"):
    sys.argv = ["x", m]
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        g = runpy.run_path(str(here / "postrun_diagnostics.py"))
    run, stats, fmt, tbill_equity, W, panel, c8 = (g[k] for k in
        ("run", "stats", "fmt", "tbill_equity", "W", "panel", "c8"))
    sel = g["sel"]
    if m == "A":
        d = pd.Timestamp("2026-01-30")
        out = {}
        for key in (sel, "benchmark"):
            res = run(key, *W)
            e, r = tbill_equity(res)
            gret = panel.close["GLD"].pct_change()[d]
            r = r.copy(); r[d] -= res.weights["GLD"].shift(1)[d] * gret
            out[key] = stats((1 + r).cumprod() * 300.0, r)
            print(f"A {key:16s} T-bill cash + GLD 01-30 neutral: {fmt(out[key])}")
        print("A c8:", c8(out[sel], out["benchmark"]))
    else:
        cf = dataclasses.replace(panel, open=panel.close)
        res = run(sel, *W, p=cf)
        e, r = tbill_equity(res)
        print(f"B close-fill (1-day latency) + T-bill cash: {fmt(stats(e, r))}")
        res = run("benchmark", *W, p=cf)
        print(f"B benchmark close-fill: {fmt(stats(res.equity))}")
