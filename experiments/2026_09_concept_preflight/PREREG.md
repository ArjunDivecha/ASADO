# Concept-layer pre-flight checks — pre-registration

*Written 2026-09-23 before any data for these checks was loaded or inspected. Committed to git
before the snapshot is taken; the commit timestamp is the registration record. Parent design:
`docs/concept_layer_2026_09_23/RESEARCH_DESIGN.md` §3.*

Two diagnostics decide whether the concept-layer program continues. Neither is a trading
signal, a hypothesis-ledger registration, or a harness trial. Both use frozen snapshots only.

---

## Check B — G2 orthogonalization gate, per relation type

**Source of the rule.** Research-Agenda-2026-07-v2 item G2 and
`docs/country_interaction_program/WP-11-baci-flagship.md` Step 2: "partner-weighted 1m returns
minus own + global + regional momentum (regress cross-sectionally per month), pooled IC t-stat
on the residual predictor, 2000→present, monthly. Pooled t ≥ 2 → proceed." WP-11 specifies the
trade relation; this check runs it separately for trade, banking and holdings.

Note: the agenda sequences G2 after G1 (the flip autopsy), which ended INCONCLUSIVE. G2 is run
here as a diagnostic at the owner's request (2026-09-23); a pass does not by itself authorize a
build.

**Data.** Daily backward-labelled country returns (the `loopdb.daily_country_returns`
definition: `t2_factors_daily.1DRet` shifted one calendar row, exact zeros dropped), compounded
within calendar months per country. Edge weights from `graph_edge_vintages` (loop DB), using for
month m the latest vintage with `applies_from` ≤ the last calendar day of m, diagonal removed,
weights re-normalised over neighbours with a return that month (same rule as
`build_graph_features.weighted_neighbor`).

**Signal at month m for country i and relation r ∈ {trade, bank, holder}:**
PW_r(i,m) = weighted mean of neighbours' month-m returns.

**Orthogonalization.** For each month, cross-sectional OLS of PW_r on an intercept (absorbs the
global component), own month-m return, own 12-1 momentum (compounded months m−11..m−1), and the
equal-weight month-m return of i's region excluding i and excluding i's own-sovereign sleeves
(ChinaA/ChinaH; U.S./NASDAQ/US SmallCap). Region map: `config/ff_region_map.json`
`country_to_region` (the repo's canonical map). Months with fewer than 15 complete countries are
skipped. The residual is the predictor.

**Target.** Primary (P): country i's month m+1 return. Skip-day variant (S): month m+1 return
excluding i's first trading day of m+1 (guards against the asynchronous-close artefact, where a
late-closing partner's last-day move is mechanically followed by an early-closing market's next
open).

**Statistic.** Monthly Spearman IC between residual and target across countries; pooled
t = mean IC / (sd / √months). Newey-West (3 lags) t reported alongside. Sample: first month with
edges for that relation through the last complete month in the snapshot.

**Pass rule (G2, per spec).** Relation r passes G2 if the primary pooled t ≥ 2.0 (positive:
continuation). Holm-adjusted results across the three relations are reported as a secondary
reading.

**Additional rule for proceeding to the relational experiment.** Relation r qualifies only if it
passes G2 *and* the skip-day variant has the same sign with t ≥ 2.0. A G2 pass that fails the
skip-day variant is recorded as an asynchronous-close timing effect, not transmission.

**Placebo.** For each relation, 200 random neighbour relabelings per vintage (permute each
focal row's weights across its non-self neighbours), same pipeline; report the percentile of the
real t in the null. Reported, not a gate.

**Descriptive only (no gate):** IC by era 2000–13 / 2014–23 / 2024–26, yearly IC, and whether any
relation shows significant convergence (t ≤ −2).

**Outcome.** If no relation passes G2, the diffusion/interaction territory downgrades per WP-11,
and the relational experiment in the design is cancelled.

---

## Check A — does the country panel hold more than one or two concepts?

**Data.** `t2_master` `_CS` variables (cross-sectional z-scores), monthly, with the five forward
returns (`1MRet`…`12MRet`) excluded. Variables with near-zero cross-sectional variance (broadcast
series) are dropped. Keep variables with ≥ 90% coverage of country-months from 2005-01 on; use
complete cases on the kept set. Counts of kept variables and rows are reported. Known caveat: the
T2 cleaning step has a small look-ahead (0.8% of cells, `docs/T2_CAUSAL_CLEANING_2026-08-21.md`);
acceptable for a rank diagnostic, not for training.

**A1 — number of concepts (variable-mode rank).** Eigenvalues of the pooled correlation matrix of
kept variables. Null: Horn's parallel analysis — 200 reps in which, within each month, each
variable is independently permuted across countries. k_var = number of leading eigenvalues that
exceed the null's 95th percentile at the same rank, counted until the first failure. Computed on
the full sample and on expanding cutoffs (2010-12, 2015-12, 2020-12). Secondary: the
Wang-Liu-Chen matrix-factor eigenvalue-ratio estimates for the country mode and variable mode.

**A2 — does the return signal live in the strong directions? (source-condition slope,
`docs/SPECTRAL_DIAGNOSTICS.md` §1).** Pooled X (country-months × kept variables, standardised),
target y = 12-month forward return relative to the cross-sectional mean (primary), 1-month
(secondary), both built from compounded daily returns. H = XᵀX/n = Σ λᵢvᵢvᵢᵀ; bᵢ = vᵢᵀXᵀy/n;
cᵢ = bᵢ/λᵢ; s′ = OLS slope of log|cᵢ| on log λᵢ. A pure-noise target gives s′ ≈ −0.5 in
expectation, so the decision uses an empirical null: 200 reps with y permuted across countries
within each month.

**Decision rules.**
- k_var ≤ 2 on the full sample → the learnable vocabulary is too small; the node-level concept
  experiment reduces to the IPCA listwise ablation only.
- s′ (12-month target) not above the null's 95th percentile → the return-relevant signal is not
  concentrated in well-conditioned directions; the node-level concept experiment is dropped.
- Otherwise the node experiment proceeds, with the number of concepts capped at k_var.

**Deliberately not done here:** no walk-forward comparison of ridge, PCA or PLS forecasts. That
would spend the node experiment's out-of-sample evidence before the experiment is registered.

---

## Outputs

`experiments/2026_09_concept_preflight/results/` — `check_b_g2.json`, `check_b_yearly_ic.xlsx`,
`check_a_spectral.json`, charts as PDF, `RESULTS.md`. Frozen inputs under
`Data/work/experiments/concept_preflight/snapshot_2026_09_23/`. No production table, ledger, or
config is written.

---

## Amendment A1 — 2026-09-23, before any return or IC was computed

Found while reading the snapshot schema (no returns or statistics had been computed):

1. **Edges exist only for the 31 sovereign tokens.** `graph_edge_vintages` has no rows for
   NASDAQ, US SmallCap or ChinaH, matching `build_graph_features_pit.py` (sleeves get no graph
   features). Check B therefore covers the 31 sovereigns as focal countries and as neighbours.
2. **Singleton regions.** Under `ff_region_map.json`, U.S. (region `US`), Canada
   (`North_America`) and Japan (`Japan`) have no other member once the focal country and its
   own sleeves are excluded, so they would drop out of every regression. Fix, using the map's
   own region definitions: U.S. and Canada form one region (the map describes `North_America` as
   "US + Canada"); Japan joins `Asia_Pacific_ex_Japan` (Developed Asia-Pacific). Regional means
   use sovereign tokens only (NASDAQ, US SmallCap, ChinaH excluded) so no market is counted
   twice, and always exclude the focal country.
3. **Monthly return validity.** A country-month return is computed only if the country has at
   least 10 non-zero daily returns in that calendar month; otherwise it is missing. 12-1
   momentum requires all 11 months present.
4. **Months used.** Only complete calendar months. Snapshot data run into September 2026, so the
   last signal month is July 2026 (target August 2026).

---

## Check A3 — replacement for A2 (registered 2026-09-23, after A2 was found underpowered)

**Why this exists.** A2's source-slope test detected a planted realistic signal only 12–16% of
the time (`RESULTS.md`, power check). By owner decision (2026-09-23) A2 is recorded as
**inconclusive for lack of power**, not as a drop. A3 is a new test, registered here before it
is run. Its result is final for the node-level concept question: there is no A4.

**Question.** Do the panel's 9 concepts (A1's k_var) explain next-year country returns better
than chance, once country identity is removed?

**Data.** Identical to Check A: the same 36 `_CS` variables, 2005-01 on, 7,031 complete
country-months; same 12-month forward relative return built from compounded daily returns.

**Concepts.** The top 9 principal components of the pooled, standardised feature matrix (fitted
on features only; no return enters).

**Removing identity (primary).** Both the 9 concept scores and the target are two-way demeaned
(month means and country means removed). This asks whether a country's *changing* concept
exposures line up with its relative returns, and shuts off the "persistent winner looks like a
persistent feature" channel that inflated the MacroState result.

**Statistic.** R² from pooled OLS of the demeaned target on the 9 demeaned concept scores.

**Null.** 1,000 country-block permutations: each country's entire target history is reassigned to
another country, then the same demeaning and regression are applied. This preserves each
series' own persistence and the overlap of 12-month targets, which a row-wise shuffle would not.

**Decision rule.** Real R² above the null's 95th percentile → the node-level concept experiment
proceeds, with at most 9 concepts. Otherwise → the node-level concept experiment is dropped, and
that is final.

**Reported, not gating:** the same test with month-demeaning only (identity channel left open),
the 1-month target, and each concept's individual contribution.

**Power, established before the real target is touched.** Synthetic targets built from the real
features plus synthetic noise (no real returns): signal = a random combination of the top-3
demeaned concept scores; noise = 12-month rolling sums of iid monthly draws per country (so it
has the same overlap structure); pooled correlation between target and signal set to 0.05, 0.10
and 0.20; 200 draws each through the full pipeline (with a 200-permutation null per draw).
The detection rates are committed before the real test runs. If power at 0.10 is below 50%, A3
is reported as underpowered alongside its result.
