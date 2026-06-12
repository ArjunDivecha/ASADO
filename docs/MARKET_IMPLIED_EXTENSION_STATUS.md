# ASADO Market-Implied Stress Extension — Implementation Status

**Date:** 2026-06-11
**Status:** Live end-to-end — collector + loader wired into the nightly loop job (steps 18–19),
brief context section rendering, detector D10 firing. Full 2006+ history backfilled and
validated against known market events.

---

## Why This Layer Exists (plain-English)

The warehouse already had *backward-looking* currency information: realized currency vol
(T2 daily), monthly FX levels (ECB), REER. It had **nothing forward-looking from the options
market** — no price of fear. This layer adds three families of daily, market-priced,
forward-looking stress data from Bloomberg:

1. **FX options surfaces** — what the options market charges for currency insurance.
   - *1M ATM implied vol* = how big the market thinks currency moves will be.
   - *25-delta risk reversal (RR)* = how much MORE the market pays for crash protection than
     for rally participation. A spiking RR means traders are paying up for devaluation
     protection — the cleanest daily read on currency fear that exists, including
     **peg-break pricing** for the Hong Kong dollar and Saudi riyal.
2. **Global risk dashboard** — VIX and VIX3M (equity vol now vs 3 months out — when the
   ratio inverts below 1.0, stress is acute), MOVE (bond-market vol), US high-yield and
   investment-grade credit spreads (Bloomberg natives with 30+ year history), and two
   dollar indices (DXY, BBDXY).
3. **Commodity futures curves** — 1st vs 2nd month contracts for WTI, Brent, copper, gold,
   natgas. Front trading ABOVE second (backwardation) = the market is paying a premium for
   immediate delivery = physical tightness.

The loop's whole premise is finding places where subsystems disagree. This layer gives the
detectors an entirely new "subsystem" to disagree with: the options market.

---

## What Was Built

### Collector (Bloomberg side, OpusBloomberg conda env)

- `scripts/loop/collect_market_implied_bbg.py`
  - 65 tickers in ONE `hist_batch` request (~20s, ~65 API hits/night)
  - Nightly mode pulls the last 15 days; `--backfill` pulls full history from 2006-01-01
  - Sanity bounds per family (implied vol (0, 200], |RR| ≤ 50, OAS (0, 50], VIX/MOVE
    (0, 400], commodity floor −100 so WTI's −37.63 print survives); >5% of a series out of
    range = unit error = abort, parquet untouched (FAIL-IS-FAIL)
  - Atomic merge-write to `Data/work/loop/market_implied_daily.parquet`
    (new rows win on `(date, country, variable)`)
  - Append-only quota log: `Data/work/loop/bbg_quota_log.csv`
    (timestamp, script, operation, est_hits, rows, elapsed, status)

### Loader (project venv, loop DuckDB)

- `scripts/loop/load_market_implied.py`
  - Idempotent rebuild of `market_implied_daily` (raw) + `market_implied_signals` (derived)
  - Z-scores use a **shifted trailing 252d baseline** (today's spike never inflates its own
    baseline), require ≥ 60 observations and positive std, and are omitted — never
    zero-filled — when history is insufficient
  - `--check` mode for verification

### Wiring

- `scripts/loop/loop_daily_job.py` — steps 18 (`collect_market_implied_bbg`, conda env) and
  19 (`load_market_implied`, project venv); same conda/venv split as the other Bloomberg steps
- `scripts/loop/build_dislocations.py` v1.2:
  - new brief context section **"Market-implied stress (FX options, vol, credit, curves)"**
    — global dashboard line + stretched currencies (|252d z| ≥ 2) + unusual futures curves
  - new detector **D10** (below)

---

## Ticker Inventory (all 65 verified with live 1-security pulls 2026-06-11)

### FX options — 24 pairs × {V1M, 25R1M} = 48 series (`... Curncy`, PX_LAST)

```
EURUSD GBPUSD AUDUSD USDJPY USDCAD USDCHF USDSEK USDBRL USDCLP USDMXN
USDCNH USDHKD USDINR USDIDR USDKRW USDMYR USDPHP USDSGD USDTWD USDTHB
USDPLN USDZAR USDTRY USDSAR
```

Pair→country mapping: EURUSD broadcasts to France/Germany/Italy/Netherlands/Spain;
USDCNH to ChinaA + ChinaH; every other pair maps to one T2 country. **29 of 34 countries
covered.** Structurally uncovered: Denmark (DKK pegged to EUR, no liquid surface), Vietnam
(managed VND), and U.S./NASDAQ/US SmallCap (USD is the numeraire — dollar stress lives in
the GLOBAL rows).

### Risk dashboard — 7 series (GLOBAL)

| Ticker | Variable | History |
|---|---|---|
| VIX Index | RISK_VIX | 2006+ (Bloomberg has 1990+) |
| VIX3M Index | RISK_VIX3M | 2006+ |
| MOVE Index | RISK_MOVE | 2006+ |
| LF98OAS Index | RISK_HY_OAS | 2006+ (US HY OAS, %) |
| LUACOAS Index | RISK_IG_OAS | 2006+ (US IG OAS, %) |
| DXY Curncy | RISK_DXY | 2006+ |
| BBDXY Index | RISK_BBDXY | 2006+ |

### Commodity curve — 10 series (GLOBAL)

`CL1/CL2` (WTI), `CO1/CO2` (Brent), `HG1/HG2` (copper), `GC1/GC2` (gold), `NG1/NG2`
(natgas), all `... Comdty` generics.

---

## Sign Convention (memorize this one)

Bloomberg quotes a risk reversal as **base-currency calls minus puts**. For `USDXXX` pairs a
positive RR = USD calls bid = premium on local-currency DEPRECIATION. For `XXXUSD` pairs
(EUR/GBP/AUD) a positive RR means the opposite — so the collector **flips the sign for
XXXUSD pairs** before storage. Result, everywhere in ASADO:

> **`FX_RR25_1M_PCT` positive = the options market is paying a premium for that country's
> currency to fall.**

---

## DuckDB Tables (loop DB — `Data/loop/asado_loop.duckdb`)

Both tidy `(date, country, value, variable, source)`.

### `market_implied_daily` (raw, source='bloomberg')

| Variable | Entity | Meaning |
|---|---|---|
| `FX_IMPVOL_1M_PCT` | 29 countries | 1M ATM implied vol, annualized % |
| `FX_RR25_1M_PCT` | 29 countries | 25Δ 1M risk reversal, vol pts, sign-normalized (above) |
| `RISK_VIX`, `RISK_VIX3M`, `RISK_MOVE`, `RISK_HY_OAS`, `RISK_IG_OAS`, `RISK_DXY`, `RISK_BBDXY` | GLOBAL | dashboard levels |
| `CMD_CL1` … `CMD_NG2` | GLOBAL | generic 1st/2nd contract settles |

### `market_implied_signals` (derived, source='derived')

| Variable | Entity | Meaning |
|---|---|---|
| `FX_IMPVOL_Z252`, `FX_RR25_Z252` | 29 countries | z vs own shifted trailing 252d |
| `RISK_VIX_TERM_RATIO` | GLOBAL | VIX3M / VIX; **< 1 = inverted = acute stress** |
| `RISK_*_Z252` | GLOBAL | z of each dashboard series |
| `CMD_<ROOT>_CURVE_PCT` | GLOBAL | (front/second − 1) × 100; **> 0 = backwardation** |
| `CMD_<ROOT>_CURVE_Z252` | GLOBAL | z of curve shape (guarded against ≤ 0 front prints) |

---

## Detector D10 — A10: FX Options vs Equity (v1, live 2026-06-11)

Two conflict shapes, both per-country, both direction `flag`:

| Conflict | Condition | Severity |
|---|---|---|
| `fx_options_stress_unpriced_by_equity` | RR z ≥ 2.0 **or** implied-vol z ≥ 2.5, while \|21d equity z\| ≤ 0.75 | the stretched options z (+) |
| `equity_stress_unconfirmed_by_fx_options` | 5d equity z ≤ −1.5 while RR z **and** vol z ≤ 0.5 | the equity z (−) |

- The 21d "price has not resolved" gate is what separates a *dislocation* from a mere
  *stretched surface*: Indonesia and Chile had stretched surfaces on the first run but did
  NOT fire because their equity had already moved. Switzerland fired (CHF crash premium,
  RR z +2.28, equity flat).
- **Pegs are included** (unlike D4's spot-FX leg): a near-zero peg surface waking up IS
  peg/devaluation risk getting priced. Peg rows (Hong Kong, Saudi Arabia) carry a
  `peg_note` because z's off a near-zero baseline run hot — read as repricing, not magnitude.
- Structural skips: U.S./NASDAQ/US SmallCap, Denmark, Vietnam.
- Staleness: surface silent > 7 calendar days → loud `DETECTOR_DEGRADED` row, never a
  silently-narrower scan.
- Rows flow through the standard persistence engine
  (new → persisting/intensifying/fading → resolved).

---

## Quota Economics (bloomberg-skill limits.md discipline)

- All 65 tickers were first-pulled 2026-06-11, so they are **free against the monthly
  unique-security counter** from now on.
- `HistoricalDataRequest` costs 1 hit per (security, field) **regardless of date range** —
  the 20-year backfill cost the same ~65 hits as one nightly increment.
- Nightly steady-state: ~65 hits ≈ 0.013% of the ~500k/day cap.
- Every pull appends to `Data/work/loop/bbg_quota_log.csv`.

---

## Verification Snapshot (2026-06-11 backfill)

- Parquet: **387,145 rows**, 2006-01-02 → 2026-06-11; 75 mapped series, 0 empty.
- History validated against famous prints:
  - WTI front month **−37.63 on 2020-04-20** (the negative-oil day) — survives the sanity floor
  - TRY risk reversal **11.6 in Aug-2018**, **12.5 in Dec-2021** (lira crises)
  - BRL risk reversal **22.9 in Oct-2008**
  - HY OAS max **19.71** (2008), VIX max **82.69** (Mar-2020)
  - HKD implied vol 2019 peak **1.5** (peg-stress episode) vs 0.745 today
- `load_market_implied.py --check`: PASS — 29 countries on both FX variables,
  388,082 signal rows.
- First D10 run: 5 rows (Switzerland A-type; Hong Kong/Japan/Mexico/South Africa B-type),
  with the eq21 gate correctly suppressing already-repriced Indonesia/Chile.

---

## Known Caveats

- **Peg z-scores run hot.** USDHKD/USDSAR surfaces sit near zero for years; any wake-up
  produces large z's. D10 annotates these rows; do not read peg severities as magnitudes.
- 25Δ RR for NDF surfaces (KRW/TWD/INR/IDR/PHP/MYR) reflects offshore pricing, which can
  detach from onshore policy reality in capital-control regimes.
- The risk dashboard and commodity curves are GLOBAL rows — country attribution
  (e.g. Brent backwardation → importers vs exporters) is deliberately left to detectors
  and Layer 2, not baked into the data.
- ~~3M tenors follow the same ticker pattern but are NOT yet pulled~~ **Done 2026-06-12:**
  1W + 3M ATM vol, 25Δ butterflies, and 3M forward-implied carry are now collected
  (collector v1.2) — see `docs/BBG_SKILL_ENHANCEMENTS_2026_06_12.md`.
- `market_implied_*` lives in the loop DB only; it is NOT unioned into `unified_panel`/
  `feature_panel` (consistent with the loop/warehouse separation).

---

## File Map

| File | Role |
|---|---|
| `scripts/loop/collect_market_implied_bbg.py` | Bloomberg collector (conda env, parquet only) |
| `scripts/loop/load_market_implied.py` | Loop-DB loader + signal derivation (project venv) |
| `scripts/loop/loop_daily_job.py` | Nightly orchestration (steps 18–19) |
| `scripts/loop/build_dislocations.py` | D10 detector + brief context section |
| `Data/work/loop/market_implied_daily.parquet` | Raw panel (collector-owned) |
| `Data/work/loop/bbg_quota_log.csv` | Append-only quota log |
| `Data/loop/asado_loop.duckdb` | `market_implied_daily` + `market_implied_signals` |
