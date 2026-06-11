#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/build_variable_registry.py
=============================================================================

WHAT THIS PROGRAM DOES (plain English):
ASADO's warehouse holds ~1,600 distinct variable strings across its query
surfaces, but until now there was no single machine-readable record of what
each variable MEANS (definition, units, which direction is "good", how
trustworthy it is, when it becomes knowable). This script builds that record
— the "variable registry" — in three layers that are never mixed:

  1. CURATED SEMANTICS (config/variable_registry_seed.yaml, git-tracked):
     the hand-maintained source of truth. This script can BOOTSTRAP missing
     entries with deterministic fields (base variable, normalization suffix,
     sign extracted from the actual flip lists in the normalize scripts,
     native frequency, broadcast flag) — but it NEVER overwrites an entry
     that already exists in the seed. Humans edit the seed; the script only
     appends skeletons for newly-appeared variables.

  2. AUTO-GENERATED FACTS (variable_registry_facts table): regenerated on
     every run by scanning the live DuckDB — row counts, country counts,
     date ranges, freshness, observed min/max, returns-role tags. Never
     hand-edited.

  3. JOIN VIEW (variable_registry_full): curated ⨝ facts on the variable
     key. This is what downstream consumers (harness, agents, renderer) read.

It also renders a human-readable dictionary (docs/VARIABLE_DICTIONARY.md)
FROM the registry, so the dictionary can never drift from the live DB.

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
    (live warehouse — scanned read-only for the facts layer, then written
     with the variable_registry / variable_registry_facts tables + view)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    (loop DB, read-only — graph_features_daily variables)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/variable_registry_seed.yaml
    (curated semantics seed; created on first --bootstrap-seed run)
- scripts/t2_normalize.py, scripts/econ_normalize.py, scripts/gdelt_normalize.py
    (imported for the ACTUAL sign-flip lists — never guessed)
- scripts/build_schema_registry.py (imported for SOURCE_FREQUENCIES etc.)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/variable_registry_seed.yaml
    (appended with skeleton entries for new variables when --bootstrap-seed)
- Data/asado.duckdb tables: variable_registry (curated), variable_registry_facts
    (auto), and view variable_registry_full (join)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/docs/VARIABLE_DICTIONARY.md
    (rendered human-readable dictionary — a VIEW of the registry, never
     hand-edited)

VERSION: 1.0
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by Cursor agent)

DESCRIPTION:
Phase 0/1 implementation of PRD_Semantic_Layer_Variable_Registry.md.
Enumerates the true variable universe from the live DB (never from docs),
bootstraps/loads the curated seed, scans auto-facts, builds the join view,
and renders the dictionary. Designed to be re-run safely: monthly DB
rebuilds destroy the tables, and this script (wired into monthly_update.py
after the Event Log stage) recreates them from the seed + a fresh scan.

VARIABLE UNIVERSE (decided 2026-06-10, documented per PRD §8 Q1):
- INCLUDED: feature_panel (raw + normalized union), t2_factors_daily,
  t2_levels_daily, gdelt_factors_daily, commodity_panel,
  predmkt_signals_daily, graph_features_daily (loop DB), and the numeric
  columns of gdelt_raw_daily (wide format).
- TAGGED, NOT DUPLICATED: country-return variables (1MRet..120DRet) get
  returns_role tags; factor_returns / factor_returns_daily factor names
  are the same strings as registry variables (the factor IS the variable)
  so they get no separate rows.
- EXCLUDED: bilateral_portfolio_matrix (different grain), event_log,
  predmkt market-metadata tables, and the wb_commodity_prices/indices/
  features tables (their content is covered by commodity_panel strings).

SIGN CONVENTION (extracted from code, the single most error-prone field):
- Raw variables named in t2_normalize.INVERT_NORM / INVERT_NORM_DAILY or
  econ_normalize.ECON_INVERT_SHEETS  -> lower_is_better.
- t2-source and gdelt-source _CS/_TS variants -> higher_is_better BY
  CONSTRUCTION (the normalize scripts multiply by -1 during the build).
- econ-block _CS/_TS variants in normalized_panel are built by
  build_normalized_panel.py which has NO sign logic -> they INHERIT the
  raw variable's sign (lower_is_better if the base is on the econ invert
  list). This asymmetry is deliberate and is exactly why the registry
  records it.
- Everything else -> unknown (never guessed).

DEPENDENCIES: duckdb, pandas, pyyaml (all in the project venv)

USAGE:
  ./venv/bin/python scripts/build_variable_registry.py                  # load seed + scan facts + view + render
  ./venv/bin/python scripts/build_variable_registry.py --bootstrap-seed # also append skeleton seed entries for new variables
  ./venv/bin/python scripts/build_variable_registry.py --check          # scan + report coverage, no writes

NOTES:
- The seed file is append-only from this script's perspective. Hand edits
  (definitions, mechanisms, review_status='verified') are never touched.
- Runtime: ~30-60s (the facts scan aggregates the big daily tables).
=============================================================================
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb
import pandas as pd
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

CONFIG_DIR = BASE_DIR / "config"
DOCS_DIR = BASE_DIR / "docs"
DB_PATH = BASE_DIR / "Data" / "asado.duckdb"
LOOP_DB_PATH = BASE_DIR / "Data" / "loop" / "asado_loop.duckdb"
SEED_PATH = CONFIG_DIR / "variable_registry_seed.yaml"
DICTIONARY_PATH = DOCS_DIR / "VARIABLE_DICTIONARY.md"

# ── the actual flip lists, imported from the code that applies them ─────────
from scripts.t2_normalize import INVERT_NORM, INVERT_NORM_DAILY  # noqa: E402
from scripts.econ_normalize import ECON_INVERT_SHEETS  # noqa: E402
from scripts.gdelt_normalize import FLIP_PREFIXES  # noqa: E402
from scripts.build_schema_registry import (  # noqa: E402
    SOURCE_FREQUENCIES,
    FRESHNESS_THRESHOLDS,
    FORECAST_SOURCES,
    FORECAST_VARIABLE_PREFIXES,
    GLOBAL_REFERENCE_VARIABLES,
    HOME_CURRENCY_REFERENCE_PREFIX,
)

# Trimmed lower-is-better name sets for raw variables (T2 sheet names carry
# trailing spaces like "Best PE " — match on the stripped form).
T2_LOWER_IS_BETTER_RAW = {n.strip() for n in INVERT_NORM} | {n.strip() for n in INVERT_NORM_DAILY}
ECON_LOWER_IS_BETTER_RAW = {n.strip() for n in ECON_INVERT_SHEETS}

COUNTRY_RETURN_MONTHLY = {"1MRet", "3MRet", "6MRet", "9MRet", "12MRet"}
COUNTRY_RETURN_DAILY = {"1DRet", "5DRet", "20DRet", "60DRet", "120DRet"}
COUNTRY_RETURN_ALL = COUNTRY_RETURN_MONTHLY | COUNTRY_RETURN_DAILY

# Sources whose _CS/_TS variants were sign-flipped during construction
# (higher = better by design). The econ block is NOT in this set — see header.
FLIPPED_BY_CONSTRUCTION_SOURCES = {"t2", "gdelt", "t2_daily", "gdelt_daily"}

SOURCE_PROVIDER_MAP = {
    "t2": "T2/Bloomberg", "t2_raw": "T2/Bloomberg", "t2_daily": "T2/Bloomberg",
    "t2_levels": "T2/Bloomberg", "gdelt": "GDELT", "gdelt_daily": "GDELT",
    "gdelt_raw": "GDELT", "bloomberg": "Bloomberg", "bis_credit": "BIS",
    "bis_debt_service": "BIS", "bis_policy_rate": "BIS", "bis_property": "BIS",
    "bis_reer": "BIS", "ecb_fx": "ECB", "eia": "EIA", "epu": "EPU (policyuncertainty.com)",
    "faostat": "FAO", "fred": "FRED", "gpr": "GPR (Caldara-Iacoviello)",
    "ilostat": "ILO", "imf_bop": "IMF", "imf_cpi": "IMF", "imf_er": "IMF",
    "imf_fsi": "IMF", "imf_itg": "IMF", "imf_ls": "IMF", "imf_mfs_ir": "IMF",
    "imf_mfs_cbs": "IMF", "imf_weo": "IMF", "macrostructure_derived": "ASADO derived",
    "ndgain": "ND-GAIN", "oecd": "OECD", "oecd_bci": "OECD", "oecd_cci": "OECD",
    "oecd_household_dashboard": "OECD", "oecd_institutional_investors": "OECD",
    "ofac": "OFAC", "portfolio_ownership": "IMF PIP / US TIC", "qpsd": "World Bank QPSD",
    "undp_hdi": "UNDP", "worldbank": "World Bank", "wb_commodity": "World Bank Pink Sheet",
    "predmkt_signal": "Kalshi/Polymarket (curated)", "graph": "ASADO graph (Neo4j edges)",
    "demographics_dip": "ASADO derived (demographics)",
}


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic curated-field derivation (used only when bootstrapping NEW
# seed entries — existing seed rows are never touched)
# ─────────────────────────────────────────────────────────────────────────────

def parse_normalization(variable: str) -> str:
    if variable.endswith("_CS"):
        return "_CS"
    if variable.endswith("_TS"):
        return "_TS"
    return "raw"


def parse_base_variable(variable: str) -> str:
    if variable.endswith("_CS") or variable.endswith("_TS"):
        return variable[:-3].strip()
    return variable.strip()


def derive_sign(variable: str, source: str) -> str:
    """Extract sign from the actual flip lists. 'unknown' when not derivable."""
    norm = parse_normalization(variable)
    base = parse_base_variable(variable)

    if variable in COUNTRY_RETURN_ALL:
        return "higher_is_better"  # returns: trivially

    if norm in ("_CS", "_TS"):
        if source in FLIPPED_BY_CONSTRUCTION_SOURCES:
            # t2_normalize / gdelt_normalize multiply lower-is-better factors
            # by -1 BEFORE writing _CS/_TS — so post-build, higher = better.
            return "higher_is_better"
        # econ-block normalized variants (build_normalized_panel.py) carry
        # NO flip — they inherit the raw variable's orientation.
        if base in ECON_LOWER_IS_BETTER_RAW:
            return "lower_is_better"
        return "unknown"

    # raw variables
    if base in T2_LOWER_IS_BETTER_RAW or base in ECON_LOWER_IS_BETTER_RAW:
        return "lower_is_better"
    return "unknown"


def derive_native_frequency(surface: str, source: str) -> str:
    if surface in ("t2_factors_daily", "t2_levels_daily", "gdelt_factors_daily",
                   "gdelt_raw_daily", "graph_features_daily", "predmkt_signals_daily"):
        return "D"
    freq = SOURCE_FREQUENCIES.get(source, "monthly")
    return {"daily": "D", "monthly": "M", "quarterly": "Q", "annual": "A"}.get(freq, "M")


def derive_is_broadcast(variable: str, source: str, country_count: int) -> bool:
    if variable in GLOBAL_REFERENCE_VARIABLES:
        return True
    if source == "wb_commodity":
        return True  # commodity_panel is global, no country axis
    if country_count <= 1:
        return True
    return False


def derive_sign_note(variable: str, source: str) -> str:
    norm = parse_normalization(variable)
    base = parse_base_variable(variable)
    if norm in ("_CS", "_TS") and source in FLIPPED_BY_CONSTRUCTION_SOURCES:
        if base in T2_LOWER_IS_BETTER_RAW or any(base.lower().startswith(p) for p in FLIP_PREFIXES):
            return "sign-flipped during normalization (raw concept is lower-is-better)"
    return ""


def new_seed_entry(variable: str, surface: str, source: str, country_count: int) -> Dict[str, Any]:
    """Skeleton seed entry with ONLY deterministic fields populated."""
    sign = derive_sign(variable, source)
    note = derive_sign_note(variable, source)
    return {
        "variable": variable,
        "base_variable": parse_base_variable(variable),
        "normalization": parse_normalization(variable),
        "definition": "",
        "source_provider": SOURCE_PROVIDER_MAP.get(source, ""),
        "source_series_id": "",
        "units": "",
        "cross_country_comparable": None,
        "native_frequency": derive_native_frequency(surface, source),
        "publication_lag": "",
        "revision_prone": None,
        "vintage_available": "",
        "sign": sign,
        "economic_mechanism": "",
        "mechanism_reference": "",
        "concept": "",
        "is_broadcast": derive_is_broadcast(variable, source, country_count),
        "quality_flag": "",
        "valid_range": "",
        "review_status": "unknown",
        "notes": note,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Facts layer — scanned from the live DB, regenerated every run
# ─────────────────────────────────────────────────────────────────────────────

def _freshness(last_date: Any) -> Optional[int]:
    if last_date is None or pd.isna(last_date):
        return None
    d = pd.Timestamp(last_date).date()
    return (date.today() - d).days


def _returns_role(variable: str, source: str, surface: str) -> str:
    if variable in COUNTRY_RETURN_ALL:
        if source == "gdelt" or surface == "gdelt_factors_daily":
            return "country_return_alias"
        return "country_return"
    return "explanatory"


def scan_facts() -> pd.DataFrame:
    """Scan every in-scope surface and return one facts row per (variable, surface)."""
    rows: List[Dict[str, Any]] = []
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        # 1. feature_panel — the monthly query-facing union (raw + normalized)
        df = con.execute(
            """
            SELECT variable, source,
                   COUNT(*) AS row_count,
                   COUNT(DISTINCT country) AS country_count,
                   MIN(date) AS first_date, MAX(date) AS last_date,
                   MIN(value) AS observed_min, MAX(value) AS observed_max,
                   SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS null_pct
            FROM feature_panel GROUP BY 1, 2
            """
        ).fetchdf()
        for r in df.itertuples():
            rows.append(dict(variable=r.variable, surface="feature_panel", source=r.source,
                             row_count=int(r.row_count), country_count=int(r.country_count),
                             first_date=r.first_date, last_date=r.last_date,
                             observed_min=r.observed_min, observed_max=r.observed_max,
                             null_pct=float(r.null_pct),
                             returns_role=_returns_role(r.variable, r.source, "feature_panel")))

        # 2. tidy daily tables
        for table, src in [("t2_factors_daily", "t2_daily"),
                           ("t2_levels_daily", "t2_levels"),
                           ("gdelt_factors_daily", "gdelt_daily")]:
            df = con.execute(
                f"""
                SELECT variable,
                       COUNT(*) AS row_count,
                       COUNT(DISTINCT country) AS country_count,
                       MIN(date) AS first_date, MAX(date) AS last_date,
                       MIN(value) AS observed_min, MAX(value) AS observed_max,
                       SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS null_pct
                FROM {table} GROUP BY 1
                """
            ).fetchdf()
            for r in df.itertuples():
                rows.append(dict(variable=r.variable, surface=table, source=src,
                                 row_count=int(r.row_count), country_count=int(r.country_count),
                                 first_date=r.first_date, last_date=r.last_date,
                                 observed_min=r.observed_min, observed_max=r.observed_max,
                                 null_pct=float(r.null_pct),
                                 returns_role=_returns_role(r.variable, src, table)))

        # 3. commodity_panel — global, no country axis
        df = con.execute(
            """
            SELECT variable,
                   COUNT(*) AS row_count,
                   MIN(date) AS first_date, MAX(date) AS last_date,
                   MIN(value) AS observed_min, MAX(value) AS observed_max,
                   SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS null_pct
            FROM commodity_panel GROUP BY 1
            """
        ).fetchdf()
        for r in df.itertuples():
            rows.append(dict(variable=r.variable, surface="commodity_panel", source="wb_commodity",
                             row_count=int(r.row_count), country_count=0,
                             first_date=r.first_date, last_date=r.last_date,
                             observed_min=r.observed_min, observed_max=r.observed_max,
                             null_pct=float(r.null_pct), returns_role="explanatory"))

        # 4. predmkt signal layer
        df = con.execute(
            """
            SELECT signal_name AS variable,
                   COUNT(*) AS row_count,
                   COUNT(DISTINCT country) AS country_count,
                   MIN(snapshot_date) AS first_date, MAX(snapshot_date) AS last_date,
                   MIN(value) AS observed_min, MAX(value) AS observed_max,
                   SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS null_pct
            FROM predmkt_signals_daily GROUP BY 1
            """
        ).fetchdf()
        for r in df.itertuples():
            rows.append(dict(variable=r.variable, surface="predmkt_signals_daily",
                             source="predmkt_signal",
                             row_count=int(r.row_count), country_count=int(r.country_count),
                             first_date=r.first_date, last_date=r.last_date,
                             observed_min=r.observed_min, observed_max=r.observed_max,
                             null_pct=float(r.null_pct), returns_role="explanatory"))

        # 5. gdelt_raw_daily — wide format: each numeric column is a variable
        cols = con.execute("DESCRIBE gdelt_raw_daily").fetchdf()
        numeric = cols[cols["column_type"].str.contains("DOUBLE|FLOAT|INT|BIGINT|DECIMAL", case=False)]
        skip = {"gkg_files_expected", "gkg_files_fetched", "gkg_files_missing"}
        for col in numeric["column_name"]:
            if col in skip:
                continue
            r = con.execute(
                f"""
                SELECT COUNT("{col}") AS row_count,
                       COUNT(DISTINCT country_iso3) AS country_count,
                       MIN(date) AS first_date, MAX(date) AS last_date,
                       MIN("{col}") AS observed_min, MAX("{col}") AS observed_max,
                       SUM(CASE WHEN "{col}" IS NULL THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS null_pct
                FROM gdelt_raw_daily
                """
            ).fetchone()
            rows.append(dict(variable=col, surface="gdelt_raw_daily", source="gdelt_raw",
                             row_count=int(r[0]), country_count=int(r[1]),
                             first_date=r[2], last_date=r[3],
                             observed_min=r[4], observed_max=r[5],
                             null_pct=float(r[6]), returns_role="explanatory"))
    finally:
        con.close()

    # 6. graph features (loop DB — separate file so monthly rebuilds can't touch it)
    if LOOP_DB_PATH.exists():
        lcon = duckdb.connect(str(LOOP_DB_PATH), read_only=True)
        try:
            df = lcon.execute(
                """
                SELECT variable,
                       COUNT(*) AS row_count,
                       COUNT(DISTINCT country) AS country_count,
                       MIN(date) AS first_date, MAX(date) AS last_date,
                       MIN(value) AS observed_min, MAX(value) AS observed_max,
                       SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS null_pct
                FROM graph_features_daily GROUP BY 1
                """
            ).fetchdf()
            for r in df.itertuples():
                rows.append(dict(variable=r.variable, surface="graph_features_daily", source="graph",
                                 row_count=int(r.row_count), country_count=int(r.country_count),
                                 first_date=r.first_date, last_date=r.last_date,
                                 observed_min=r.observed_min, observed_max=r.observed_max,
                                 null_pct=float(r.null_pct), returns_role="explanatory"))
        finally:
            lcon.close()
    else:
        print(f"  [WARN] loop DB not found at {LOOP_DB_PATH} — graph features skipped")

    facts = pd.DataFrame(rows)
    facts["first_date"] = pd.to_datetime(facts["first_date"]).dt.date
    facts["last_date"] = pd.to_datetime(facts["last_date"]).dt.date
    facts["freshness_days"] = facts["last_date"].map(_freshness)

    def _stale(row) -> bool:
        freq = derive_native_frequency(row["surface"], row["source"])
        freq_name = {"D": "daily", "M": "monthly", "Q": "quarterly", "A": "annual"}[freq]
        thresh = FRESHNESS_THRESHOLDS.get(freq_name, 180)
        return row["freshness_days"] is not None and row["freshness_days"] > thresh

    facts["is_stale"] = facts.apply(_stale, axis=1)
    facts["is_sparse"] = (facts["country_count"] <= 2) & (facts["country_count"] > 0)
    facts["is_forecast"] = facts.apply(
        lambda r: r["source"] in FORECAST_SOURCES or str(r["variable"]).startswith(FORECAST_VARIABLE_PREFIXES),
        axis=1,
    )
    facts["scanned_at"] = datetime.now().isoformat(timespec="seconds")
    return facts


# ─────────────────────────────────────────────────────────────────────────────
# Seed handling (curated layer)
# ─────────────────────────────────────────────────────────────────────────────

def load_seed() -> List[Dict[str, Any]]:
    if not SEED_PATH.exists():
        return []
    with open(SEED_PATH) as f:
        entries = yaml.safe_load(f)
    if entries is None:
        return []
    if not isinstance(entries, list):
        raise ValueError("variable_registry_seed.yaml must be a YAML list")
    return entries


def bootstrap_seed(facts: pd.DataFrame) -> int:
    """Append skeleton entries for live variables missing from the seed.
    NEVER modifies existing entries. Returns count appended."""
    entries = load_seed()
    existing = {e["variable"] for e in entries}

    # Pick the primary surface per variable (priority: monthly query surface
    # first, so source attribution favors feature_panel's source string).
    priority = {"feature_panel": 0, "t2_factors_daily": 1, "gdelt_factors_daily": 2,
                "t2_levels_daily": 3, "commodity_panel": 4, "predmkt_signals_daily": 5,
                "graph_features_daily": 6, "gdelt_raw_daily": 7}
    f = facts.copy()
    f["prio"] = f["surface"].map(priority)
    primary = f.sort_values("prio").drop_duplicates("variable", keep="first")

    appended = []
    for r in primary.itertuples():
        if r.variable in existing:
            continue
        appended.append(new_seed_entry(r.variable, r.surface, r.source, r.country_count))

    if not appended:
        return 0

    appended.sort(key=lambda e: e["variable"])
    all_entries = entries + appended
    header = (
        "# =========================================================================\n"
        "# ASADO Variable Registry — CURATED SEMANTICS SEED\n"
        "# =========================================================================\n"
        "# Source of truth for variable-level semantics (definition, units, sign,\n"
        "# PIT fields, mechanism). Loaded into DuckDB table `variable_registry` by\n"
        "# scripts/build_variable_registry.py.\n"
        "#\n"
        "# RULES:\n"
        "# - This file is HAND-CURATED. The build script only APPENDS skeleton\n"
        "#   entries for newly-appeared variables; it never edits existing ones.\n"
        "# - review_status: 'verified' may only be set by a human. Agents must use\n"
        "#   'model_drafted' for any field they fill and 'unknown' when unsure.\n"
        "# - sign values were extracted from the live flip lists in\n"
        "#   t2_normalize.py / econ_normalize.py / gdelt_normalize.py — see\n"
        "#   build_variable_registry.py header for the full convention.\n"
        "# - Auto-facts (row counts, dates, freshness) do NOT live here; they are\n"
        "#   regenerated into `variable_registry_facts` on every build.\n"
        "# =========================================================================\n\n"
    )
    with open(SEED_PATH, "w") as fh:
        fh.write(header)
        yaml.safe_dump(all_entries, fh, sort_keys=False, allow_unicode=True, width=100)
    return len(appended)


# ─────────────────────────────────────────────────────────────────────────────
# DB load + view
# ─────────────────────────────────────────────────────────────────────────────

CURATED_COLUMNS = [
    ("variable", "VARCHAR"), ("base_variable", "VARCHAR"), ("normalization", "VARCHAR"),
    ("definition", "VARCHAR"), ("source_provider", "VARCHAR"), ("source_series_id", "VARCHAR"),
    ("units", "VARCHAR"), ("cross_country_comparable", "BOOLEAN"), ("native_frequency", "VARCHAR"),
    ("publication_lag", "VARCHAR"), ("revision_prone", "BOOLEAN"), ("vintage_available", "VARCHAR"),
    ("sign", "VARCHAR"), ("economic_mechanism", "VARCHAR"), ("mechanism_reference", "VARCHAR"),
    ("concept", "VARCHAR"), ("is_broadcast", "BOOLEAN"), ("quality_flag", "VARCHAR"),
    ("valid_range", "VARCHAR"), ("review_status", "VARCHAR"), ("notes", "VARCHAR"),
]


def write_db(entries: List[Dict[str, Any]], facts: pd.DataFrame) -> None:
    con = duckdb.connect(str(DB_PATH))
    try:
        # curated table
        cols_sql = ", ".join(f'"{c}" {t}' for c, t in CURATED_COLUMNS)
        con.execute("DROP VIEW IF EXISTS variable_registry_full")
        con.execute("DROP TABLE IF EXISTS variable_registry")
        con.execute(f"CREATE TABLE variable_registry ({cols_sql}, PRIMARY KEY (variable))")
        cur_df = pd.DataFrame(entries)
        for c, _ in CURATED_COLUMNS:
            if c not in cur_df.columns:
                cur_df[c] = None
        cur_df = cur_df[[c for c, _ in CURATED_COLUMNS]]
        con.register("cur_df", cur_df)
        con.execute("INSERT INTO variable_registry SELECT * FROM cur_df")

        # facts table
        con.execute("DROP TABLE IF EXISTS variable_registry_facts")
        con.register("facts_df", facts)
        con.execute("CREATE TABLE variable_registry_facts AS SELECT * FROM facts_df")

        # join view (one row per variable x surface)
        con.execute(
            """
            CREATE VIEW variable_registry_full AS
            SELECT f.variable, f.surface, f.source,
                   r.base_variable, r.normalization, r.definition, r.source_provider,
                   r.source_series_id, r.units, r.cross_country_comparable,
                   r.native_frequency, r.publication_lag, r.revision_prone,
                   r.vintage_available, r.sign, r.economic_mechanism,
                   r.mechanism_reference, r.concept, r.is_broadcast, r.quality_flag,
                   r.valid_range, r.review_status, r.notes,
                   f.row_count, f.country_count, f.first_date, f.last_date,
                   f.freshness_days, f.is_stale, f.is_sparse, f.is_forecast,
                   f.observed_min, f.observed_max, f.null_pct, f.returns_role
            FROM variable_registry_facts f
            LEFT JOIN variable_registry r USING (variable)
            """
        )
    finally:
        con.close()


# ─────────────────────────────────────────────────────────────────────────────
# Renderer — the dictionary is a VIEW of the registry
# ─────────────────────────────────────────────────────────────────────────────

def render_dictionary(entries: List[Dict[str, Any]], facts: pd.DataFrame) -> None:
    by_var = {e["variable"]: e for e in entries}
    lines: List[str] = []
    lines.append("# ASADO Variable Dictionary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now():%Y-%m-%d %H:%M} — by `scripts/build_variable_registry.py`. "
                 "DO NOT EDIT BY HAND: this file is rendered from the variable registry "
                 "(`variable_registry` ⨝ `variable_registry_facts` in `Data/asado.duckdb`). "
                 "Edit semantics in `config/variable_registry_seed.yaml` and re-run the build.")
    lines.append("")
    n_vars = facts["variable"].nunique()
    drafted = sum(1 for e in entries if e.get("review_status") in ("model_drafted", "needs_review"))
    verified = sum(1 for e in entries if e.get("review_status") == "verified")
    lines.append(f"**Coverage:** {n_vars} live variables across {facts['surface'].nunique()} surfaces. "
                 f"Registry rows: {len(entries)} ({verified} verified, {drafted} drafted/needs-review, "
                 f"{len(entries) - verified - drafted} pending semantics).")
    lines.append("")
    lines.append("**Sign convention:** `higher_is_better` / `lower_is_better` from the live flip lists; "
                 "`unknown` = not yet established (never guessed). t2/gdelt `_CS`/`_TS` variants are "
                 "flipped during construction; econ-block `_CS`/`_TS` are NOT and inherit the raw sign.")
    lines.append("")

    for surface in ["feature_panel", "t2_factors_daily", "t2_levels_daily", "gdelt_factors_daily",
                    "commodity_panel", "predmkt_signals_daily", "graph_features_daily", "gdelt_raw_daily"]:
        sub = facts[facts["surface"] == surface].sort_values(["source", "variable"])
        if sub.empty:
            continue
        lines.append(f"## {surface}  ({len(sub)} variables)")
        lines.append("")
        lines.append("| variable | source | freq | sign | role | countries | range | fresh(d) | definition |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for r in sub.itertuples():
            e = by_var.get(r.variable, {})
            sign = {"higher_is_better": "↑", "lower_is_better": "↓", "unknown": "?"}.get(
                e.get("sign", "unknown"), "?")
            role = {"country_return": "RETURN", "country_return_alias": "RET-ALIAS",
                    "explanatory": ""}.get(r.returns_role, "")
            definition = (e.get("definition") or "").replace("|", "/")[:80]
            stale_mark = " ⚠STALE" if r.is_stale else ""
            lines.append(
                f"| {r.variable} | {r.source} | {e.get('native_frequency', '')} | {sign} | {role} "
                f"| {r.country_count} | {r.first_date}→{r.last_date} | {r.freshness_days}{stale_mark} "
                f"| {definition} |"
            )
        lines.append("")

    DICTIONARY_PATH.write_text("\n".join(lines), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Build the ASADO variable registry (seed + facts + view + dictionary)")
    ap.add_argument("--bootstrap-seed", action="store_true",
                    help="Append skeleton seed entries for live variables missing from the seed")
    ap.add_argument("--check", action="store_true", help="Scan and report coverage only; no writes")
    args = ap.parse_args()

    print("=" * 70)
    print("  ASADO VARIABLE REGISTRY BUILD")
    print("=" * 70)

    print("\n  Scanning live DB for the variable universe (facts layer) ...")
    facts = scan_facts()
    n_pairs = len(facts)
    n_vars = facts["variable"].nunique()
    print(f"  Universe: {n_vars} distinct variables / {n_pairs} (variable, surface) pairs")
    for s, n in facts.groupby("surface")["variable"].nunique().sort_values(ascending=False).items():
        print(f"    {s:25s} {n}")

    if args.check:
        entries = load_seed()
        seeded = {e["variable"] for e in entries}
        missing = sorted(set(facts["variable"]) - seeded)
        print(f"\n  Seed entries: {len(entries)} | live vars missing from seed: {len(missing)}")
        if missing[:10]:
            print("  e.g.:", missing[:10])
        return 0 if not missing else 1

    if args.bootstrap_seed:
        n_new = bootstrap_seed(facts)
        print(f"\n  Seed bootstrap: appended {n_new} skeleton entries -> {SEED_PATH.name}")

    entries = load_seed()
    if not entries:
        print("\n  ERROR: seed is empty — run with --bootstrap-seed first")
        return 1

    seeded = {e["variable"] for e in entries}
    live = set(facts["variable"])
    missing = sorted(live - seeded)
    orphans = sorted(seeded - live)
    if missing:
        print(f"\n  WARNING: {len(missing)} live variables have NO seed row (CI will fail):")
        for v in missing[:15]:
            print(f"    - {v}")

    print(f"\n  Loading registry into DuckDB ({len(entries)} curated rows, {n_pairs} fact rows) ...")
    write_db(entries, facts)

    print("  Rendering dictionary ...")
    render_dictionary(entries, facts)

    print(f"\n  DONE.")
    print(f"    seed:       {SEED_PATH}  ({len(entries)} entries)")
    print(f"    tables:     variable_registry, variable_registry_facts, view variable_registry_full")
    print(f"    dictionary: {DICTIONARY_PATH}")
    if orphans:
        print(f"    note: {len(orphans)} seed entries reference variables no longer live "
              f"(kept in seed; flagged by CI as warnings): {orphans[:5]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
