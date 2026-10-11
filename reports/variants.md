# Variant log

Every backtest run, appended automatically by `algotrade.variants.record_run` (source of truth: `reports/variants.jsonl`). The cap counts distinct variant keys per market (12; the benchmark is not a variant). Timestamps are UTC.

| Timestamp (UTC) | Commit | Market | Variant | Split | Cost x | Metrics |
|---|---|---|---|---|---|---|
| 2026-10-11T21:16:45Z | cfc3af3dfba0 | A | TSMOM-63-weekly | is | 1 | sharpe=0.4052, max_dd=0.09072, underwater_months=30.29, round_trips=206, cagr=0.02752, final_equity=435.6, cost_total=26.7, n_fills=557, below_min_exits=0 |
| 2026-10-11T21:16:46Z | cfc3af3dfba0 | A | TSMOM-63-monthly | is | 1 | sharpe=0.2856, max_dd=0.1143, underwater_months=76.39, round_trips=104, cagr=0.0221, final_equity=405.1, cost_total=13.74, n_fills=301, below_min_exits=0 |
| 2026-10-11T21:16:46Z | cfc3af3dfba0 | A | TSMOM-126-weekly | is | 1 | sharpe=0.4055, max_dd=0.1009, underwater_months=28.65, round_trips=117, cagr=0.02879, final_equity=443.1, cost_total=16.93, n_fills=384, below_min_exits=0 |
| 2026-10-11T21:16:46Z | cfc3af3dfba0 | A | TSMOM-126-monthly | is | 1 | sharpe=0.5325, max_dd=0.1234, underwater_months=23.23, round_trips=58, cagr=0.03735, final_equity=496.4, cost_total=9.896, n_fills=228, below_min_exits=0 |
| 2026-10-11T21:16:46Z | cfc3af3dfba0 | A | TSMOM-252-weekly | is | 1 | sharpe=0.3998, max_dd=0.1125, underwater_months=24.16, round_trips=99, cagr=0.02858, final_equity=441.8, cost_total=13.82, n_fills=362, below_min_exits=0 |
| 2026-10-11T21:16:46Z | cfc3af3dfba0 | A | TSMOM-252-monthly | is | 1 | sharpe=0.4571, max_dd=0.1292, underwater_months=33.23, round_trips=44, cagr=0.03268, final_equity=466.6, cost_total=7.771, n_fills=213, below_min_exits=0 |
| 2026-10-11T21:16:47Z | cfc3af3dfba0 | A | SMA-63-weekly | is | 1 | sharpe=0.3345, max_dd=0.1063, underwater_months=37.97, round_trips=251, cagr=0.02322, final_equity=411.2, cost_total=31.58, n_fills=630, below_min_exits=0 |
| 2026-10-11T21:16:47Z | cfc3af3dfba0 | A | SMA-63-monthly | is | 1 | sharpe=0.3759, max_dd=0.09796, underwater_months=48.39, round_trips=127, cagr=0.02586, final_equity=426, cost_total=15.97, n_fills=348, below_min_exits=0 |
| 2026-10-11T21:16:47Z | cfc3af3dfba0 | A | SMA-126-weekly | is | 1 | sharpe=0.4864, max_dd=0.07286, underwater_months=24.58, round_trips=161, cagr=0.03192, final_equity=461.9, cost_total=21.92, n_fills=462, below_min_exits=0 |
| 2026-10-11T21:16:47Z | cfc3af3dfba0 | A | SMA-126-monthly | is | 1 | sharpe=0.515, max_dd=0.08318, underwater_months=68.9, round_trips=81, cagr=0.03448, final_equity=477.9, cost_total=12.11, n_fills=272, below_min_exits=0 |
| 2026-10-11T21:16:47Z | cfc3af3dfba0 | A | SMA-252-weekly | is | 1 | sharpe=0.5531, max_dd=0.06584, underwater_months=37.87, round_trips=103, cagr=0.0361, final_equity=488.3, cost_total=15.19, n_fills=362, below_min_exits=0 |
| 2026-10-11T21:16:48Z | cfc3af3dfba0 | A | SMA-252-monthly | is | 1 | sharpe=0.4961, max_dd=0.07296, underwater_months=38.35, round_trips=52, cagr=0.03388, final_equity=474.1, cost_total=8.4, n_fills=226, below_min_exits=0 |
| 2026-10-11T21:16:48Z | cfc3af3dfba0 | A | benchmark | is | 1 | sharpe=0.3681, max_dd=0.3464, underwater_months=38.2, round_trips=0, cagr=0.04559, final_equity=553.4, cost_total=2.042, n_fills=588, below_min_exits=0 |
| 2026-10-11T21:16:48Z | cfc3af3dfba0 | B | TSMOM-63-weekly | is | 1 | sharpe=0.8313, max_dd=0.4106, underwater_months=18.29, round_trips=36, cagr=0.256, final_equity=949.8, cost_total=21.55, n_fills=170, below_min_exits=0 |
| 2026-10-11T21:16:48Z | cfc3af3dfba0 | B | TSMOM-63-monthly | is | 1 | sharpe=0.7969, max_dd=0.4139, underwater_months=18.29, round_trips=19, cagr=0.2553, final_equity=947.3, cost_total=13.46, n_fills=77, below_min_exits=0 |
| 2026-10-11T21:16:49Z | cfc3af3dfba0 | B | TSMOM-126-weekly | is | 1 | sharpe=1.174, max_dd=0.3531, underwater_months=18.29, round_trips=20, cagr=0.3729, final_equity=1490, cost_total=21.69, n_fills=141, below_min_exits=0 |
| 2026-10-11T21:16:49Z | cfc3af3dfba0 | B | TSMOM-126-monthly | is | 1 | sharpe=0.9278, max_dd=0.3315, underwater_months=18.29, round_trips=11, cagr=0.2904, final_equity=1089, cost_total=8.964, n_fills=61, below_min_exits=0 |
| 2026-10-11T21:16:49Z | cfc3af3dfba0 | B | TSMOM-252-weekly | is | 1 | sharpe=0.8911, max_dd=0.3665, underwater_months=30, round_trips=14, cagr=0.2635, final_equity=979, cost_total=10.38, n_fills=149, below_min_exits=0 |
| 2026-10-11T21:16:49Z | cfc3af3dfba0 | B | TSMOM-252-monthly | is | 1 | sharpe=0.7906, max_dd=0.375, underwater_months=27.87, round_trips=7, cagr=0.232, final_equity=861.6, cost_total=5.569, n_fills=64, below_min_exits=0 |
| 2026-10-11T21:16:49Z | cfc3af3dfba0 | B | SMA-63-weekly | is | 1 | sharpe=1.131, max_dd=0.3162, underwater_months=18.29, round_trips=36, cagr=0.3568, final_equity=1404, cost_total=27.67, n_fills=169, below_min_exits=0 |
| 2026-10-11T21:16:49Z | cfc3af3dfba0 | B | SMA-63-monthly | is | 1 | sharpe=0.8069, max_dd=0.483, underwater_months=24.19, round_trips=24, cagr=0.248, final_equity=919.8, cost_total=16.58, n_fills=83, below_min_exits=0 |
| 2026-10-11T21:16:49Z | cfc3af3dfba0 | B | SMA-126-weekly | is | 1 | sharpe=1.193, max_dd=0.3901, underwater_months=18.29, round_trips=18, cagr=0.3828, final_equity=1545, cost_total=21.24, n_fills=134, below_min_exits=0 |
| 2026-10-11T21:16:49Z | cfc3af3dfba0 | B | SMA-126-monthly | is | 1 | sharpe=1.043, max_dd=0.4038, underwater_months=18.29, round_trips=12, cagr=0.3576, final_equity=1408, cost_total=13.46, n_fills=65, below_min_exits=0 |
| 2026-10-11T21:16:49Z | cfc3af3dfba0 | B | SMA-252-weekly | is | 1 | sharpe=0.9196, max_dd=0.4045, underwater_months=18.29, round_trips=16, cagr=0.2727, final_equity=1015, cost_total=12.86, n_fills=136, below_min_exits=0 |
| 2026-10-11T21:16:49Z | cfc3af3dfba0 | B | SMA-252-monthly | is | 1 | sharpe=0.8909, max_dd=0.3595, underwater_months=24.19, round_trips=10, cagr=0.2618, final_equity=972.5, cost_total=7.399, n_fills=59, below_min_exits=0 |
| 2026-10-11T21:16:49Z | cfc3af3dfba0 | B | benchmark | is | 1 | sharpe=-0.6968, max_dd=0.5789, underwater_months=60.39, round_trips=2, cagr=-0.1336, final_equity=145.3, cost_total=0.7508, n_fills=8, below_min_exits=0 |
