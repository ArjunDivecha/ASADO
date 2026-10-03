# E1 network_spillover capture test — 2026-08-23

## Decision

The re-arm gate correctly triggered an investigation, but this test does not
authorize deployment. The family remains parked. The only expression that was
positive in the 10 bp one-way execution diagnostic was the six-market futures
subset; the broad ETF expressions did not survive that diagnostic, and the
local-index result is not directly tradable.

No paper sleeve or external order was created.

## Frozen inputs and clock

- Existing frozen nightly ranks: `Data/work/experiments/flip_autopsy/snapshot_2026_07_13/family_ranks_daily.parquet`
- Rank-panel SHA256: `a685e8b336149a149bef1a1a30fc28175e6fce3190aa9326f452bab8a827e22e`
- Equal-weight blend of the available frozen rank families: `graph_bank`,
  `graph_twohop`, `leadlag`, and `twins`; at least two member ranks required.
- Harness-v4 effective execution lag: one trading day.
- Horizons: 1d, 5d, and 21d overlapping tranches.
- Costs: gross first; 2.5/5/10/25 bp one-way cases are implementation
  diagnostics only, not verdict gates.

## E1 results

Annualized top-versus-equal-weight excess return, gross:

| expression | coverage | 1d | 5d | 21d |
|---|---:|---:|---:|---:|
| local country index | 32 | 16.86% | 8.52% | 3.53% |
| mapped equity-index futures | 6 | 25.37% | 6.09% | 2.79% |
| US ETF next-session open → close | 32 | -2.88% | -2.08% | -1.68% |
| US ETF close → close | 32 | 1.15% | 2.96% | 1.57% |

At 10 bp one-way, only futures remained positive: 11.15% / 1.82% / 1.15%
for 1d / 5d / 21d. ETF close-to-close fell to -10.44% / -1.73% / -0.25%;
ETF open-to-close was already negative gross. The six futures roots are CF,
GX, HI, NK, Z, and ES; this is a narrow diagnostic return panel, not a
notional-sized or broad deployment universe.

## Formal re-verdict

All 23 pre-registered hypotheses currently classified in the
`network_spillover` canonical family were re-measured through the existing
harness IDs, with their recovered registered parameters. No new hypotheses
were registered and `--force` was not used.

| fresh verdict | count |
|---|---:|
| WATCH | 6 |
| WEAK | 8 |
| DEAD | 5 |
| INSUFFICIENT_COVERAGE | 4 |

This is not a proven strategy. WATCH means continue to observe or investigate;
it is not permission to trade. The result therefore stops at research and
keeps the family parked.

## Artifacts

- `run.py` — focused E1 runner; no ASADO pipeline stages invoked.
- `metrics.csv` — all expression × horizon × cost cases.
- `daily_series.parquet` — captured daily portfolio paths.
- `formal_reverdict_summary.json` — per-hypothesis formal results.
- `manifest.json` — frozen input and ETF-cache hashes.
