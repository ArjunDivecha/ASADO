# Pre-registration — Boundaries of TSM, ASADO 34-country universe

**Written:** 2026-08-08, **before** any regression was executed.
**Frozen input:** `results/boundaries_panel.parquet`, md5 `ecf8d8149f30ed8868547464b25fae0d`
(12,779 rows × 74 cols, 34 countries). Built read-only from `Data/asado.duckdb` this session;
this hash is the snapshot of record for everything below.

---

## Part 1 — REPLICATION (this run). Data validation, not discovery.

**No holdout is used, and none is burned.** Reproducing a published table on the full sample
is validation of our data against a known answer. The holdout in Part 2 is reserved
exclusively for discovery and is untouched by this run. This distinction is recorded here so
it cannot be reinterpreted later.

### Dependent variable — MOP (2012) 25-strategy TSMOM index, per country
- Monthly market excess return `r_ex[t] = tri_usd[t]/tri_usd[t-1] − 1 − rf[t]`.
- Lookbacks L ∈ {1,3,6,9,12} × holding periods H ∈ {1,3,6,9,12} = 25 strategies.
- Strategy return, MOP form: `sign(cumulative r_ex over the L months ending t−1−j) × r_ex[t]`,
  averaged over the H open vintages j = 0…H−1. This sidesteps short-side financing asymmetry.
- TSMOM index = equal-weighted mean across all 25 strategies. **No volatility scaling**
  (the paper's specification).
- Forward 12-month TSMOM return = compounded index return over t+1 … t+12.

### Declared deviations from the paper
1. **Currency/risk-free.** The paper uses local-currency cash markets with a local risk-free
   rate. Our basis is USD (owner-confirmed, verified against the US-listed ETFs), so we use
   USD returns with the **US** short rate as `rf` for every country — consistent with the
   traded instruments. This changes what "excess return" means for the sign rule, hence it is
   declared rather than silent. `rf` is `short_rate` for `U.S.`, an annualized level, /1200.
2. **Sample.** Paper: US 1927–2024, 20 DM countries 1989–2024. Ours floors at 2000/2001.
3. **Valuation leg.** `Shiller PE` (a genuine CAPE analog) rather than dividend yield, which
   is the paper's acknowledged international weakness.

### Alignment rule (stated because this error class already bit once this session)
Row `t` under T2's first-of-next-month stamping carries data through end of month `M−1`.
Forward k-month return is `tri_usd[t+k]/tri_usd[t] − 1` — no extra gap, no contemporaneous
term on the right-hand side. The trailing regressor is `mom_12m_usd` at row `t`. To be
verified by hand on one country before the full panel runs.

### Specifications
- **A (TSMOM predictability, paper Table 4/5 analog):**
  `fwd12_tsmom[t] = a + b·Boundaries[t] + e`.  Paper's claim: **b < 0**.
- **B (reversal at boundaries, paper Table 6 analog):**
  `fwd12_mkt_excess[t] = a + b1·past12[t] + b2·Boundaries[t] + b3·(past12 × Boundaries)[t] + e`.
  Paper's claim: **b3 < 0** (momentum reverts at extremes), b1 > 0 once b3 is included.

### Standard errors
Month-clustered OLS as headline (contemporaneous cross-country correlation is the dominant
dependence in a 34-country panel of overlapping 12-month returns). Driscoll–Kraay (lag 12)
recorded as a noted upgrade; it needs `linearmodels`, which would have to go in a
per-experiment `uv venv` — never the project venv the nightly pipeline depends on.
**Newey–West 12-lag is NOT the headline**: the paper's own Hodrick (1992) and IVX tables show
NW-12 overstates significance, and the handoff flags the same.

### Both normalizations are run, and they are framed differently
- **Peer-relative — PRIMARY.** 23 countries from 2001-02, ~6,060 obs before the forward window.
- **Paper-exact (12m MA → [−1,1] vs trailing 10y min/max) — SIGN-AND-SHAPE CHECK ONLY.**
  18 countries from 2010-12, ~2,704 obs. **Attenuated t-statistics here are expected and
  pre-declared**: that is a statement about our warehouse's sample, not evidence against the
  paper. A **sign flip between the two constructions is a finding, not a bug**, and will be
  reported as one.

### Acceptance criteria (declared in advance)
- **REPLICATED** — b (Spec A) and b3 (Spec B) negative, |t| ≥ 2 month-clustered, in the
  primary (peer-relative) construction.
- **PARTIAL** — correct signs, |t| < 2; or replicates in one construction only.
- **FAILED** — wrong sign at |t| ≥ 2, in which case the paper's mechanism does not survive
  transfer to this universe/sample and the whole program's premise is in question.
- An `INSUFFICIENT` outcome is available and expected to be live for the paper-exact arm.

---

## Part 2 — DISCOVERY SHORTLIST (registered now; NOT run this session)

The power arithmetic forces this: ~15 years of overlapping 12-month returns is ~15
independent observations per country. Thirteen hypotheses against that is not a research
programme, it is a fishing licence. Four are registered, ranked, each with a kill criterion.

**Holdout, declared now and untouched:** the **last 5 years (2021-08 → 2026-07)** plus
**ChinaA, India, Brazil, Poland** held out entirely. No discovery test may look at either
until its in-sample verdict is recorded.

| # | Hypothesis (handoff idea) | Why it ranks here | Kill criterion |
|---|---|---|---|
| **D1** | **Boundary olympics on REER, credit_gap, CAPE** (#1) | The three with full coverage. `credit_gap` is only testable at all because of this session's quarterly-ffill fix; REER is the prior favourite; CAPE is the paper's own variable. | No state variable achieves \|t\| ≥ 2 on the past-return × extremeness interaction in-sample → the "extremes break trend" premise dies for this universe. |
| **D2** | **Time-series conditioning before cross-sectional** (#7-ish) | *Regime EW* is explicit that own-history **time-series** calibration is the one expression that worked here (gross Sharpe ~0.72) while cross-sectional ranking **lost money**. Test the expression with a track record first. | TS-conditioned momentum fails to beat unconditional momentum in-sample → drop conditioning entirely. |
| **D3** | **FX decomposition** (#8) | Now nearly free — the panel carries both bases. Directly tests whether "momentum breaks at extremes" is FX mean-reversion in costume. | Boundary effect is identical in USD and local → FX is not the channel; deprioritise REER as a boundary. |
| **D4** | **Peer-relative vs own-history horse-race** (#3) | Already half-answered on sample size (2.24×); the open question is whether peer-relative *also* predicts better, not merely more often. | Peer-relative underperforms own-history on identical countries/dates → revert to own-history and accept the shorter sample. |

**Explicitly deferred, with reasons:**
- **#13 (Boundaries vs HMMs)** and **#5 (cross-sectional momentum)** — behind the *Regime EW*
  prior ("regime timing is not alpha in this stack"; "regime taxonomies do not reorder the
  cross-section"; XS ranking of per-country posteriors loses money). Not dead — that entry's
  own open question notes HMMs are return-driven and blind to the levels Boundaries uses —
  but they carry a documented burden of proof and go last.
- **#11 (two-speed trap)** — behind the GDELT monthly-IC plateau.
- **#10 (boundary contagion)** — the handoff's own sequencing puts it last.
- **#4 (DIP moving anchor)** — needs a demographic fair-value model that does not exist.
