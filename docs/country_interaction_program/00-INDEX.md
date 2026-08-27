# Country-Interaction Program — implementation index

**Parent plan (approved 2026-08-24, "do all of it"):**
`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/docs/COUNTRY_INTERACTION_PLAN_2026-08-24.md`

**Carve-outs the approval does NOT cover** (each is a STOP checkpoint inside its WP):
- GSDB sanctions data (external non-commercial license — needs Arjun's explicit yes)
- GDELT bilateral aggregation key change (separate live production repo)
- Swap-line table hand-curation (needs Arjun or a sourced dataset)

**How to run this program**: one WP per session, in order, each self-contained. Read the WP
file top to bottom before touching anything. Each WP ends committed-clean or restored-clean.
Update the status table here (this file) in the same commit as the WP.

| WP | title | phase | model | depends on | status |
|---|---|---|---|---|---|
| 01 | D2 detector fix batch | 0 | SONNET | — | **DONE 2026-08-24** (gate v2 attribution PASS after Arjun's fix-forward; v1 gate retired as miscalibrated) |
| 02 | v1 feature retirement + gate-roster v2 | 0 | SONNET (STOP branch → OPUS) | 01 | TODO |
| 03 | Neo4j hygiene (forecast dates, SUBJECT_TO) | 0 | SONNET | — | TODO |
| 04 | PIT interval edges (`applies_to`) + Neo4j load | 1 | SONNET | 03 | TODO |
| 05 | Ego-network evidence packs | 1 | SONNET | — | TODO |
| 06 | Exposure-state conditioning + divergence detector | 1 | SONNET | 01 | TODO |
| 07 | Graph-target covariance shrinkage (methodology) | 1 | SONNET | — | TODO |
| 08 | `flow_pressure` family: registry + TIC edge + JLR signal | 2 | SONNET build, OPUS verdict | 02 | TODO |
| 09 | `external_balance` family: CBC imbalance centrality | 2 | SONNET build, OPUS verdict | 02 | TODO |
| 10 | Sudden-stop partner conditioning | 2 | SONNET | 06 | TODO |
| 11 | BACI collector + flagship two-sided transmission test | 3 | OPUS design already embedded; SONNET build | 02, 09 | TODO |
| 12 | UNGA ideal-point dyad edges (context tier) | 1–2 | SONNET | — | TODO |

**Result-dependent joints** (read before starting the dependent WP):
- WP-02 has a STOP branch: if `network_spillover`'s re-armed state does not survive
  re-derivation on the PIT surface, Phases 2–3 sizing posture changes — Arjun decides.
- WP-11 embeds the standing G2 gate: if the orthogonalized IC ≈ 0, Phase-3 work is
  CANCELLED and the diffusion territory downgrades. That is a valid, reportable outcome.

**Standing context every session should know**: family `network_spillover` = 23 trials
(6 DEAD / 7 WEAK / 6 WATCH), re-armed 2026-08-20 off June+July month-ends; 2025–26 yearly
ICs on the strongest survivors are still negative; re-arm is a sizing gate, not a research
verdict. The ≥1-trading-day execution embargo and a declared horizon are constitutional for
every new signal. All new diffusion-flavored variables charge `network_spillover`.
