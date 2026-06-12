# Bloomberg Skill Enhancements — Six New Data Layers (2026-06-12)

**Status:** Live end-to-end. All six layers collected, backfilled, loaded into the loop
DuckDB, wired into the nightly job (now 27 steps), and rendering in the daily brief.

**Why this batch exists (plain English):** Arjun rebuilt the Bloomberg skill with a much
deeper knowledge base (verified BQL syntax, ticker grids from findatapy, ECO survey
fields, FX vol-surface conventions). This session mined that new knowledge for data the
warehouse could not reach before — most importantly **BQL historical sovereign ratings**
(impossible via plain BDH) and the **economic surprise layer** (what printed vs what
economists expected — returns react to the gap, not the level).

---

## The Six Layers, Easiest → Hardest (as built)

### 1. FX vol butterflies + term slope (extends `collect_market_implied_bbg.py`, v1.0 → v1.2)
- New tickers per pair: `[PAIR]25B1M` (25-delta butterfly = tail/kurtosis premium),
  `[PAIR]V1W` and `[PAIR]V3M` (1-week and 3-month ATM vol).
- New signals in `market_implied_signals`:
  - `FX_BF25_Z252` — butterfly z. A rising butterfly = the market pays up for BOTH tails.
  - `FX_VOL_TERM_PCT` / `_Z252` — 1W vol minus 3M vol. Normally negative; a POSITIVE
    slope = the market prices more turbulence THIS WEEK than over the quarter — the
    signature of an imminent scheduled event (election, peg decision, crisis weekend).

### 2. CDS curve slope (extends `collect_sovereign_daily_bbg.py`, v1.0 → v1.1)
- 1Y CDS added by tenor substitution on the existing 5Y names (`... SR 1Y Corp`):
  18 of 20 CDS countries have a quoted 1Y (Poland and Vietnam don't — structural).
- New table `sovereign_signals`: `SOV_CDS_SLOPE_BP` (5Y − 1Y) + z. Normally positive.
  **Inversion (1Y above 5Y) = the market prices imminent default risk** — the Greece-2011 /
  Turkey-2018 / Russia-2022 signature. The brief flags any inversion nightly.

### 3. Daily 2s10s government curve (same collector, same loader)
- 2Y generic yields added for 27 countries (map from the corrected monthly
  `COUNTRY_TICKERS`; Brazil's dead `GEBR2Y Index` replaced with `GTBRL2Y Govt`/`YLD_YTM_MID`
  in BOTH the daily and monthly collectors).
- `sovereign_signals`: `SOV_2S10S_PCT` (10Y − 2Y) + z — the daily recession/regime read
  per country. The monthly warehouse already had a 10Y−2Y slope but only month-end;
  this one moves daily and feeds the brief when |z| ≥ 2.

### 4. Historical sovereign credit ratings via BQL (`collect_sov_ratings_bql.py`, NEW)
- **ASADO's first BQL collector.** Raw blpapi against `//blp/bqlsvc` with the
  `clientContext.appName = "EXCEL"` unlock (without it Bloomberg returns a fake
  "not authorized" error).
- **The key discovery — `issuerof()`:** `rating()` on a yield generic returns null, and
  `rating()` on the resolved bond is capped at that bond's issue date. But
  `get(rating(source=SP, dates=range(-20Y,0D, frq=M))) for(issuerof('<anchor>'))`
  returns the ISSUER's monthly rating path. Anchors: the country's **5Y CDS contract**
  where one exists (the CDS entity is the sovereign itself and carries the standard
  foreign-currency ratings from all three agencies), else the `GT[CCY]10Y Govt` generic.
  The CDS anchor matters: Mexico/South Africa/Turkey local generics resolve to NO entity.
- Result: **33 of 34 countries** (Hong Kong has neither anchor), S&P + Moody's + Fitch,
  monthly back to 2015 (Moody's 2017 — Bloomberg-side depth), on the same 21-point
  numeric scale as the monthly snapshot collector.
- Loader `load_sov_ratings.py` derives **`sov_rating_changes`** — 128 dated events
  (80 downgrades, 48 upgrades). A rating change is a tradeable, dated event; the brief
  shows the last 90 days. Verified against reality: Brazil BBB+→BB downgrade arc,
  Turkey's slide, Saudi's 2023/2025 upgrades.

### 5. FX forwards / NDF-implied carry (extends `collect_market_implied_bbg.py`)
- 3M outright forwards for 25 pairs (the 24 vol pairs + USDDKK — Denmark has no options
  surface but has a liquid forward). NDF roots for capital-controlled currencies:
  `BCN`=BRL, `KWN`=KRW, `NTN`=TWD, `IRN`=INR, `IHN`=IDR, `MRN`=MYR, `PPN`=PHP, `CHN`=CLP.
- **Verified live:** `PX_LAST` on these tickers is the OUTRIGHT forward, not points —
  so carry needs no scale factor: `(fwd/spot − 1) × 4 × 100`, sign-normalized so
  positive = local rates above USD.
- `FX_CARRY_3M_PCT` + `FX_CARRY_Z252`. Sanity check on latest: Turkey +34%,
  Brazil +9%, Switzerland −3.9%, pegs ≈ 0. A carry SPIKE without a central-bank hike
  = devaluation expectation moving into the forwards.

### 6. Economic surprise layer (`collect_eco_surprise_bbg.py` + `load_eco_surprise.py`, NEW)
- For each T2 country and four indicator families — **CPI YoY (31), Unemployment (22),
  GDP headline (17), Markit Manufacturing PMI (20)** — pulls BDH history of
  `ACTUAL_RELEASE` and `BN_SURVEY_MEDIAN` on the ECO release tickers.
  Surprise = actual − survey median, per reference month (first-of-month dates).
- The findatapy grid's CPI/UNEMP/PMI tickers were mostly good; its **GDP tickers were
  almost all dead** — the GDP map was rebuilt by live Terminal probe (only tickers
  carrying BOTH fields kept). No survey-carrying GDP ticker exists for CA/CL/DK/IN/IT/
  NL/PH/CH/TW/TH/TR; no survey unemployment for DK/FR/ES/TH/TR.
- `eco_surprise_signals` (Citi-surprise-style normalization — surprise ÷ trailing 60-month
  std of own surprises, min 12 obs):
  - `ECO_{CPI,UNEMP,GDP,PMI}_SURPRISE_Z` per print
  - `ECO_GROWTH_SURPRISE_Z` = mean(GDP_z, PMI_z, −UNEMP_z) — positive = data beating
  - `ECO_INFL_SURPRISE_Z` = CPI_z — positive = inflation printing hot
- Brief shows latest prints with |z| ≥ 1.5.

---

## Quota / Cost Footprint

All new daily tickers were first-pulled 2026-06-12 (free against the monthly unique-ID
counter thereafter). Nightly incremental cost: ~187 hist hits (market-implied),
~95 (sovereign), ~190 (eco surprise) — well under 0.1% of the daily cap combined.
BQL ratings (~99 queries, ~2 min) are compute-capacity bound, not unique-ID bound.
Everything logs to `Data/work/loop/bbg_quota_log.csv`.

## Nightly Job Wiring (now 27 steps)

New steps in `scripts/loop/loop_daily_job.py`:
- 20 `collect_sov_ratings_bql` → 21 `load_sov_ratings`
- 22 `collect_eco_surprise_bbg` → 23 `load_eco_surprise`
(steps 9/10 and 18/19 now carry the extended sovereign and market-implied families).

## Brief Additions (`build_dislocations.py`)

- "Stretched currencies" block now triggers on ANY of RR / impvol / butterfly /
  vol-term-slope / carry z ≥ |2| and prints all five per country.
- NEW section **"Sovereign curves, ratings & macro surprises"**:
  CDS curve inversions, stretched 2s10s (|z| ≥ 2), rating changes (last 90d),
  hot surprises (|z| ≥ 1.5).

## Verification Done (2026-06-12)

- Curve slopes: Turkey 2s10s −8.1pp (the famously inverted lira curve), all CDS slopes
  positive today, Korea vol-term +3.15 ahead of scheduled news.
- Ratings trajectories match public record for Brazil/Turkey/Saudi/Vietnam/U.S.
- Carry cross-section economically correct (Turkey top, CHF/JPY bottom, pegs ≈ 0).
- All four `--check` loaders PASS; full nightly-mode incremental runs verified clean.

## Coverage Gaps (structural, documented, NOT bugs)

- Hong Kong: no rating anchor (no CDS, no GT generic).
- Poland/Vietnam: no quoted 1Y CDS → no CDS slope.
- 7 countries lack a 2Y generic → no daily 2s10s (Chile, Hong Kong, Malaysia,
  Philippines, Saudi Arabia, Taiwan, Vietnam).
- GDP/unemployment survey gaps listed above; CPI is full-coverage (the most important
  monthly print).

## File Map

| File | Role |
|---|---|
| `scripts/loop/collect_market_implied_bbg.py` v1.2 | FX vol (3 tenors) + RR + BF + forwards/carry + dashboard + commodity curves |
| `scripts/loop/load_market_implied.py` v1.1 | + butterfly/term/carry z-scores |
| `scripts/loop/collect_sovereign_daily_bbg.py` v1.1 | + 1Y CDS, + 2Y yields, Brazil 2Y fix |
| `scripts/loop/load_sovereign_daily.py` v1.1 | + `sovereign_signals` (CDS slope, 2s10s) |
| `scripts/loop/collect_sov_ratings_bql.py` v1.0 NEW | BQL rating history (first BQL collector) |
| `scripts/loop/load_sov_ratings.py` v1.0 NEW | `sov_ratings_monthly` + `sov_rating_changes` |
| `scripts/loop/collect_eco_surprise_bbg.py` v1.0 NEW | ECO actual-vs-survey history |
| `scripts/loop/load_eco_surprise.py` v1.0 NEW | `eco_surprise_monthly` + `_signals` |
| `scripts/loop/loop_daily_job.py` v1.1 | 27-step nightly wiring |
| `scripts/loop/build_dislocations.py` | extended FX block + new curves/ratings/surprises section |
| `scripts/collect_bloomberg.py` | Brazil 2Y ticker fix (monthly map) |

New loop-DB tables: `sovereign_signals`, `sov_ratings_monthly`, `sov_rating_changes`,
`eco_surprise_monthly`, `eco_surprise_signals` (plus extended `market_implied_*` and
`sovereign_daily`). None are unioned into `unified_panel`/`feature_panel` (loop/warehouse
separation preserved).

New parquets under `Data/work/loop/`: `sov_ratings_monthly.parquet`,
`eco_surprise_monthly.parquet` (plus extended `market_implied_daily.parquet`,
`sovereign_daily.parquet`).
