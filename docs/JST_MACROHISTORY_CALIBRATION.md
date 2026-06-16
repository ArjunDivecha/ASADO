# JST Macrohistory — Long-Cycle Calibration Corpus

*Added 2026-06-15. Addresses the long-cycle / once-in-a-century tail gap in the
regime + bear-bottom conditional-return layers.*

## Why

ASADO's live factor surface starts ~2000 and is monthly. That window contains
only ~3 true crises (2000, 2008, 2020) — far too few to estimate regime
transition behavior or calibrate tail returns. The Jordà-Schularick-Taylor
Macrohistory Database (Release 6, **1870–2020, annual**) supplies the missing
tail population: **65 banking-crisis onsets** across the 13 in-universe
developed markets, plus Depressions, world wars, and hyperinflations.

## The one rule

**JST is a calibration corpus, not a factor feed.** It is annual and ends 2020.
- Loaded to its **own** DuckDB table `jst_macrohistory`.
- **Never** unioned into `unified_panel` / `feature_panel`; **never** forward-filled
  to monthly. (Verified: `SELECT COUNT(*) FROM unified_panel WHERE source='jst'` = 0.)
  Doing otherwise repeats the deprecated `wb_commodity_factor_panel` mistake —
  tiling static history across modern months → degenerate `_CS` variants.
- The live monthly system never reads the raw 150-year panel — only the small
  distilled tables below.

## Scope

13 JST countries that are in ASADO's tradable 34-universe: Australia, Canada,
Denmark, France, Germany, Italy, Japan, Netherlands, Spain, Sweden, Switzerland,
U.K., U.S. The 5 JST-only DMs (Belgium, Finland, Ireland, Norway, Portugal) are
dropped; they can return as a pooled robustness overlay if a tail cell ever goes
thin (none currently do — min episodes per cell ≥ 65 for crisis states).

## Pipeline

```
collect_jst_macrohistory.py   raw R6 xlsx (Data/raw/jst/) ─► Data/processed/jst_macrohistory_panel.parquet
                              tidy annual (date, year, country, iso3, variable, value, source='jst')
setup_duckdb.py               ─► isolated table  jst_macrohistory  (NOT unified_panel)
calibrate_jst_bearbottom.py   ─► regime/calib/jst_bearbottom_conditional_returns.{parquet,json}
                                 regime/calib/jst_calibration_report.md
```

`collect_jst_macrohistory.py` is **not** a nightly collector — JST R6 is a static
release. Re-run only when macrohistory.net publishes a new release
(`--refresh-download` re-pulls the xlsx).

## What the calibration produces

Real (CPI-deflated) annualized forward 1/3/5-year return distributions for
equity / bond / bill, conditional on:
- **drawdown buckets** (0/-10/-20/-35%+ real drawdown from running peak),
- **banking-crisis onset** (`crisisJST==1`),
- **post-crisis 1–3y**, and **normal**.

Each cell reports n, mean, median, std, p10/p25/p50/p75/p90, P(neg), plus an
`ex_hyperinflation` robustness variant. Cells with < 8 distinct episodes are
flagged THIN.

Headline (forward 3y real equity, all 13 DMs, 1870–2020):

| State | episodes | median | p10 | P(neg) |
|---|---|---|---|---|
| drawdown ≤ -35% | 70 | +8.8% | -12.0% | 27% |
| drawdown -20…-35% | 145 | +4.5% | -11.1% | 33% |
| banking-crisis onset | 65 | +7.0% | -1.8% | 18% |

Deeper real drawdowns historically precede higher forward real equity returns
(mean-reversion at bottoms), but with a fat left tail — the p10 column is the
once-in-a-century downside the modern sample cannot see.

## How the live layers use it (current wiring)

- The rule-based regime tagger (`regime/src/regime_tagger.py`) is **unchanged**;
  JST supplies priors/tail tables it can shrink toward (kept additive by choice).
- The bear-bottom / conditional-return analysis reads
  `regime/calib/jst_bearbottom_conditional_returns.json` for tail distributions
  instead of inventing tails from the 3 modern crises.

Deferred (not built yet, by decision): a full HMM/Markov regime model fit on JST.
The 150-year corpus makes one estimable later; current scope is ingest + tail
tables only.

## Source

Jordà, Ò., Schularick, M., Taylor, A.M. *Macrohistory Database*, Release 6.
University of Bonn MacroFinance & MacroHistory Lab, https://www.macrohistory.net/database/
(CC-licensed). Raw file: `Data/raw/jst/JSTdatasetR6.xlsx`.
