# Learned economic concepts on the ASADO database — research design

*2026-09-23. Written in response to the Tensor Logic / predicate-invention discussion (Domingos,
"Tensor Logic: The Language of AI", arXiv:2510.12269). Research only: no code, no DB writes, no
ledger registrations were made. Evidence came from five read-only sweeps of the repo, both
DuckDB databases (queried as scratch copies, never the live files), the Neo4j graph, the
graveyard and ledgers, Investment Learnings, Quantpedia, and the outside literature.*

---

**Status 2026-09-23 (after the pre-flight checks,
`experiments/2026_09_concept_preflight/RESULTS.md`):** Experiment 2 (relational) is **cancelled**
— G2 failed for trade, banking and holdings, and the neighbour-gap signal's historical strength
turned out to be own-country one-month reversal. Experiment 1 (node-level concepts) **proceeds**:
with U.S. markets removed and country identity stripped out, nine feature concepts explain 11.8%
of next-year relative-return variation against a 3.1% chance ceiling. The sections below are
the original design and have not been rewritten.

## The short answer

The database can support this idea, but not as a new, free-standing program, and not in the
form the Tensor Logic framing suggests. Three things decide that.

First, **the country-level half of the idea has already been run twice on this panel, and the
most useful version of it already exists on a branch.** The Macro State Model was fitted on
6 September: hand-built economic states beat equal weight by about three points a year, but a
control that saw only *which data were missing* — no macro values at all — got most of the
way there (12.14% vs 11.57% a year), because data availability acts as a country label and the
model sat in the three US sleeves plus Denmark in every one of 97 months. Separately, the
Kelly-Pruitt-Su IPCA branch is, mathematically, a supervised Tucker-style concept layer:
36 characteristics are mapped through a learned matrix into 36 latent factors that are then
priced. With a ridge loss it ranked countries backwards (rank IC −0.017); with a listwise
ranking loss it roughly doubled active Sharpe over the additive predictor (0.107 to 0.202).
That branch was never merged, and its constrained-ablation run is "built, pending backtest."
Predicate invention on the node side is therefore best tested as **a constrained, small-rank
version of that IPCA-listwise model**, entered into the MacroState model contest — not as a
fork.

Second, **the database's genuinely distinctive asset for this idea is relational, not
country-level.** `graph_edge_vintages` in the loop DB is a dated, point-in-time tensor of
source country × recipient country × relation type (trade, banking, portfolio holdings), back
to 1998–2000, audited as the only legal source for adjacency matrices. That is exactly the
shape a RESCAL/TuckER relational factorization wants, and the only family that has ever
survived in ASADO — delayed propagation through neighbours — lives on it. Nobody has tried
learning *relation-specific* transmission ("a banking link transmits stress to recipients with
fragile funding; a trade link transmits growth to recipients with high export exposure").
That is the version of this idea most likely to be new.

Third, **the literature does not give a learned latent layer a head start at this sample
size.** Every demonstrated win for autoencoders or high-complexity models (Gu-Kelly-Xiu; Kelly-
Malamud-Zhou) is on panels orders of magnitude bigger than 34 countries × 300 months, and
Nagel (2025) showed one celebrated "complexity" win collapses algebraically to disguised
momentum. The Domingos claim itself is a one-paragraph aside in a manifesto, with no
experiment behind it. So the design has to be cheap to kill.

**My recommendation:** run two pre-flight checks that cost a day each, then one node-level
experiment and one relational experiment, in that order, each with its kill criteria written
before any result is seen. Details follow.

---

## 1. What the database actually offers, ranked for this purpose

### Node side: month × country × variable

The best tensor is the **T2 monthly core** (`t2_master`, `_CS`/`_TS`, 2000-02 onward, all 34
markets, fully dense, 106 non-return variables). Two corrections are required before training
on it. The five forward-return columns (`1MRet`…`12MRet`) sit in the same table and must be
stripped. And `build_t2_master.py::_clean_sheet` winsorizes on full-sample median/MAD and
replaces local outliers using the next 20 months — a real, if small, look-ahead touching 0.8%
of cells (`docs/T2_CAUSAL_CLEANING_2026-08-21.md`). The measured fix (drop the winsorizer,
keep a causal spike guard, 0.24% of cells touched) awaits your decision for production; an
experiment can apply it to its own copy of `t2_raw` without touching the feed.

The second layer is the **loop DB daily market block** — sovereign 2Y/10Y and CDS, FX implied
vol / risk reversal / carry, ETF flows, ECFC consensus — sampled monthly. It is genuinely
point-in-time (market prices; consensus is Bloomberg's stored revision history, re-polled
daily), but thinner: about 29 of 34 countries from 2006–2010, with CDS on only 19–20.

The macro panels (`external_`, `extended_`, `imf_`, `macrostructure_factors`) should be kept
out of the first build: per-variable coverage runs from 11 to 33 of the 34 markets, and none
carries release-lag or vintage metadata (leakage audit L-03). GDELT is dense but starts 2015.

### The vintage axis — underused and point-in-time by construction

Three tables carry a real "what was known when" dimension: `consensus_revisions` (44k rows,
34 countries, 2007-10 on, same-target-year revisions), `weo_vintages` (36 IMF vintages,
2008-04 on, with `vintage_date` and `target_year`), and `release_events_daily` (48k release-
dated events, 1996-11 to 2026-07, with separate `release_date` and `reference_period`).
Together they allow an **expectations tensor** — country × macro concept × target horizon ×
vintage — from which "growth surprising relative to what was expected at the time" can be
built with no revision leakage at all. Caution: consensus-revision momentum is already dead as
a first-order signal. Its only legitimate role here is as an *ingredient* of a concept that
earns its place in an interaction, never as a standalone predictor. `release_events_daily`
stops at 2026-07-10, so a live version needs that feed restored.

### Relational side: source × recipient × relation × vintage

| Relation (`graph_edge_vintages`) | Country pairs | Vintages | Cadence |
|---|---:|---:|---|
| Trade | 900 | 27 (2000-04 on) | ~annual |
| Banking | 627 | 109 (1999-07 on) | ~quarterly |
| Portfolio holdings | 864 | 25 (1998-09 on) | ~annual |

Each vintage carries `applies_from`, so the graph as known at any decision date can be
reconstructed. `bilateral_portfolio_matrix` (imf_pip) adds instrument-type detail to the
holdings slice. The Neo4j graph holds only the *current* weight per edge and must not be a
training source. `leadlag_edges` and `similarity_twins` are denser (85–94% of pairs) but are
outputs of earlier research loops; they need a lineage manifest (audit L-09) before feeding a
model. The retired v1 surfaces (`graph_edge_snapshots`, `graph_features_daily`) project
today's weights over all history and are look-ahead.

### Returns and the factor-return panel

Country returns come from the T2 total-return surfaces, trading days filtered through
`daily_calendar`, which lags by one day. `factor_returns` (390 factors in the monthly table)
is optimizer output and is barred from every *input* surface. The IPCA branch used factor
returns as its *training target* for the concept loadings, which is the correct direction of
use — but it deserves an explicit ruling from you before a new experiment relies on it.

---

## 2. What the record rules out

Each of these is settled and cited; a proposal that resembles one of them needs to say how it
differs.

- **Flattened whole-panel compression.** PCA over the ~2,900-dimensional country × feature
  vector (the WorldState analogs) anchored to the 2007–13 era and delivered IC ≈ 0; the same
  "history as predictor" mechanism has died five times (`docs/strategy/lessons.md`). A Tucker
  decomposition of the full panel, fit for reconstruction, is this experiment again.
- **Unsupervised concepts judged by variance explained.** Same root cause; the objective must
  be the forward cross-section.
- **Hard partitions.** Depth-2 trees on a 15-input state produced zero admissible forecasts in
  all 25 fits of the September nonlinear study, even on synthetic linear labels — smooth
  state features cut time into episodes too thin to support a leaf. Thresholding learned
  factors into Boolean "predicates" (the literal Domingos move) would hit the same wall.
  Concepts must stay continuous.
- **L2 loss on the cross-section.** The IPCA ridge variant was anti-monotonic because rare
  outlier months dominate; ranking loss fixed it.
- **Residualizing out the common component.** The residual-forecasting study found the
  signal *is* the common component.
- **Learned graph topology.** Standalone GNNs at N=34 are a settled skip
  (`ox-graph-deep-dive.md`, item #35); transmission models must condition on the existing PIT
  graph.
- **Combiners of known survivors** report an in-sample selection ceiling, not alpha.
- **Fixed linear concept maps** add no information, only reshape the ridge penalty
  (`docs/macrostate_2026_09_05/RESEARCH_PLAN.md` §1). A learned concept layer has to earn its
  keep against a matched flat model with identical inputs, and against the missingness-only
  control.

---

## 3. Two pre-flight checks, before any model is built

**Check A — is there more than one concept to invent?** Run the spectral diagnostic already
specified in `docs/SPECTRAL_DIAGNOSTICS.md` (never run against the current panel), mode by
mode: the effective rank of the country mode and of the variable mode of the cleaned node
tensor, each against its Marchenko-Pastur noise floor, on expanding windows. Add the matrix
factor model of Wang, Liu & Chen (2019), which was applied to almost exactly this shape (14
OECD countries × 10 indicators) and gives separate row and column loadings. If the variable
mode has only one or two eigenvalues above noise, "a small learned vocabulary" is a vocabulary
of one or two words, and the node experiment should shrink accordingly. *Also* compute the
supervised version: how much of the forward cross-section is explained by the top k scaled-PCA
or PLS directions. The gap between the unsupervised and supervised spectra tells you whether
the return-relevant structure is in the dominant variance at all.

**Check B — does network transmission survive the momentum control?** The Country-Interaction
plan's G2 gate (`docs/COUNTRY_INTERACTION_PLAN_2026-08-24.md`, WP-11) has never been run:
partner-weighted returns, orthogonalized against own, global and regional momentum, must show
pooled t ≥ 2, or the whole diffusion territory is cancelled. The relational experiment below
lives in that territory, so G2 is its entry ticket. Run it per relation type (trade, banking,
holdings) rather than pooled, because a relation-specific result is exactly what the
relational layer would exploit.

Both checks write only to an experiment directory and use `snapshot_for_experiment.py` inputs.

---

## 4. Experiment 1 — a constrained concept layer on the node tensor

**The model.** Resume the IPCA-listwise branch and constrain it. Characteristics z(i,t) for
country i at month t (L ≈ 40–60, cleaned T2 core plus the monthly-sampled market block) map
to F concept scores c(i,t) = Γᵀ z(i,t); the forecast is a linear function of c. Two changes turn
IPCA into something that deserves the word "concept":

1. **Small F with a block structure** (the constrained-factor idea of Chen, Tsay & Chen,
   2020). Six concepts are each allowed to load only on one economic block — valuation,
   growth expectations and surprise, policy and curve, sovereign and FX stress, flows and
   positioning, price trend. Two further concepts are unconstrained. The unconstrained pair is
   where "discovery" can happen; the constrained six keep the layer from becoming an opaque
   mixture.
2. **Sparsity within each concept** (a group-lasso or L1 penalty on Γ), so a concept depends
   materially on a handful of inputs and can be written down.

Loss: listwise cross-entropy with tempered labels, as in the branch that worked. Target:
12-month USD return relative to the eligible equal-weight universe, with monthly and 12-month
staggered portfolio expressions evaluated by the existing MacroState evaluator
(`experiments/2026_09_macrostate/evaluator.py`). Training rows are only those whose 12-month
label has matured (`prepare.py::mature_training_rows`); refit each July on expanding history,
as MacroState did, so the two are directly comparable.

**Shutting the identity channel.** This is the lesson that matters most from MacroState.
Train on a sub-panel where the chosen inputs are complete, rather than imputing and flagging;
weight dates and macro identities equally, splitting the weight among the US and China sleeves;
and include two mandatory controls: the missingness-flags-only model, and a
country-fixed-effect-only model (each market's trailing average relative return). A concept
layer that cannot beat both has learned identity, not economics.

**The contest.** Same folds, same dates, same eligible markets:

- ridge on raw characteristics (the flat baseline)
- PLS and scaled PCA with F components (Kelly-Pruitt; Huang et al.) — the supervised
  dimension-reduction baselines the literature says to beat
- unconstrained IPCA-listwise (the branch as it stands)
- constrained IPCA-listwise (the proposal)
- the MacroState states-plus-interactions leader and the missingness control

Hyperparameters (F, sparsity, label temperature) come from a stated small grid, selected on
inner time folds only, with the search count reported beside every result.

**What would count.** Pre-register before running. My suggested reading: the constrained model
must at least match the unconstrained one on out-of-sample rank IC and gross active return
(constraint cost ≈ 0), and beat PLS, the missingness control and the fixed-effect control on
both portfolio expressions. Contributions must not be concentrated in the US sleeves. Separately,
at least three concepts must be **stable** across refits — after Procrustes alignment, since
latent factors can rotate or flip sign without changing predictions — and each must be
approximable by a rule of five or fewer inputs that retains most of its out-of-sample
contribution. Each surviving concept gets a card (definition, top and bottom examples,
stability, incremental contribution) and keeps an anonymous name until the card is filled.

**What it would mean.** If the constrained model matches the unconstrained one and its
concepts are stable, you have an interpretable replacement for the additive predictor and a
vocabulary the relational model can use. If it predicts but the concepts are unstable, it is
ordinary representation learning, and the predicate-invention claim is unproven. If it fails
both controls, the node-level concept idea is done on this panel.

**Governance.** This is a directory experiment registered in `ledgers/methodology_ledger.jsonl`
as an alternative estimator inside the MacroState contest, rather than a new family. Whether the
MacroState "results-first, no significance gate" contract extends to it is your call; the
contract is explicitly scoped to MacroState's evaluator task (`experiments/2026_09_macrostate/
contract.json`). New packages (PyTorch with MPS, TensorLy) go in a per-experiment `uv venv`; the
project venv has neither, and there is no existing factor-model code to reuse.

---

## 5. Experiment 2 — relation-specific transmission on the graph tensor

**Entry condition:** G2 passes for at least one relation type.

**The model.** A RESCAL/TuckER-style bilinear transmission layer on the *fixed* PIT graph:

  forecast(i, t) = Σ over relations r, Σ over neighbours j of  A_r(i, j, t) · s(j, t)ᵀ W_r e(i, t)

where A_r is the trade, banking or holdings adjacency as known at t (from `graph_edge_vintages`,
publication-lagged), s(j, t) is a short source-condition vector for neighbour j (its recent
return innovation plus two or three node concepts from Experiment 1, or hand-built ones if
Experiment 1 fails), e(i, t) is a recipient-exposure vector, and W_r is a small matrix per
relation. With three-dimensional s and e, that is 27 transmission parameters in total — small
enough for this sample. Topology is never learned; only how each relation type transmits which
condition to which kind of recipient.

**Horizons.** The flip autopsy's leading explanation is absorption-speed compression: the
63-day diffusion died first, while the one-day signal stayed positive. So this is a daily
model scored at 1, 5 and 21 trading days, with the monthly version a secondary check.

**The comparisons.** The existing `GRAPHP_*` neighbour-gap features, through a ridge with the
same inputs (this is the incumbent); the bilinear model with W_r forced equal across relations
(tests whether relation type matters); the model on degree-preserving shuffled graphs, twenty
seeds (tests whether the graph matters); and the model with e(i, t) held constant (tests
whether recipient conditioning matters). Any gain must survive all four.

**The 2024–26 flip.** Those years have already motivated the hypothesis, so they are not a
test of it. The pre-registered question is whether the model fit through 2023 predicts the
*direction* of the flip — does it assign lower transmission in 2024–26 because recipient
exposures or source conditions changed, not because it saw the returns? Genuine confirmation
has to come from data arriving after registration. WP-06's warning applies here: exposure
density and spillover density move in opposite directions in crises, so a single
"connectedness" concept would mislead; relation-specific W_r is designed to avoid exactly that.

**Governance.** This mechanism is "neighbour moves, endpoint reprices" and is charged to the
`network_spillover` family whatever the representation (WP-08), which already carries 23
trials. It is also the Country-Interaction plan's Phase 3 flagship (#15–16), so it should run
as that work package, not as a separate program.

---

## 6. Order of work and what each step costs

1. Check A (spectral + matrix factor model) and Check B (G2 by relation). Roughly one day
   each. Either can end a branch of the program.
2. Recover the IPCA branch and run its pending linear listwise ablation. It is already built,
   and tells you whether the listwise gain is from the loss function or the latent structure.
   The branch lives outside ASADO: worktree
   `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy IPCA/` (git
   branch `IPCA`, pushed, not for merge), reading `Normalized_T2_Master.xlsx` from the sibling
   `T2 Factor Timing Fuzzy/` worktree. That workbook comes from the same cleaning step with the
   0.8% look-ahead, so the branch's 0.107 → 0.202 Sharpe result should be re-checked on causally
   cleaned inputs before Experiment 1 treats it as the incumbent.
3. Experiment 1, with the contest and controls above.
4. Experiment 2, if G2 passed.

Nothing here requires new data collection, a new language, or Tensor Logic itself; einsum in
PyTorch is enough to express every model above.

---

## 7. Honest prior

On the node side, I would put perhaps one chance in four on a constrained concept layer beating
PLS *and* both identity controls on both portfolio expressions, and lower on it also producing
stable, nameable concepts. The prior is low because MacroState's hand-built states were largely
explained by missingness, and five unsupervised compressions have died. It is not lower because
the IPCA-listwise result is real and the constraint is cheap.

On the relational side, the prior for clearing G2 is uncertain, since it has never been run. If
G2 passes, relation-specific transmission is the most promising part of this program: it
extends the only mechanism that has survived here, uses the one asset in the database that is
both point-in-time and genuinely relational, and has not been tried.

---

## 8. Corrections to the record found along the way

- `docs/ASTRA_BRIEF_regime_model_2026_09_13.md` says 57 hypotheses sit at WEAK. The live
  `ledgers/hypothesis_ledger.jsonl` has 63 hypotheses: 26 DEAD, 16 INSUFFICIENT_COVERAGE,
  11 WEAK, 10 WATCH. Seven moved from WEAK to WATCH at the 2026-07-13 cost retraction.
- `experiments/2026_09_macrostate/RESULTS.md` still reads "MacroState itself has not yet been
  fitted"; `MODEL_RESULTS.md` in the same directory and the methodology ledger
  (M_20260906_001–003, all WATCH) show it was fitted on 2026-09-06. A reader of RESULTS.md alone
  gets the wrong picture.
- The graveyard skill's cached tallies (21 WEAK / 1 WATCH) predate the cost retraction.

---

## Sources

Repo (all under `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/` unless noted):
`experiments/2026_09_macrostate/MODEL_RESULTS.md`, `…/RESULTS.md`, `…/evaluator.py`,
`…/prepare.py`, `…/contract.json`; `ledgers/methodology_ledger.jsonl` (lines 8–10);
`ledgers/hypothesis_ledger.jsonl`; `docs/macrostate_2026_09_05/RESEARCH_PLAN.md`,
`PRIOR_RESEARCH.md`; `docs/T2_CAUSAL_CLEANING_2026-08-21.md`; `ASADO_LEAKAGE_AUDIT.md`
(L-01 to L-13); `docs/DB_INVENTORY_2026_09_13.md`; `docs/SPECTRAL_DIAGNOSTICS.md`;
`docs/COUNTRY_INTERACTION_PLAN_2026-08-24.md`; `docs/country_interaction_program/`
(WP-04, WP-06, WP-08, WP-11); `docs/strategy/lessons.md`; `ox-graph-deep-dive.md`;
`experiments/2026_07_flip_autopsy/RESULTS.md`; `experiments/2026_08_network_spillover_capture/RESULTS.md`;
`docs/ASADO_Nonlinear_Study_Agent_Pack/ASADO_Nonlinear_Study_PRD.md`;
`../ASADO-exp-Nonlinear/experiments/2026_09_nonlinear_country_returns/RESULTS.md` and `src/`
(label_store, runner, estimators, pseudolabels, p10_portfolio);
`../ASADO-Astra-Simple/scripts/nonlinear_country_study/`.
Investment Learnings: `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/Investment Learnings/`
`T2 Factor Timing Fuzzy IPCA.md`, `T2 Factor Timing Fuzzy ElasticNet PIT Audit.md`,
`T2 Factor Timing Fuzzy Residual Forecasting.md`, `INDEX.md`.

Literature (URLs verified by the research agent unless marked):
Domingos 2025, https://arxiv.org/abs/2510.12269 ·
Kok & Domingos 2007, https://homes.cs.washington.edu/~pedrod/papers/mlc07.pdf ·
Kelly, Pruitt & Su 2019 (IPCA), https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2983919 ·
Gu, Kelly & Xiu 2021, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3335536 ·
Kelly & Pruitt 2013 (PLS), https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12060 ·
Kelly & Pruitt 2015 (3PRF), J. Econometrics 186(2) ·
Huang et al. 2022 (scaled PCA), https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3358911 ·
Wang, Liu & Chen 2019 (matrix factor model), J. Econometrics 208(1) ·
Chen, Tsay & Chen 2020 (constrained matrix factors), https://statweb.rutgers.edu/rongchen/publications/20JASA_Constrained_Matrix.pdf ·
Chen, Yang & Zhang 2022 (tensor factor models), JASA 117(537) ·
Nickel et al. 2011 (RESCAL, verified via slides only) ·
Balažević et al. 2019 (TuckER), https://aclanthology.org/D19-1522/ ·
Cohen & Frazzini 2008 · Rapach, Strauss & Zhou 2013, https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12041 ·
Pu et al. 2023 (network momentum), https://arxiv.org/abs/2308.11294 ·
Cakici, Fieberg, Metko & Zaremba 2024, Review of Finance 28(1) ·
Locatello et al. 2019, https://proceedings.mlr.press/v97/locatello19a.html ·
Kelly, Malamud & Zhou 2024, https://www.nber.org/papers/w30217 ·
Nagel 2025, https://www.nber.org/papers/w34104.
Not independently verified: Rizova's trade-momentum effect size (paywalled).
