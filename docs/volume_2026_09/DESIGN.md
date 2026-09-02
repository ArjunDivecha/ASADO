# Volume × sentiment × issuance — research design (DRAFT for discussion, 2026-09-02)

Owner request (2026-09-02): investigate volume changes alongside GDELT sentiment changes as
a country-selection signal; look at ETF volume, ETF share issuance, and underlying-index
volume. Ticker lists: `/Users/arjundivecha/Dropbox/AAA Backup/Master Database/Country Bloomberg Data Master T.xlsx`
(sheet `Master`: col A = 34 US-listed ETFs, col D = MSCI local index, col E = MSCI dollar index).
That workbook holds the ticker lists only; it has no volume, share-count, or sentiment data.

Nothing below has been run. No Bloomberg batch, no ledger registration, no harness trial.
One 1-security probe (10 hist hits) was made to settle the data-existence question.

## 1. Prior art (mandatory step zero) — two of the three legs are already dead standalone

| Leg | House record | Status |
|---|---|---|
| ETF share issuance (creations/redemptions) | ASADO ledger family `etf_flows_2026_06`: `ETF_FLOW_21D_Z` as momentum **DEAD** (5d rank IC −0.011, NW-t −2.0, harness v4 2026-07-14); contrarian flip **WEAK** (same IC, deflated Sharpe ≈ 0); ETF short interest **DEAD**. Research-Agenda-2026-07-v2 lists "ETF-flow contrarian (t −2.2)" among the dead alt-data first-order signals. Data exists: `etf_flows` / `etf_flow_signals`, Bloomberg EQY_SH_OUT-derived, 34 ETFs, daily 2010-01 → 2026-09-01. | tested, dead standalone |
| GDELT sentiment | First-order tone "killed by the loop DB, survives only as conditioning" (Agenda v2 §alt-data). `gdelt_narrative_v2` stage 1a (93-var keep-list HGB/ridge) and 1b (1,133-col wide panel) both **DEAD** in the 2017–21 design window, canary FAIL; stage 2 (chain-age freshness) registered, no result. Agenda v2 "Deliberately excluded": standalone GDELT tone. Data exists: `gdelt_factors_daily` (asado.duckdb), 34 T2 buckets, daily 2015-02-18 → 2026-09-01, incl. `country_news_sentiment_TS/_CS`, `attention_shock`, `n_articles`, `tone_dispersion`. | tested, dead standalone; allowed as conditioning |
| Trading volume — ETF or underlying index | **Never tested at country level anywhere in the record.** No loop-DB variable, no hypothesis, no Investment Learnings entry. Only volume on disk is yfinance `etf_prices_daily.volume` from 2025-06 (15 months). Quantpedia: abnormal-volume / high-volume-premium anomalies exist (#0178 Europe OOS Sharpe 0.34/0.39; #1054 US 0.25/0.41; #1129 overnight volume shock 0.83/0.54; #0863 persistence of abnormal volume 0.01) but all are **single-stock and UNSCREENED** for country ETFs. | open lane |

Implication: the defensible study is (i) volume as a new standalone family, and (ii) volume as the
*confirmation* for the two dead legs — the interaction, not a re-run. Re-testing issuance or
GDELT tone standalone would be re-proposing a ledger kill.

## 2. Data — what exists, what needs pulling

**Exists (no pull):** shares outstanding / flows (loop DB `etf_flow_signals`), GDELT daily
features (`asado.duckdb.gdelt_factors_daily`), T2 country returns (marking surface).

**Needs pulling (Bloomberg, OpusBloomberg env):** daily `PX_VOLUME` and `TURNOVER` for the
34 ETFs (`<tkr> US Equity`) and the 34 indices in workbook column D **as given**, 2010-01-01 → today.
Column D is MSCI local-currency for 30 rows, but SPY/QQQ/IWM map to SPX/CCMP/RTY and ASHR maps
to SHCOMP, which is the Shanghai Composite, not ASHR's actual benchmark CSI 300 — that row is
Arjun's mapping choice to confirm. Local (col D) vs dollar (col E) is moot for PX_VOLUME: the
constituents are identical, only the price denomination differs.

**Probe result 2026-09-02 12:38 PT (Terminal live on 10.211.55.3:8194, quota guard clear):**

| Ticker | PX_VOLUME 2026-09-01 | TURNOVER 2026-09-01 |
|---|---|---|
| EWY US Equity | 13,438,943 | 2,378,911,000 |
| MXKR Index (MSCI Korea) | 57,782,563 | 15,634,681,024 |
| MSDLSG Index (MSCI Singapore local) | 151,786,945 | not probed |
| KOSPI Index | 273,600,000 | 18,752,589,174 |
| SHCOMP Index | 56,082,236,872 | not probed |

MSCI country indices DO carry aggregate constituent volume and turnover, so the workbook's
index list works as-is; exchange composites (KOSPI, SHCOMP) are the alternative. TURNOVER
currency/scale units are NOT verified across indices (MXKR looks like USD, KOSPI like KRW
thousands) — every signal below is a within-country ratio, so units cancel by construction.
Cross-country level comparisons of turnover are out of scope for that reason.

Cost: 68 tickers × 2 fields = 136 hist hits (a `hist` request is 1 hit per security-field
regardless of date range). All 34 ETFs and the MSCI indices are already used by ASADO/T2 this
month, so the monthly unique-ID charge should be ~0. Terminal history depth for index volume
will be checked on the first pull (expect 2000+ for MSCI; the ETFs launch 2009–2015).

## 3. Signal definitions (pre-registered transforms — fix BEFORE any feature is computed)

All daily, per country, log-ratio to the country's own trailing history (units cancel).
`ADV_n` = trailing n-day mean of PX_VOLUME, requiring ≥ 0.8·n non-null days.

| Variable | Definition | Source lag |
|---|---|---|
| `VOL_ETF_ABN5` | log(ADV_5 / ADV_252) on ETF PX_VOLUME | 0 (market) |
| `VOL_IDX_ABN5` | log(ADV_5 / ADV_252) on MSCI-index PX_VOLUME | 0 |
| `VOL_ETF_ABN21` | log(ADV_21 / ADV_252) on ETF PX_VOLUME | 0 |
| `VOL_GAP_ABN5` | `VOL_ETF_ABN5 − VOL_IDX_ABN5` (US-side attention net of local attention) | 0 |
| `SENT_CHG21_VOLCONF` | Δ21d of `country_news_sentiment_TS` × exp(`VOL_IDX_ABN5`) = Δsent21 × (ADV_5/ADV_252) on index volume — a strictly positive, monotone volume weight, so the sentiment change is scaled by local volume confirmation but never sign-flipped and never zeroed (a max(z,0) gate would tie roughly half the panel at exactly zero every day and break the harness's bottom bucket arbitrarily) | 0 (GDELT is same-day) |
| `FLOW_X_VOL21` | `ETF_FLOW_21D_Z` × exp(`VOL_ETF_ABN21`) = flow z × (ADV_21/ADV_252) on ETF volume — positive weight only. Multiplying by the signed log-ratio would flip the sign of every flow that arrived on below-normal volume, which is not the mechanism | 0 |

Lag convention (checked in `evaluate_signal.py`): for daily runs the effective lag is
max(publication lag, 1-day execution embargo); `bloomberg_derived` and `gdelt_derived` are not in
`ZERO_LAG_SOURCES`, so publication lag defaults to 1 and the effective lag is 1 — identical to what a
zero-lag source would get. The `source` string is documentation only for these trials.

Corporate-action guard: inherit `load_etf_flows.py`'s 20 % one-day share-change rule (flow
set to NULL that day). Volume has no equivalent guard; a 1-day volume spike is the signal.

## 4. Trials — one new family, `volume_2026_09`, five charged trials

Every trial pre-registers a mechanism and a direction; the harness (v4: 1-day execution
embargo, rank IC with NW-t, top-7 vs EW-34 and top7−bottom7 gross, permutation canary,
deflated Sharpe charged against the family trial count) is the test. Horizons 5d primary,
21d secondary. Coverage gate ≥ 28 countries on ≥ 95 % of dates — and an INSUFFICIENT_COVERAGE
verdict still charges a trial to the family (the `ml_combiner_2026_06` rows in the ledger show
this). So: start 2011-01-01, and use the same 33-name universe (no Saudi Arabia — KSA launched
2015) that `etf_flow_contra_2026_06.yaml` uses. EDEN/INDA (2012), ASHR (2013), MCHI (2011) still
leave the early years thin; a coverage table from the pulled data is computed and checked against
the gate BEFORE the sweep runs, and start dates are moved later if needed, not after a charged
INSUFFICIENT verdict.

| # | Variable | Direction | Mechanism (pre-registered) | Window |
|---|---|---|---|---|
| 1 | `VOL_ETF_ABN5` | higher_is_better | High-volume return premium (Gervais–Kaniel–Mingelgrin): an abnormal volume shock raises visibility and attracts investors who would otherwise not hold the asset, so the country ETF outperforms peers over the following weeks. Tests whether a single-stock anomaly survives at country-basket level. | 2011→ |
| 2 | `VOL_IDX_ABN5` | higher_is_better | Same visibility mechanism measured where the information actually clears — the local market — rather than in the US wrapper. | 2011→ (index history may allow earlier; kept aligned with trial 1) |
| 3 | `VOL_GAP_ABN5` | lower_is_better | ETF volume surging without matching local-market volume is US-side attention/allocator flow with no local information behind it; house prior "surges revert, information sticks" (Compendium 2026-08-14 §2.7) says fade it. | 2011→ |
| 4 | `SENT_CHG21_VOLCONF` | higher_is_better | GDELT tone alone is dead because most tone moves carry no priced information; a tone improvement that coincides with abnormal local trading volume is the subset the market is actually acting on, so it should predict relative return where unconfirmed tone does not. This is the "conditioning" role Agenda v2 reserves for GDELT. | 2015-02→ |
| 5 | `FLOW_X_VOL21` | lower_is_better | Creations that arrive on abnormal ETF volume are chasing flow (retail/allocators after the move); the dead momentum test showed significant negative IC (t −2.0) and the volume condition should isolate the dumb-money component of that reversal. | 2011→ |

Optional 6th (not recommended at first pass): "attention without volume" — z(`attention_shock`) −
z(`VOL_IDX_ABN5`) as an underreaction proxy. Adds a trial to the deflated-Sharpe count for a
weaker prior; hold it for a second round if 4 shows anything.

## 5. Execution plan (once agreed)

1. `scripts/loop/collect_volume_bbg.py` — OpusBloomberg conda env; `hist_batch` PX_VOLUME +
   TURNOVER for 68 tickers, 2010-01-01→today; incremental atomic cache; append-only quota log;
   timestamped backup of any prior parquet → `Data/work/loop/volume_daily.parquet`.
   1-security test first (done for 5 tickers above).
2. `scripts/loop/load_volume.py` — ASADO venv; loop tables `volume_daily` (raw tidy) and
   `volume_signals` (§3 variables, joining `etf_flow_signals` and `gdelt_factors_daily`).
   Mirrors the `collect_etf_flows_bbg.py` / `load_etf_flows.py` split (the Bloomberg env has
   no duckdb). Idempotent rebuild; `--check` mode; FAIL-IS-FAIL.
3. `config/sweeps/volume_2026_09.yaml` (draft written alongside this doc) →
   `sweep_signals.py --dry-run` → run. Five trials charged to `volume_2026_09`.
4. Investment Learnings entry via the `verdict` skill regardless of outcome; Bloomberg
   lesson already appended to the skill's `lessons.md`.

Work lives in ASADO (this directory), not in Fable Daily Trading — FDT's CLAUDE.md marks
ASADO read-only from the trading repo, and this is signal research, not execution.

## 6. Decisions needed before anything is charged

1. **Route:** ASADO harness family (recommended — it is the house's only idea→evidence path
   and the trial accounting is what makes a WATCH/PROMISING verdict mean anything) vs an
   uncharged exploratory notebook first.
2. **Underlying index:** MSCI local index from the workbook (recommended; verified to carry
   volume; it is the ETF's actual benchmark) vs exchange composites (KOSPI, SHCOMP, …) which
   are broader than the ETF's basket.
3. **Directions for trials 3 and 5** are pre-registration commitments. Recommendations are
   above; flip them before registration if your prior differs. The harness records the IC
   sign either way, but a wrong-way direction is still a charged trial.
4. **Include the optional 6th trial or not.**
