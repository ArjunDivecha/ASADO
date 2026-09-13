# P02 label reconciliation

Snapshot: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/nonlinear_country_returns/snapshot_2026_09_13` (asof 2026-09-11)

## Calendar

- Session convention: mark-change days on the padded T2 grid (see calendar_manifest.json). 149,976 sessions across 22 markets, 2000-01-04 -> 2026-09-11.
- Weekend sessions in store: **0** (T08).
- Candidate origins (>=20 sessions): **6,765**, 2000-01-04 -> 2026-09-10.

## Labels (h20 primary; h5/h63 diagnostics in labels.parquet)

- rows: 148,830
- mature: 148,369
- censored_tail: 440
- unresolved_mature: 0
- no_future_session: 21

## Reconciliation vs harness `20DRet`

Stage A — source anchor: recomputing the harness convention (20 padded-grid-row shift) from our TRI marks gives median abs diff **2.52e-07** over 214,522 rows; 0.43% of rows differ by >1pp — concentrated in Mar-2020 Indonesia/Thailand (stored factor rows predate TRI back-revisions). Worst rows:

  - {'date': '2020-03-03', 'country': 'Indonesia', 'grid_recomputed': -0.08285236102809324, 'ret_20d_grid': -0.436581}
  - {'date': '2020-03-05', 'country': 'Indonesia', 'grid_recomputed': -0.09513564519933937, 'ret_20d_grid': -0.444798}
  - {'date': '2020-03-04', 'country': 'Indonesia', 'grid_recomputed': -0.10625116495806153, 'ret_20d_grid': -0.451654}
  - {'date': '2020-02-28', 'country': 'Indonesia', 'grid_recomputed': -0.05130531520395554, 'ret_20d_grid': -0.358096}
  - {'date': '2020-03-25', 'country': 'Indonesia', 'grid_recomputed': -0.010535179835858721, 'ret_20d_grid': 0.295092}

Labels therefore use the latest-corrected TRI marks — the correct convention for realized outcomes.

Stage B — clock difference (structural, expected):

- compared_rows: 148809
- label_abs_diff_median: 0.021806974655079962
- label_abs_diff_p95: 0.08333294578880245
- label_abs_diff_max: 0.46061130193815614
- entry_is_next_calendar_day_share: 0.788164694339724
- meaning: harness 20DRet = 20 padded-GRID-row shift (~14 sessions); study label = 20 local-SESSION shift (~28 calendar days). The gap is a horizon/clock difference, not a defect.

`20DRet` is a 20 padded-grid-row shift (~14 sessions); the study label is a 20 local-session shift from the first session after a 23:59 UTC origin (~28 calendar days). The divergence is a horizon/clock difference, not a defect — the harness surface is not the authority for this label.
