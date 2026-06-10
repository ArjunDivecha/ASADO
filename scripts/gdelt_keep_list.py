"""
=============================================================================
SCRIPT NAME: scripts/gdelt_keep_list.py
=============================================================================

INPUT FILES:
- (none) — this is a pure-Python canonical configuration module, no I/O.

OUTPUT FILES:
- (none) — imported by other scripts; defines no side effects on import.

VERSION: 1.0
LAST UPDATED: 2026-06-03
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
Single source of truth for the GDELT Deep "keep-list" — the curated subset of
GDELT theme / GCAM / event feature columns that ASADO retains. Every script
that filters GDELT Deep features (the warehouse ingest and the optimizer
workbook export) MUST import `keep_deep_feature` from here so the prune rule
can never drift between producers.

WHY THIS EXISTS:
The upstream GDELT Deep panel emits ~1,169 feature columns
(516 theme_*, 450 gcam_*, 120 event_*). Empirical analysis (2026-06-03)
showed the theme/gcam firehose carries the SAME (noise-level) return signal as
the ~71 hand-designed core features, none survived the optimizer's own
curation into the live daily layer, and ~78% of the variable count was
contributing nothing to either signal or narrative. This keep-list prunes the
firehose down to:
  - ~24 interpretable, geopolitically/economically load-bearing themes
    (kept for EXPLANATORY / event-study value, e.g. "who benefits from a war",
    not as return factors), each as {_share, _share_delta};
  - ~16 canonical CAMEO/Goldstein event aggregates (raw level only; the
    downstream T2 GDELT normalization adds _CS/_TS), NEW to the warehouse;
  - ZERO gcam_* (emotional dictionaries — no signal, no narrative value);
  - ZERO other theme_* (the long tail + the TAX_FNCACT occupation-word noise).

The ~71 core designed features (attention_*, country_news_*, dispersion_*,
foreign_tone_*) are produced by a SEPARATE (shallow) pipeline and never pass
through this filter — they are untouched.

USAGE:
  from gdelt_keep_list import keep_deep_feature, KEEP_COLUMNS
  cols = [c for c in df.columns if keep_deep_feature(c)]

NOTES:
- `keep_deep_feature(col)` answers ONLY "is this a GDELT DEEP feature column we
  retain?" It returns False for non-deep columns (core features, metadata) —
  callers that also need to keep core/meta columns handle those separately.
- Theme/event matching is by EXACT column-name membership (no fragile
  prefix/suffix parsing), built once from the base-name lists below.
- To change the prune, edit the *_BASES / EVENT_KEEP lists below; do not
  hand-edit consumers.
=============================================================================
"""

from __future__ import annotations

# ── Themes kept for GEOPOLITICAL / SECURITY explanatory value ────────────────
# Each base B is retained as both theme_{B}_share and theme_{B}_share_delta.
THEME_BASES_GEO: list[str] = [
    "ARMEDCONFLICT",
    "MILITARY",
    "TERROR",
    "TAX_TERROR_GROUP",
    "PROTEST",
    "REFUGEES",
    "BORDER",
    "SECURITY_SERVICES",
    "ENV_OIL",
    "DRUG_TRADE",
    "WB_2432_FRAGILITY_CONFLICT_AND_VIOLENCE",
    "WB_2433_CONFLICT_AND_VIOLENCE",
    "WB_2462_POLITICAL_VIOLENCE_AND_WAR",
    "WB_2467_TERRORISM",
    "WB_507_ENERGY_AND_EXTRACTIVES",
    "WB_698_TRADE",
]

# ── Themes kept for ECONOMIC / MARKETS explanatory value ─────────────────────
THEME_BASES_ECON: list[str] = [
    "ECON_DEBT",
    "ECON_HOUSING_PRICES",
    "ECON_STOCKMARKET",
    "ECON_TAXATION",
    "ECON_WORLDCURRENCIES",
    "WB_1104_MACROECONOMIC_VULNERABILITY_AND_DEBT",
    "WB_450_DEBT",
    "WB_471_ECONOMIC_GROWTH",
]

THEME_BASES: list[str] = THEME_BASES_GEO + THEME_BASES_ECON

# Theme suffixes retained per base: the share level and its month-over-month change.
_THEME_SUFFIXES = ("_share", "_share_delta")

# ── Curated CAMEO / Goldstein EVENT aggregates (RAW level only) ───────────────
# These are NEW to the warehouse (upstream had them; T2 normalization dropped
# them). Raw base aggregates only — downstream T2 GDELT normalization produces
# the _CS/_TS variants. The _fast/_fast_z/_trend/_z EWMA transforms are dropped.
EVENT_KEEP: list[str] = [
    "event_avgtone_mean",                 # overall news tone of events
    "event_goldstein_mean",               # CAMEO Goldstein conflict<->cooperation intensity
    "event_goldstein_sum",                # volume-weighted intensity
    "event_n_total",                      # total event volume
    "event_n_quad1",                      # CAMEO quad: verbal cooperation
    "event_n_quad2",                      # CAMEO quad: material cooperation
    "event_n_quad3",                      # CAMEO quad: verbal conflict
    "event_n_quad4",                      # CAMEO quad: material conflict
    "event_root_fight_n",                 # combat / armed clashes
    "event_root_assault_n",               # assault
    "event_root_protest_n",               # protest
    "event_root_unconv_mass_violence_n",  # unconventional mass violence
    "event_root_threaten_n",              # threats
    "event_root_express_cooperate_n",     # expressed intent to cooperate
    "event_root_diplomatic_coop_n",       # diplomatic cooperation
    "event_root_material_coop_n",         # material cooperation
]

# ── Canonical short names (≤31 chars, Excel-sheet & warehouse variable names) ─
# The T2 GDELT pipeline names each Excel sheet after the column and uses that
# sheet name as the variable base downstream (<sheet>_CS / <sheet>_TS). Excel
# caps sheet names at 31 chars, so long upstream columns must map to clean,
# unique, readable aliases. Columns NOT listed here keep their original name
# (already ≤31 chars). These aliases become the PERMANENT warehouse variable
# names — chosen to be human-readable and collision-free.
CANONICAL_NAME: dict[str, str] = {
    # long event aggregate
    "event_root_unconv_mass_violence_n": "event_mass_violence_n",
    # long ECON themes
    "theme_ECON_HOUSING_PRICES_share": "theme_ECON_HOUSING_share",
    "theme_ECON_HOUSING_PRICES_share_delta": "theme_ECON_HOUSING_share_delta",
    "theme_ECON_STOCKMARKET_share": "theme_ECON_STOCKMKT_share",
    "theme_ECON_STOCKMARKET_share_delta": "theme_ECON_STOCKMKT_share_delta",
    "theme_ECON_WORLDCURRENCIES_share": "theme_ECON_FX_share",
    "theme_ECON_WORLDCURRENCIES_share_delta": "theme_ECON_FX_share_delta",
    "theme_WB_471_ECONOMIC_GROWTH_share": "theme_ECON_GROWTH_share",
    "theme_WB_471_ECONOMIC_GROWTH_share_delta": "theme_ECON_GROWTH_share_delta",
    "theme_WB_1104_MACROECONOMIC_VULNERABILITY_AND_DEBT_share": "theme_MACROVULN_share",
    "theme_WB_1104_MACROECONOMIC_VULNERABILITY_AND_DEBT_share_delta": "theme_MACROVULN_share_delta",
    # long security / conflict themes
    "theme_SECURITY_SERVICES_share": "theme_SECURITY_SVCS_share",
    "theme_SECURITY_SERVICES_share_delta": "theme_SECURITY_SVCS_share_delta",
    "theme_TAX_TERROR_GROUP_share": "theme_TERROR_GROUP_share",
    "theme_TAX_TERROR_GROUP_share_delta": "theme_TERROR_GROUP_share_delta",
    "theme_WB_2467_TERRORISM_share": "theme_TERRORISM_share",
    "theme_WB_2467_TERRORISM_share_delta": "theme_TERRORISM_share_delta",
    "theme_WB_2432_FRAGILITY_CONFLICT_AND_VIOLENCE_share": "theme_FRAGILITY_share",
    "theme_WB_2432_FRAGILITY_CONFLICT_AND_VIOLENCE_share_delta": "theme_FRAGILITY_share_delta",
    "theme_WB_2433_CONFLICT_AND_VIOLENCE_share": "theme_CONFLICT_VIOL_share",
    "theme_WB_2433_CONFLICT_AND_VIOLENCE_share_delta": "theme_CONFLICT_VIOL_share_delta",
    "theme_WB_2462_POLITICAL_VIOLENCE_AND_WAR_share": "theme_POLVIOL_WAR_share",
    "theme_WB_2462_POLITICAL_VIOLENCE_AND_WAR_share_delta": "theme_POLVIOL_WAR_share_delta",
    "theme_WB_507_ENERGY_AND_EXTRACTIVES_share": "theme_ENERGY_EXTR_share",
    "theme_WB_507_ENERGY_AND_EXTRACTIVES_share_delta": "theme_ENERGY_EXTR_share_delta",
}


def canonical_name(col: str) -> str:
    """Return the ≤31-char warehouse/sheet name for a kept upstream column.

    Falls back to the original column name when it is already short enough and
    needs no alias.
    """
    return CANONICAL_NAME.get(col, col)


# ── Built keep-sets (exact column-name membership) ───────────────────────────
THEME_KEEP_COLUMNS: frozenset[str] = frozenset(
    f"theme_{base}{suffix}"
    for base in THEME_BASES
    for suffix in _THEME_SUFFIXES
)
EVENT_KEEP_COLUMNS: frozenset[str] = frozenset(EVENT_KEEP)

# The full set of GDELT Deep feature columns ASADO retains. gcam_* is absent
# by design (all gcam pruned).
KEEP_COLUMNS: frozenset[str] = THEME_KEEP_COLUMNS | EVENT_KEEP_COLUMNS


def keep_deep_feature(col: str) -> bool:
    """Return True iff `col` is a GDELT Deep feature column ASADO retains.

    Rules:
      - theme_*  → keep iff in THEME_KEEP_COLUMNS (the ~24 curated bases ×
                   {_share, _share_delta}); all other themes dropped.
      - gcam_*   → always dropped.
      - event_*  → keep iff in EVENT_KEEP_COLUMNS (the ~16 raw aggregates);
                   the _fast/_fast_z/_trend/_z transforms dropped.
      - anything else (core features, metadata) → False (not a deep feature;
        callers handle those columns on their own).
    """
    if col.startswith("theme_"):
        return col in THEME_KEEP_COLUMNS
    if col.startswith("gcam_"):
        return False
    if col.startswith("event_"):
        return col in EVENT_KEEP_COLUMNS
    return False


def summary() -> dict[str, int]:
    """Return counts for logging / sanity checks."""
    return {
        "theme_bases_geo": len(THEME_BASES_GEO),
        "theme_bases_econ": len(THEME_BASES_ECON),
        "theme_columns": len(THEME_KEEP_COLUMNS),
        "event_columns": len(EVENT_KEEP_COLUMNS),
        "total_keep_columns": len(KEEP_COLUMNS),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(summary(), indent=2))
    print("\nTHEME keep columns:")
    for c in sorted(THEME_KEEP_COLUMNS):
        print("  ", c)
    print("\nEVENT keep columns:")
    for c in sorted(EVENT_KEEP_COLUMNS):
        print("  ", c)
