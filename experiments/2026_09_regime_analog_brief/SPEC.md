# Regime-Analog Context Brief — pre-registration

**Date written:** 2026-09-02, BEFORE any forward return was computed.
**Status:** CONTEXT-TIER DESCRIPTIVE BRIEF. Not a signal, not a hypothesis registration,
not a ledger entry. No country ranking or trade list is a deliverable of this work.

## Prior verdicts this brief must not pretend away

History-as-predictor has been tested in ASADO four times and died every time:

| Experiment | Verdict | Evidence |
|---|---|---|
| Strategy #1 PCA world-state analogs | DEAD (NO-GO) | `docs/strategy/lessons.md:1-20`; IC≈0, sticky basis, n≪p |
| `regime/` v2 regime conditioning | DEAD | `regime2.md:12-18`; 0/52 factors significant post-BH-FDR |
| `regime_factor_selection/` | DEAD (clean null) | `regime_factor_selection/results/RESULTS.md:5-13`; 0/74 factors clear FDR |
| `regime_ew/` per-country HMM | DEAD (Gate 3) | `regime_ew/results/RESULTS.md:5-11`; 17/34 countries wrong sign |

The prior is therefore: **conditioning on macro state does NOT reorder the cross-section
of country returns.** This brief tests a narrower, mostly *descriptive* question and
reports its own null honestly.

## Question

1. Does the ASADO warehouse actually show the tone change the Fable 5.1 narrative claims
   happened after 2026-07-01? (verification, not prediction)
2. Conditional on months that historically resembled the current state on a small
   pre-stated vector, what distribution of forward outcomes followed — and is that
   distribution distinguishable from the unconditional one?

## State vector (6 dims) — FROZEN BEFORE ANY FORWARD RETURN WAS COMPUTED

All trailing / contemporaneous at month-end `t`. No forward-labelled variable is used.
The T2 forward family (`1MRet/3MRet/6MRet/9MRet/12MRet`, daily `NDRet`) is OUTCOME-ONLY
and is not read by the state builder at all.

| Dim | Name | Definition | Source |
|---|---|---|---|
| S1 | `OIL_3M` | log(Brent_t / Brent_{t-3}) | `wb_commodity_prices` CRUDE_BRENT (monthly avg) |
| S2 | `UST10_CHG3M` | US 10Y yield at t minus at t-3, in pct points | `t2_levels_daily` `10Yr Bond`, U.S. |
| S3 | `BREADTH_3M` | EW 3m return minus cap-weighted 3m return | `t2_levels_daily` `Tot Return Index`, `Mcap Weights` |
| S4 | `TECHLEAD_3M` | NASDAQ 3m return minus EW 3m return | same |
| S5 | `DISP_3M` | mean of last 3 monthly cross-sectional stdevs of country returns | same |
| S6 | `VOL` | cross-country mean of `20 Day Vol` at t | `t2_levels_daily` |

Standardization: expanding-window z-score using months <= t only (min 60 months of
history), so the state reading at any historical date uses no future information.

## Universe

EW/breadth/dispersion universe = 32 entities: the 34 T2 names minus `NASDAQ` and
`US SmallCap` (US style/size proxies, not countries). `ChinaA` and `ChinaH` are BOTH
kept as separate investable markets; `U.S.` appears once. Robustness re-run drops
`ChinaH`. `NASDAQ` is used only as the tech-concentration proxy in S4.

## Matching rules (both reported)

**A. Condition screen (primary, auditable).** A month t matches if it agrees with the
current state in SIGN on all four narrative axes S1..S4 and reaches at least half the
current magnitude on each.

**B. kNN (cross-check).** Euclidean distance in the 6-d expanding-z space; k = 24
nearest months. Excludes the trailing 12 months.

Contiguous matching months (gaps of <=1 month bridged) collapse into ONE episode.
Every reported statistic carries `n_months` AND `n_episodes`. Small n reported honestly
IS the answer, not a defect.

## Outcomes (forward, h in {1, 3, 6, 12} months)

EW universe return; breadth spread (EW-CW); tech lead (NASDAQ-EW); cross-sectional
momentum spread (top vs bottom quintile on trailing 12-1M); per-country return and rank;
and bloc returns (commodity exporters / EM-tech / EM-carry / DM Europe / Japan / India /
China).

## Significance test

Episode-median outcome vs the unconditional distribution via a bootstrap that draws
`n_episodes` random anchor dates 10,000 times. Report the empirical two-sided p-value.
With a hand-picked state vector and 4 outcome families x 4 horizons, NOTHING here is
multiple-testing-clean; p-values are reported as effect-size context, not as evidence of
a tradable edge.

## Stopping rule

The deliverable is a written brief plus tables and charts. If the conditional
distributions are indistinguishable from unconditional, that is the reported answer.
No search over alternative state vectors, thresholds, or k to find a result.
