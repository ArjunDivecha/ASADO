# Mine 6 — Ground-Truth Return Math for the Long-Only Country-ETF Book

**Date:** 2026-07-02 | **Analyst:** evidence miner 6 | **Status:** complete, all numbers computed from read-only DB queries

**Databases (read-only):**
- Main warehouse: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb` (`t2_master` 1MRet, `t2_levels_daily` Tot Return Index, `ff_factors` RF)
- Loop DB: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb` (`combiner_scores_daily`, `etf_prices_daily`, `etf_t2_map`)

**Machine-readable results:** `mine_math_results.json` (same directory). Run logs: `mine_math_run.log`, `mine_math_followup.log`.

---

## 0. Data alignment facts (verified, not assumed)

1. **`t2_master` `1MRet` at first-of-month T = USD total return realized DURING month T.** Verified against `Tot Return Index` month-end levels (corr 0.992; the two apparent mismatches, Mar/Apr-2020 Brazil, compound to the identical two-month return — a month-end sampling boundary, same underlying series). USD-ness verified: Brazil Jan-2020 = −7.4% matches MSCI Brazil USD (local Bovespa was −1.6%; BRL −5.8%). Monthly panel is complete 34 countries 2006-01→2026-06 except Saudi Arabia (starts 2014-09) and Vietnam (starts 2006-12); cross-sectional stats use available names per month. The 2026-07 row is NaN (month in progress) and excluded.
2. **`t2_factors_daily` `1DRet` at date t = FORWARD return close(t)→close(t+1) on a CALENDAR-day grid** (verified: corr 1.0 with TRI(t+1)/TRI(t)−1). Weekend rows are stale/zero and the Fri→Mon move sits on the Sunday row — so naive business-day joins on `1DRet` silently drop weekend-crossing returns. **All daily returns below are therefore built directly from `Tot Return Index` levels restricted to the combiner business-day grid:** fwd(t) = TRI(next business day)/TRI(t) − 1, clipped at ±50%. This is the PIT-safe convention: signal dated t (information through close t) earns the t→t+1 close-to-close return.
3. **`combiner_scores_daily`:** business days only (Mon–Fri roughly equal counts), 2005-01-03→2026-06-30, 5,581 days, 29.9 names/day average, 31 countries (universe excludes ChinaH, NASDAQ, US SmallCap).
4. **Risk-free:** Ken French US RF from `ff_factors` (monthly + daily), auto-detected percent units, converted to decimal (0.38%/mo average 2023+ — sane).

---

## 1. Monthly ground truth: dispersion, EW portfolio, perfect-foresight bound

Panel: 246 months (2006-01→2026-06) × 34 countries, USD total returns.

| Metric | 2006–2026 | 2015–2026 |
|---|---|---|
| Mean cross-sectional std of monthly returns | **4.32%/mo** | 4.27%/mo |
| Annualized cross-sectional dispersion (×√12) | **15.0%** | 14.8% |
| EW 34-country portfolio: ann. return (geometric) | **7.8%** | 7.7% |
| EW ann. vol | 17.9% | 15.3% |
| EW Sharpe (vs FF US RF) | **0.42** | 0.44 |
| EW max drawdown | **−57.7%** (GFC) | −29.0% |
| Perfect-foresight top5 − bottom5 spread, mean | **13.0%/mo (~156%/yr)** | 13.0%/mo |
| ...median / p10 / p90 | 11.5% / 6.5% / 20.5% | 11.6% / 6.7% / 20.2% |
| **Perfect-foresight LONG-ONLY bound (top5 − EW), mean** | **6.6%/mo (~79%/yr)** | 6.6%/mo |

Reading: the raw material is enormous and stable across decades — a clairvoyant long-only top-5 picker beats equal weight by ~79%/yr. Any real signal harvests a few percent of this. Dispersion has NOT compressed post-2015; the opportunity set is intact. The EW base portfolio itself is a ~7.8%/yr, Sharpe-0.42 asset with a −58% worst drawdown fully invested — this is the beta the book rides on, and the reason a cash dial matters.

## 2. Fundamental-law translation of IC 0.057 (analytic expectation)

Assumptions, stated explicitly:
- Daily rank IC 0.057 treated as Pearson IC of a standardized score vs next-day cross-sectional returns (linear approximation).
- Measured daily cross-sectional dispersion across the ~30 scored names: mean 1.05%, **median 0.95% (used, robust to crisis fat tails)**.
- Long-only top-k tilt: E[topK mean return − universe mean] = IC × σ_cs × z̄(k), where z̄(k) = expected mean of the top-k order statistics of 29 standard normals (Monte-Carlo, 200k draws): z̄(5)=1.427, z̄(8)=1.175.

| Book | Expected daily active (gross) | Annualized (×252) |
|---|---|---|
| Top-5 of 29, 1d hold | 7.7 bp/day | **+19.4%/yr** |
| Top-8 of 29, 1d hold | 6.3 bp/day | +16.0%/yr |

The empirical realization (§3) comes in ABOVE this (11.3 bp/day) because the combiner score is a calibrated return forecast — its extreme values carry more information than a rank-normal assumption credits, and dispersion is fat-tailed upward. The fundamental law is the conservative anchor; the empirical number is the measured truth.

## 3. THE KEY NUMBER — empirical realized long-only spread (index returns, PIT-safe)

Method: each business day t, rank names by `combiner_scores_daily` value; hold top-k equal-weighted; earn fwd(t) = close(t)→close(t+1) index return; spread vs mean of all scored names that day. h-day holds are h overlapping tranches (rolling mean of daily top-k weight rows, renormalized). "skip1" lags weights one extra business day. Realized daily rank IC over the sample: **0.0552 (t=16.8)** — independently reproduces the harness digest's 0.057.

Full sample 2005-01→2026-06, 5,580 days. Costs: annual drag = 252 × 2 × one-way turnover × one-way bps.

| Expression | bp/day gross | Ann gross | t | IR | 1-way TO/day | Net 5bp | Net 10bp | Net 15bp | Net 25bp |
|---|---|---|---|---|---|---|---|---|---|
| **top5 h=1** | **11.3** | **+28.5%** | 13.2 | 2.81 | 0.378 | +18.9% | **+9.4%** | −0.1% | −19.2% |
| top5 h=1 skip1 | 4.4 | +11.0% | 5.4 | 1.14 | 0.379 | +1.4% | −8.1% | — | — |
| **top5 h=5** | **5.1** | **+12.9%** | 8.3 (NW-t 9.0) | 1.76 | 0.148 | +9.2% | **+5.5%** | +1.7% | −5.8% |
| top5 h=5 skip1 | 3.2 | +8.1% | 5.2 | 1.11 | 0.149 | +4.3% | +0.6% | — | — |
| top5 h=21 | 1.7 | +4.2% | 4.3 | 0.91 | 0.041 | +3.2% | +2.1% | +1.1% | −1.0% |
| top8 h=1 | 9.2 | +23.2% | 14.4 | 3.05 | 0.320 | +15.1% | +7.1% | −1.0% | — |
| top8 h=5 | 3.7 | +9.3% | 7.8 | 1.67 | 0.129 | +6.0% | +2.8% | −0.5% | — |
| top8 h=21 | 1.0 | +2.6% | 3.6 | 0.77 | 0.037 | +1.7% | +0.8% | — | — |

(t-stats for h>1 are overstated by overlap; the NW-t(L=10) for top5 h=5 is 9.0 — still decisive. Breakeven one-way cost for top5 h=1 ≈ 14.9bp, matching the digest's 14.2bp for the LS book.)

**Three honesty checks that change the conclusion:**

**(a) Sub-period decay (top5 h=1, bp/day gross):** 2005–10: **18.9** → 2011–15: 11.1 → 2016–20: 7.1 → 2021–26: **7.0** (t=4.3). The signal is real in the recent decade but at ~60% haircut vs full sample. 2016+ numbers: h=1 gross +17.7%/yr (net at 10bp ≈ **−1.2%** — dead), h=5 gross +7.4%/yr (net at 10bp ≈ −0.1%, at 5bp +3.6%).

**(b) Skip-1 test: ~61% of the h=1 alpha lives in the first 24 hours** (11.3 → 4.4 bp/day). You must trade the same close the signal is formed on. This is feasible in principle (all 31 foreign closes for date t occur before the US 4pm close; a 3:50pm ET compute + MOC order works) — but it makes the next check decisive.

**(c) ETF tradability check — the most important table in this mine.** The loop DB has 13 months of actual US-listed ETF closes (264 overlapping days). Same signal, same days, same top-5 construction, spread computed on ETF close(t)→close(t+1) vs on index closes:

| Hold | Index bp/day | ETF bp/day | **Capture ratio** |
|---|---|---|---|
| h=1 | 9.6 | 3.5 | **0.36** |
| h=5 | 3.1 | 1.9 | **0.60** |

US-listed country ETFs price foreign information during US hours — by the time you buy the ETF at the US close, roughly two-thirds of the next-day index alpha is already in the price at h=1. Two independent measurements agree: capture 0.36 ≈ skip1/skip0 ratio on index returns (4.4/11.3 = 0.39). Longer holds amortize the timing loss (0.60 at h=5, extrapolating ~0.75–0.85 at h=21). **This is the LL_LEADER_GAP tradability trap, measured, and it applies to the combiner too.**

## 4. Whole-book simulation ($100k, long-only + cash)

Historical simulation on the combiner grid (2005–2026), index returns, daily FF RF on the cash sleeve, costs = 2 × TO × bps scaled by invested fraction. Benchmark = EW of scored universe: **8.6%/yr, Sharpe 0.49, maxDD −59%.**

| Book | Ann ret (geo) | Vol | Sharpe | MaxDD |
|---|---|---|---|---|
| top5 h=1, 100% invested, 10bp | 18.3% | 20.2% | 0.85 | −45.7% |
| **top5 h=5, 100% invested, 10bp** | **14.1%** | 18.4% | **0.72** | −43.2% |
| **top5 h=5, 70% + 30% cash, 10bp** | **10.7%** | 12.9% | **0.72** | **−31.7%** |
| top8 h=5, 70/30, 10bp | 8.7% | 12.3% | 0.60 | −34.9% |
| top5 h=5, 70/30, gross | 16.6% | 12.9% | 1.12 | −29.5% |

The 70/30 dial does exactly what it should: cuts maxDD from −43% to −32% at identical Sharpe. **These index-based full-sample numbers are the CEILING.** Apply the two measured haircuts — recent-regime decay (~0.57×) and ETF capture (0.60 at h=5) — and the realistic forward book is:

### Expected annual active return on a $100k long-only book (vs EW benchmark)

| Book | Gross ceiling (full-sample, index) | Realistic gross (2016+ decay × ETF capture) | Net @5bp 1-way | Net @10bp 1-way |
|---|---|---|---|---|
| **Combiner top-5, weekly tranches (h=5)** | +12.9%/yr ($12,900) | **+4.4%/yr ($4,400)** | **+0.7% to +4.0%/yr ($700–4,000)** | **−3.0% to +0.3%/yr** |
| Combiner top-8, h=5 | +9.3%/yr | +3.2%/yr | 0 to +2.5%/yr | negative |
| Combiner top-5, h=1 (MOC daily) | +28.5%/yr | +6.4%/yr (capture 0.36) | **negative** (cost 9.5%/yr) | negative |
| Blended slow book (top5 h=21 + SOV_2S10S + SIM_NBR 21d tiers) | +4–6%/yr | +2.5–3.5%/yr (capture ~0.8) | +1.5–2.5%/yr | +0.5–1.5%/yr |

Range on the flagship reflects: optimistic = full-sample gross × ETF capture (7.7% gross); conservative = 2016+ gross × capture (4.4%). The blended slow row uses this mine's h=21 empirics plus the digest's slow-signal LS stats at ~50% long-only capture; its virtue is turnover (0.04/day) — it survives 10bp — and higher ETF capture.

**Bottom line for the book design:** total expected return of the flagship (70% top-5 h=5 + 30% cash, 5bp achievable-cost execution on liquid names) ≈ EW base 7.7% × 0.7 + cash 1.3% + net active 1–4% ≈ **8–11%/yr, Sharpe ~0.55–0.75, maxDD ~−30%** — versus 7.7%/Sharpe 0.44/−29% (2015+) for plain EW. The daily h=1 expression, despite its spectacular index-based stats (IR 2.81, t=13), is **not tradable in US-listed ETFs at any realistic cost** once the 0.36 capture ratio is applied. Weekly-tranche is the fastest defensible frequency; cost control below 5bp one-way (liquid tickers, midpoint/MOC execution) is worth more than any signal improvement.

**Caveats:** (i) combiner components selected in-sample 2026-06 — the 2021–26 sub-period (7.0 bp/day, t=4.3) partially but not fully mitigates; treat even "realistic" numbers as ceilings. (ii) ETF capture measured on 13 months, unadjusted closes (dividend noise, roughly cross-sectionally neutral). (iii) Index returns are MSCI-style USD country returns, not NAV — tracking difference (~20–60bp/yr expense drag) not modeled; it hits base return, not the cross-sectional active return. (iv) On $100k, IBKR commissions ($0.35–1/order) add ~0.5–1bp/trade — inside the 5–10bp cost assumptions.

---

## Appendix — code

Primary script (full source, as run): `mine_math_run.py` in this directory. Follow-up (ETF h=5 capture, 2016+ sub-periods, NW-t): inline heredoc, logged in `mine_math_followup.log`. Core construction:

```python
# PIT-safe daily forward returns on the combiner business-day grid
T   = tri.pivot(index="date", columns="country", values="tri").reindex(grid).ffill(limit=5)
FWD = (T.shift(-1) / T - 1).clip(-0.5, 0.5)          # close(t) -> close(t+1bd), labeled t
S   = scores.pivot(...).reindex(FWD.index)            # signal at t = information date
# top-k equal-weight, h overlapping tranches, one-way turnover = sum|dw|/2
r = S.where(valid).rank(axis=1, ascending=False); W = (r <= k).astype(float)
W = W.div(W.sum(axis=1), axis=0).rolling(h, min_periods=1).mean()
W = W[valid].div(W[valid].sum(axis=1), axis=0)
spread = (W * FWD).sum(axis=1) - FWD.where(valid).mean(axis=1)
net_ann = spread.mean()*252 - 252 * 2 * (W.fillna(0).diff().abs().sum(axis=1)/2).mean() * c_oneway
```

Full numeric results: `mine_math_results.json`.
