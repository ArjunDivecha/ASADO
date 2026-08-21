# ox-graph-research.md — Making the Neo4j country graph a signal source

| Field | Value |
|---|---|
| **Date** | 2026-08-21 |
| **Author** | Session "ox-alpha" (Claude Code), at Arjun's request |
| **What this is** | 14 ideas for making ASADO's country-relationship graph useful as a research signal source rather than a lookup surface, grounded in an adversarially-verified deep-research run over the network-methods / GNN / financial-knowledge-graph literature, mapped against the graph's actual live state. Ideas only — nothing implemented. Companions: [ox.md](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/ox.md) (loop ideas), [ox-data-architecture.md](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/ox-data-architecture.md) (warehouse dive), same day. |
| **Research run** | Deep-research workflow, 62 agents: 13 primary sources fetched (BIS, ECB, Journal of Finance, Journal of Econometrics, CRAN), 25 claim groups through a 3-model-family adversarial panel → **12 confirmed / 3 refuted / 10 unverified**; entailment audit clean (8 checked, 0 flagged). Full report: [report.md](file:///Users/arjundivecha/.claude/skills/deep-research/runs/20260821_014552_how-are-graph-databases-and-network-methods/report.md) |
| **Status** | Proposal document. Every idea lands through the harness front door as a registered family. **[CONFIRMED]** / **[UNVERIFIED]** tags reflect the research run's verdicts — the loop's discipline should treat them differently. |

**Repo root for every path below:** `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/` — scripts under `scripts/loop/` ([build_graph_features_pit.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/loop/build_graph_features_pit.py), [collect_pit_edges.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/loop/collect_pit_edges.py), [build_similarity_features.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/loop/build_similarity_features.py), [build_leadlag_features.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/loop/build_leadlag_features.py), [build_dislocations.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/loop/build_dislocations.py)), [scripts/setup_neo4j.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/setup_neo4j.py), [Data/loop/asado_loop.duckdb](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/loop/asado_loop.duckdb) (`graph_edge_vintages`).

---

## Starting point (from the 2026-08-21 architecture dive)

The graph holds 810 nodes / 21,473 edges: `HAS_FACTOR_EXPOSURE` 13,759 (64% — a materialized latest-value cache), `HOLDS_PORTFOLIO` 3,149, `TRADES_WITH` 1,540, `DATA_AVAILABLE_FROM` 1,244, `HAS_BANKING_EXPOSURE_TO` 933, `HAS_CRISIS_HISTORY` 378, `LEADS` 210, `SIMILAR_TO` 170, `HAS_CENTRAL_BANK` 31, `SUBJECT_TO` 31 (broken — arbitrary program assignment), `EXPORT_EXPOSED_TO` 28 (hardcoded dict). Every analytical consumer uses the graph as three 34×34 weight matrices that exist as upstream parquet; the PIT truth lives in `graph_edge_vintages` (trade: 27 annual vintages 1999-2025, +4mo lag; bank: 109 quarterly, +4mo; holder: 25 annual 1997-2024, +9mo). Existing features: neighbor return gaps (21d/63d), two-hop gap, holder stress, neighbor drawdown count, Katz (α=0.5, 3 hops), PageRank hub amplification, spectral blocs (k=4) — all static per-vintage, all direction-blind. Family verdicts: survived the PIT re-test (twohop t=4.4, Katz t=4.25, bank gap IC 0.034/t=4.5), parked, and RE-ARMED 2026-08-20.

**The research's four mechanisms for turning a country graph into a signal source — ASADO exploits ~1.5 of 4:** (1) market-estimated spillover networks, (2) temporal rather than time-aggregated centrality, (3) ownership-overlap edges as a predictive layer, (4) network-propagation-modified risk metrics. ASADO does static per-vintage exposure propagation and nothing else.

## A. New edge families (edges ASADO doesn't have)

**1. Common-holder overlap edges — the Anton & Polk port. [CONFIRMED — strongest direct precedent]**
Anton & Polk (Journal of Finance 2014, "Connected Stocks"): edge (i,j) = raw count of common holders per quarter, cross-sectionally rank-normalized to unit SD. Forecasts cross-sectional return correlation controlling for factor exposures and pair characteristics (FCAP t=13.43); the "connected return" (return of commonly-held peers) as a confirming signal for short-term reversal earned 32–57bp/month five-factor alpha (t=2.95 / t=2.60), up to ~7%/yr. ASADO's `HOLDS_PORTFOLIO` vintages make common-holder counts per country-pair a ~1-day build. Two registered hypotheses: (a) overlap-edge z as a comovement predictor; (b) connected-return as a *confirming* signal on existing entries — convergence pressure, a different mechanism than the propagation-lag features already built. Caveats: US equities 1983-2008, gross, in-sample; country-level transfer is the open question the harness exists to answer. (Sources: JF 69(3) 2014; LSE Research Online full text.)

**2. A market-estimated spillover network (Diebold-Yilmaz connectedness). [CONFIRMED method + tooling]**
A fourth edge family beyond the three fundamental ones: a directed, time-varying spillover graph estimated from returns via VAR/QVAR forecast-error variance decompositions — readable directly as a graph (from-/to-degree = sender/receiver centrality). Demonstrated at daily frequency as a crisis monitor (US firm-volatility connectedness ~56% → ~89% around Lehman). Production tooling verified: the `ConnectednessApproach` R package v1.0.4 — 8 model classes (VAR, QVAR, LAD, LASSO, Ridge, Elastic, TVP-VAR, DCC-GARCH) × 5 frameworks (Time, Frequency, Joint, Extended Joint, R2) in one call. ASADO's daily returns (2005→) feed a rolling QVAR estimate → new `SPILLS_INTO`/`SPILLS_FROM` edges. The `leadlag` builder is a primitive lag-1-correlation cousin; DY is the principled, directed upgrade. Caveat (IMF WP 17/107): generalized-FEVD rows don't sum to one and edge weights/centrality rankings are normalization-, horizon-, and window-sensitive — pre-register those choices. The descriptive crisis demonstration does not by itself establish predictive value.

**3. Frequency-split edges (Barunik-Krehlik 2018). [CONFIRMED tooling]**
The same package's frequency module (default partition c(pi, pi/2, 0)) decomposes each spillover edge into short-run (contagion-like) vs long-run (structural) bands. Registered hypothesis: short-run edges drive the daily combiner's spillover features; long-run edges drive slower signals. If true, two cleaner inputs replace one blended weight.

**4. LLM-extracted event edges (FinDKG construction pattern). [UNVERIFIED — strategically interesting]**
The financial-KG literature's pattern: an LLM converts unstructured text into typed, dated state-change events and relationships, assembled into a dynamic knowledge graph (one 2026 arXiv paper: LLM → "economic state-change events" → explicit + implicit edges; FinDKG: GPT-4-generated quadruples fine-tune a 7B extractor). ASADO has both inputs: GDELT evidence packs frozen at every dislocation, and Fable in the nightly loop. Fable could emit typed, dated edges (`DISPUTE_WITH`, `SANCTIONS_TIGHTENED`, `TRADE_PACT_SIGNED`) instead of prose-only conjectures. **Constitution conflict to resolve first:** GDELT text may never enter detectors mechanically — these edges land context-tier or as registered hypotheses unless the constitution is deliberately amended.

## B. Better algorithms on the edges already held

**5. Temporal (time-respecting) centrality. [CONFIRMED bias finding; the higher-order variant UNVERIFIED]**
ECB WP 2667 (Franch, Nocciola & Vouldis 2022; peer-reviewed JFS 71, 2024): centrality on a time-aggregated vintage stack biases toward large hubs — static measures ranked US/Japan as contagion sources while temporal (time-respecting-path) measures identified the actual crisis-hit propagators (Greece/Spain/Italy); mechanism: time-aggregation implicitly assumes edge transitivity across vintages. ASADO's features are already per-vintage (good — no stacking), but still static-per-snapshot; the second-order temporal variant separated sources/transmitters/receivers where static could not (that specific discrimination claim: unverified). Key design decision: the delta parameter bounding how far apart consecutive vintage edges may sit in one propagation chain — calibrate per edge type (quarterly BIS vs annual trade). One registered family: temporal centrality vs current static, charged once. (Caveat: the paper's setting is a causality network on 16 economies excluding China — bias magnitude on exposure-weighted country vintages is inferred.)

**6. Directionality and asymmetry. [CONFIRMED framing]**
BIS WP 796 reads lending-side centrality as credit risk and borrowing-side centrality as funding risk — two distinct node features from one network. ASADO's features are symmetric aggregates. From the directed matrices already stored: in/out strength, asymmetric neighbor gaps (creditor-side vs debtor-side moves), and the borrower/lender centrality pair as separate features.

**7. Contagion-modified stress metrics. [CONFIRMED magnitude]**
BIS WP 796 (Avdjiev, Giudici & Spelta 2019): network-modified ("multivariate") CDS spreads roughly **triple** univariate spreads for Greece/Portugal/Ireland and rise 3.5–3.9× for Italy/Spain on both borrowing and lending sides; core countries with <10bp univariate spreads lift materially. Network propagation of a risk metric is first-order, not cosmetic. Build: `network_adjusted_cds` (then vol/drawdown) from daily CDS × quarterly banking vintages — PIT-clean, directly comparable against the univariate series already in `sovereign_signals`; the modified-minus-univariate gap is itself the signal candidate. (Related but UNVERIFIED: the paper's tensor/Markov compression of the multi-layer network, and its out-of-sample CDS-forecasting superiority.)

**8. Multiplex centrality — one registered experiment, no more. [UNVERIFIED]**
Documented (Chuluun, Global Finance Journal 33, 2017): countries central in *both* portfolio and trade networks comove even more (controlling for trade connectedness; corroborated BoJ WP 18E07, IMF WP 19/181). But combined-centrality-as-signal failed verification. Run joint per-vintage multiplex centrality as one charged family; expect high correlation with existing features; let the harness decide. Never time-aggregate the layers (finding 5).

## C. Global network state as a regime layer

**9. Network-state variables for the combiner. [UNVERIFIED lead — cheap enough to build anyway]**
An equity-ML result (PLOS One, unverified): global network properties predicted returns better than node-level centralities. Independently of that paper: ASADO has zero global graph-state features. Five scalar regime columns per day from the vintages — density, average path length, clustering, component/fragmentation count, cross-layer density spread. Seconds to compute; natural combiner inputs and detector context. Unverified status should stop the belief, not the build.

**10. Density direction discipline. [CONFIRMED — a trap warning]**
Causality-network density closely tracks systemic stress (rises in crises); direct-exposure networks freeze or fragment (deleveraging: Minoiu & Reyes IMF WP 11/74 — connectivity fell end-2008 vs end-2007; Cerutti & Claessens WP 14/180). So the sign of any density-regime relationship depends on the edge family. The divergence itself — exposure graph contracting while the market-estimated spillover graph (idea 2) connects — is a detector waiting to be written.

## D. Content already in the graph that nothing consumes

**11. Crisis-history and sanctions edges.** `HAS_CRISIS_HISTORY` (378 edges) feeds zero features. Uses: neighbor-with-crisis-history conditioning on propagation features (does shock transmit faster between countries with shared crisis history?); co-crisis pairs as a similarity edge; fix `SUBJECT_TO` (currently `collect(s)[0]` — arbitrary) so sanctions-intensification dates become event-study anchors. All PIT-safe, all currently dead weight.

**12. Funding concentration (inbound HHI). [UNVERIFIED lead — trivial build]**
Herfindahl of inbound BIS exposure shares per country per vintage — a country funded by few creditors is a different contagion object than one funded by thirty. One column per vintage. (The specific CGFS-sourced numbers did not verify; treat the source's claims from that paper with suspicion — one claim from it was refuted outright.)

**13. Edge formation vs edge weight. [UNVERIFIED lead]**
One BIS analysis found link *existence* survives crises while *weights* compress (total gross exposures dipped after LTCM as degree held). Split the features: "first-time link formation" (slow regime event) vs "weight change conditional on existence" (crisis-sensitive) — today's features conflate them.

## E. The GNN path — one honest experiment, calibrated expectations

**14.** Two data points bracket the question: a controlled comparison (SDU, emerging-market sovereign data) found a GCN beat a comparable feed-forward net on *sovereign spread changes*, largest gains on large moves [UNVERIFIED]; Amundi's MSCI World backtest found a GCN layer on an LSTM barely changed gross returns but cut turnover — a stabilizer, not an alpha source [UNVERIFIED]. Translation: this is exactly **Milestone 8 of ASADO_ML_ARCHITECTURE_PLAN.md** (explicit graph model on PIT adjacency tensors, permuted-graph and no-graph placebos already mandated). The research adds two design notes: score on spread-change / large-move objectives where the evidence points; treat turnover stabilization as a legitimate secondary outcome. No new plan needed.

## Refuted by the verification panel — do not re-propose from these sources

- "Time-varying connectedness is obtained in exactly two ways (rolling window or TVP-VAR)" — REFUTED against the package source.
- "Bond market was the dominant post-Lehman transmitter across US stock/bond/FX/commodity spillovers (1999-2009)" — REFUTED (2-of-3 against).
- "BIS cross-border network monotonically tightened 1985-2006 (connectivity up, path length down)" — REFUTED. (Note: the same CGFS source's surviving claims are weak — one related claim refuted, two unverified.)

## Sequencing by leverage per day-of-work

1. **#1** common-holder overlap edges — data in hand, strongest confirmed precedent, ~1 day.
2. **#7** contagion-modified CDS — confirmed magnitude, data in hand, PIT-clean.
3. **#2** DY spillover network — biggest new surface; production tooling verified; daily returns already in the DB.
4. **#5** temporal centrality — fixes a documented bias in features already trusted; one charged family.
5. **#9–10** network-state regime columns + the density-divergence detector — an afternoon, plus a new detector.
6. **#14** Milestone-8 GCN with the spread-change objective — rides the already-planned ML milestone.

## Honest limits of the evidence base

- Most confirmed evidence is crisis-era (2007-2015) and associational, not causal; external validity to a 34-node country graph is the binding constraint — which is precisely what the harness's front door is for.
- Anton-Polk alphas are US equities 1983-2008, gross, in-sample; the country-level port is untested analogy.
- CPIS-class holder data has coverage gaps and annual-to-semiannual frequency — ASADO's 25 vintages already carry this; handle missing bilateral cells explicitly.
- FEVD connectedness is normalization/horizon/window-sensitive — pre-register those parameters.
- The "implication for ASADO" framings in findings 5 and 1 are extrapolations from the sources, not demonstrated results.
