# Country Interactions — plan of record (2026-08-24)

**Status: PROPOSED — nothing here is implemented; discussion first.**
Consolidates and supersedes as *plans*: `ox-graph-research.md` (14 ideas),
`ox-graph-deep-dive.md` (ideas #15–35 + the six-roles map, which this plan adopts as its
spine), and the Neo4j findings from the 2026-08-24 session. Those documents remain the
evidence record; this is the sequenced program.

---

## 0. The reframe this plan is built on

The request was "make the interactions between countries truly useful — the whole point of
having Neo4j." The evidence says the premise is backwards:

- **The asset is the interaction data, not the graph database.** `graph_edge_vintages`
  (93,800 rows; BIS bank 109 quarterly vintages, IMF trade 27 annual, CPIS holder 25 annual;
  every row correctly lagged, zero look-ahead violations) is the best-built object in the
  repo. Neo4j is one *surface* over that asset.
- **The analytical spine never touches Neo4j.** `build_graph_features_pit.py` reads DuckDB
  and does Katz/hub/bloc in numpy/networkx. At N=34, matrix ops beat Cypher by orders of
  magnitude; every analytical consumer uses the three 34×34 parquet matrices.
- **The only live graph detector reads the quarantined look-ahead table.** D2
  (`scripts/loop/build_dislocations.py:335-336`) consumes `graph_features_daily` — the v1
  table whose pre-2026-06 history applies a 2026 snapshot backward — nightly, with no
  freshness guard and no own-price gate on branch 1.
- **Neo4j's current graph is itself polluted**: 25.6% of `HAS_FACTOR_EXPOSURE` edges are
  future-dated (WEO 2031, DIP 2100 — same forecast class fixed in `db_bridge` on 08-21);
  `LEADS` / `SIMILAR_TO` / `TRADES_WITH` / `HAS_BANKING_EXPOSURE_TO` are single-stamp
  snapshots (as_of 2026-08); `SUBJECT_TO` has the collect(s)[0] bug (every country →
  "Iran Sanctions").

So "maximum use of the data" means, in order: (1) stop feeding the wrong table to the things
that already run; (2) put the unused, sign-agnostic value of the interaction data to work
(conditioning, estimation structure, Layer-2 context — almost entirely unbuilt); (3) add the
two genuinely new mechanisms the ledger has never tested; (4) give Neo4j the one job it is
actually good at.

**Where the program stands (verified current, 2026-08-24):** family `network_spillover`
(23 trials: 6 DEAD / 7 WEAK / 6 WATCH / 4 insufficient) **re-armed 2026-08-20** (June+July
month-end ICs positive) — a sizing gate, not a research verdict. The harness verdict pipeline
**restarted 2026-08-23** (23 re-scores overnight; the deep-dive's "stalled since 07-14"
precondition is now clear). But the 2025–26 yearly ICs on the strongest survivor are still
negative (H_055 5d: −0.034 in 2025, −0.062 in 2026) — the flip is not resolved, the family
just had two good month-ends. Every phase below respects that.

---

## 1. The six roles (adopted from ox-graph-deep-dive Part II)

| role | what | needs diffusion sign? | state |
|---|---|---|---|
| R1 edge data | PIT bilateral vintages | no | well-built (trade/bank/holder) |
| R2 signal features | node-level predictors | **yes** | 23 trials, sign flipped 2024–26 |
| R3 detectors | state monitors | partly | D2 only, on the wrong table |
| R4 conditioning | graph-state gates/sizers | no | unbuilt |
| R5 estimation structure | graph as prior/regularizer | no | nothing exists |
| R6 Layer-2 context | graph-shaped evidence for reasoning | no | nothing — packs carry zero neighbor context |

The verified literature's certainty ordering is **inverted** from ASADO's effort-to-date:
replicated out-of-sample results concentrate in R4/R5/R6 and in one untested R2 mechanism
(forced flows), while return-diffusion R2 — where all 23 trials sit — is where the edge is
being arbitraged. Allocation follows certainty.

---

## 2. Phase 0 — point what already runs at the right data *(fix-first; ~1 session)*

1. **D2 fix batch**: repoint to `graph_features_pit_daily` (PIT twins correlate 0.98–1.00
   with v1 on trade/twohop — verdicts won't jump; holder features, where PIT divergence is
   real (ρ 0.93), are DEAD and unused by D2); add the freshness guard (D5's silent-staleness
   sin); add the own-price gate to branch 1. *Loop code — needs approval, this plan is the
   request.*
2. **Retire `graph_features_daily` (v1)**: quarantine the table (tier-Q already), delete
   `build_graph_features.py` from the nightly, repoint the 6 `family_ic_roster_v1.json`
   references so family IC is measured on the PIT surface.
3. **Neo4j hygiene**: bound `HAS_FACTOR_EXPOSURE` traversals with `date <= today` (or strip
   forecast rows and re-load); fix `SUBJECT_TO`; label `LEADS`/`SIMILAR_TO` as_of-only.
4. **Registry follow-through**: `graph_edge_snapshots.parquet` (monthly current-edge archive,
   3 months old) keeps accumulating — it becomes the PIT record for LEADS/SIMILAR_TO-class
   edges from 2026-06 forward; no backfill pretense.

## 3. Phase 1 — sign-agnostic value (R6, R4, R5; the certainty-first work)

1. **Ego-network evidence packs (#26)** — highest leverage per unit of work in the program.
   `build_evidence_packs.py` joins no adjacency at all today; each dislocation pack should
   carry the country's top-k trade/bank/holder neighbors' states, recent edge deltas, and
   the historical analog set. Reads the parquet matrices, not Neo4j; no trials, no family
   charges, pure Layer-2 leverage.
2. **Exposure-state conditioning package (#20–22)**: the five structural scalars + algebraic
   connectivity of the holder graph + the BIS 3y-claims-growth EWI, plus the
   exposure-vs-return-topology **divergence detector** (#22) as a new D-row. Context tier —
   gates sizing and detector thresholds, never trades. The A7 finding (family earns ~2× its
   IC in EWS TRANSITION/OUT months) makes this the natural conditioning consumer.
3. **Graph-target covariance shrinkage (#25)**: Ledoit-Wolf with the shrinkage target from
   edge intensity. Sign-agnostic, pays even if diffusion alpha never returns; one
   methodology-ledger experiment (realized OOS risk vs standard targets).
4. **Neo4j as the as-of surface**: add `applies_to` to `graph_edge_vintages` (completing the
   interval model — the data already supports any as-of date; month-end slices would store
   ~670k edges to represent 94k), load `*_PIT` relationship types alongside current edges,
   keep current edges as the explainability layer. This is the whole Neo4j build — it serves
   #26 and human exploration, not feature generation.

## 4. Phase 2 — new mechanisms (R2, gated on family taxonomy rulings)

1. **#17 flow-pressure (JLR)**: push-exposure = holder-country flow/stress × CPIS holder
   weights; pressure leg + reversal leg pre-registered. *The one predictive mechanism class
   never tested here.* New family `flow_pressure` — requires the family_registry.yaml edit
   (trust-root change-control). Quick win en route: the TIC monthly rows already in
   `bilateral_portfolio_matrix.parquet` give a monthly-clock US-holder edge at near-zero cost.
2. **#18 trade-imbalance centrality (CBC, JFE 2025)**: signed exports−imports variant of the
   existing IMTS pull; FX leg first (smallest venue problem). New family `external_balance`.
3. **#19 sudden-stop partner exposure**: conditioning-first; one registered interaction trial
   only if the conditional IC separates.

Constraints that bind every Phase-2+ feature: ≥1-day execution embargo by construction;
declared horizon (the month-end trap killed the monthly combiner); any diffusion-flavored
variant charges `network_spillover` (N=23 and rising); never cite pre-embargo t≈4 numbers.

## 5. Phase 3 — the flagship research question (R2)

**#15–16: make the 2024–26 sign flip the research object.** Two-sided transmission test
(convergence vs continuation, by horizon) + the edge-composition hypothesis (complementarity
vs competition edges; needs BACI). Honors the standing G2 gate: partner-weighted returns
orthogonalized against own+global+regional momentum, pooled t≥2, or the territory downgrades.

## 6. Data acquisitions (only when a phase pulls them)

| dataset | unlocks | cost | when |
|---|---|---|---|
| TIC monthly holder edge (on disk already) | #17 monthly clock | ~0 | Phase 2 |
| BACI product-level trade | #16 flagship + competitor edges | ~1 day | Phase 3 |
| UNGA ideal-point dyads (CC0, pre-built) | fragmentation context | hours | Phase 1–2 |
| IMF CDIS FDI stocks | 4th layer | 1 day | only when a trial wants it |
| Swap-line table (hand-curated) | FX-stress conditioning | afternoon | Phase 1–2 |

## 7. What stays dead (earned negatives — do not revisit)

More diffusion proxies on the same trade matrix; Ricci curvature as predictor; neural TKG
on GDELT (recency baseline wins); TDA early warning (~46% hit rate); standalone GNN alpha at
N=34 (M8's comparison design already covers the honest version); holder-derived v1 features
(DEAD both clocks).

## 8. Decision menu (Arjun)

1. Approve Phase 0 (touches loop code + a live detector).
2. Family taxonomy: `flow_pressure` and `external_balance` as new families; diffusion
   variants charge `network_spillover` — write the rule into family_registry.yaml comments.
3. Neo4j role: adopt §3.4 (as-of + Layer-2 surface; feature generation stays in DuckDB/numpy).
4. GDELT bilateral aggregation key change (separate live repo).
5. GSDB sanctions non-commercial license — acceptable?
6. Dormant collectors (Comtrade/ACLED) — BACI reduces Comtrade's urgency.

## Files
- This plan: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/docs/COUNTRY_INTERACTION_PLAN_2026-08-24.md`
- Evidence: `ox-graph-deep-dive.md`, `ox-graph-research.md`, `ASADO_DATA_AUDIT.md` (§ PIT),
  session findings 2026-08-24 (Neo4j snapshot/future-dating audit, PIT-twin divergence
  measurement, vintage Jaccard analysis).
