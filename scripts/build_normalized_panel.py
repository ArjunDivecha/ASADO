#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: build_normalized_panel.py
=============================================================================

INPUT FILES:
- Data/asado.duckdb   (expects unified_panel from setup_duckdb.py)
- scripts/loop/loopdb.py  (T2_UNIVERSE — the canonical 34-country list for the
  feature_panel_t2 view; country_mapping.json has 43 entries and is NOT it)

OUTPUT FILES:
- DuckDB table: normalized_panel
- DuckDB view:  feature_panel
- DuckDB view:  feature_panel_t2  (feature_panel restricted to the 34 T2 names)

VERSION: 1.1
LAST UPDATED: 2026-07-01
AUTHOR: Arjun Divecha

DESCRIPTION:
Builds ASADO's canonical normalization layer on top of the raw DuckDB warehouse.

Design:
  - unified_panel remains the raw analytical warehouse
  - normalized_panel stores ASADO-generated normalized variants
  - feature_panel is the query-facing union of raw + normalized rows
  - feature_panel_t2 (v1.1, audit R3 2026-07-01) is feature_panel filtered to
    the canonical 34-country T2 universe. Multi-country sources leak non-T2
    names (Austria, Greece, ...) into feature_panel — 43 distinct countries as
    of the audit — so every consumer had to re-filter by hand. feature_panel_t2
    is the documented DEFAULT for analysis consumers; raw feature_panel remains
    for coverage QA.

Normalization outputs:
  - _CS  same-date cross-sectional z-scores across countries
  - _TS  rolling time-series z-scores within country/variable groups

The builder intentionally skips sources that are already normalized upstream
or are not appropriate for a second normalization pass.

USAGE:
  ./venv/bin/python scripts/build_normalized_panel.py
  ./venv/bin/python scripts/build_normalized_panel.py --check
=============================================================================
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Dict, List, Tuple

import duckdb
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "Data" / "asado.duckdb"

NORMALIZED_TABLE = "normalized_panel"
FEATURE_VIEW = "feature_panel"
FEATURE_VIEW_T2 = "feature_panel_t2"


def load_t2_names() -> List[str]:
    """The canonical 34 T2 country names.

    NOTE: config/country_mapping.json is NOT the T2 universe — it carries 43
    entries (the 34 T2 names plus 9 auxiliary source-mapping countries such as
    Austria/Greece/Norway), which is exactly how non-T2 names leak into
    feature_panel. The single source of truth for the 34 is
    scripts/loop/loopdb.py::T2_UNIVERSE.
    """
    import sys

    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    from scripts.loop.loopdb import T2_UNIVERSE

    names = list(T2_UNIVERSE)
    if len(names) != 34:
        raise SystemExit(
            f"loopdb.T2_UNIVERSE has {len(names)} countries, expected 34 — refusing to build {FEATURE_VIEW_T2}"
        )
    return names

# Sources already normalized upstream or intentionally excluded from the
# canonical ASADO-generated z-score layer.
EXCLUDED_SOURCES = {
    "t2",
    "t2_raw",
    "gdelt",
    "macrostructure_derived",
}

SOURCE_FREQUENCIES = {
    "bis_credit": "quarterly",
    "bis_debt_service": "quarterly",
    "bis_policy_rate": "daily",
    "bis_property": "quarterly",
    "bis_reer": "monthly",
    "bloomberg": "monthly",
    "ecb_fx": "monthly",
    "eia": "annual",
    "epu": "monthly",
    "faostat": "annual",
    "fred": "monthly",
    "gpr": "monthly",
    "ilostat": "annual",
    "imf_bop": "annual",
    "imf_cpi": "monthly",
    "imf_er": "monthly",
    "imf_fsi": "quarterly",
    "imf_itg": "monthly",
    "imf_ls": "monthly",
    "imf_mfs_ir": "monthly",
    "imf_weo": "annual",
    "ndgain": "annual",
    "oecd": "monthly",
    "oecd_bci": "monthly",
    "oecd_cci": "monthly",
    "oecd_household_dashboard": "annual",
    "oecd_institutional_investors": "quarterly",
    "ofac": "event-driven",
    "portfolio_ownership": "annual",
    "qpsd": "quarterly",
    "undp_hdi": "annual",
    "worldbank": "annual",
}

TS_WINDOW_OBSERVATIONS = {
    "daily": 252,
    "monthly": 60,
    "quarterly": 20,
    "annual": 10,
}

TS_MIN_OBSERVATIONS = {
    "daily": 63,
    "monthly": 24,
    "quarterly": 8,
    "annual": 5,
}


def _load_candidate_rows(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    query = """
        SELECT
            CAST(date AS DATE) AS date,
            country,
            CAST(value AS DOUBLE) AS value,
            variable,
            source
        FROM unified_panel
        WHERE value IS NOT NULL
          AND source NOT IN ('t2', 't2_raw', 'gdelt', 'macrostructure_derived')
          AND variable NOT LIKE '%\\_CS' ESCAPE '\\'
          AND variable NOT LIKE '%\\_TS' ESCAPE '\\'
    """
    df = con.execute(query).fetchdf()
    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["date", "country", "value", "variable", "source"]).copy()
    df = df.sort_values(["variable", "country", "date"]).reset_index(drop=True)
    return df


def _build_cross_sectional(panel: pd.DataFrame) -> pd.DataFrame:
    grouped = panel.groupby(["variable", "source", "date"])["value"]
    means = grouped.transform("mean")
    counts = grouped.transform("count")
    stds = grouped.transform(lambda series: series.std(ddof=0))
    valid = counts.ge(2) & stds.notna() & stds.gt(0)

    if not valid.any():
        return pd.DataFrame(
            columns=[
                "date",
                "country",
                "value",
                "variable",
                "source",
                "normalization",
                "base_variable",
                "normalization_origin",
                "lookback_observations",
                "min_observations",
            ]
        )

    normalized = panel.loc[valid, ["date", "country", "source", "variable"]].copy()
    normalized["value"] = ((panel.loc[valid, "value"] - means.loc[valid]) / stds.loc[valid]).astype(float)
    normalized["base_variable"] = normalized["variable"]
    normalized["variable"] = normalized["variable"] + "_CS"
    normalized["normalization"] = "cs"
    normalized["normalization_origin"] = "asado_generated"
    normalized["lookback_observations"] = pd.NA
    normalized["min_observations"] = 2
    return normalized[
        [
            "date",
            "country",
            "value",
            "variable",
            "source",
            "normalization",
            "base_variable",
            "normalization_origin",
            "lookback_observations",
            "min_observations",
        ]
    ].sort_values(["variable", "country", "date"]).reset_index(drop=True)


def _rolling_window_for_source(source: str) -> Tuple[int | None, int | None, str]:
    frequency = SOURCE_FREQUENCIES.get(source, "monthly")
    return (
        TS_WINDOW_OBSERVATIONS.get(frequency),
        TS_MIN_OBSERVATIONS.get(frequency),
        frequency,
    )


def _build_time_series(panel: pd.DataFrame) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    grouped = panel.groupby(["country", "variable", "source"], sort=False)

    for (country, variable, source), group in grouped:
        window_obs, min_obs, _frequency = _rolling_window_for_source(str(source))
        if window_obs is None or min_obs is None or len(group) < min_obs:
            continue

        ordered = group.sort_values("date").copy()
        rolling_mean = ordered["value"].rolling(window=window_obs, min_periods=min_obs).mean()
        rolling_std = ordered["value"].rolling(window=window_obs, min_periods=min_obs).std(ddof=0)
        z_scores = (ordered["value"] - rolling_mean) / rolling_std
        valid = rolling_std.notna() & rolling_std.gt(0)
        if not valid.any():
            continue

        normalized = ordered.loc[valid, ["date", "country", "source"]].copy()
        normalized["value"] = z_scores.loc[valid].astype(float)
        normalized["variable"] = f"{variable}_TS"
        normalized["base_variable"] = variable
        normalized["normalization"] = "ts"
        normalized["normalization_origin"] = "asado_generated"
        normalized["lookback_observations"] = window_obs
        normalized["min_observations"] = min_obs
        frames.append(
            normalized[
                [
                    "date",
                    "country",
                    "value",
                    "variable",
                    "source",
                    "normalization",
                    "base_variable",
                    "normalization_origin",
                    "lookback_observations",
                    "min_observations",
                ]
            ]
        )

    if not frames:
        return pd.DataFrame(
            columns=[
                "date",
                "country",
                "value",
                "variable",
                "source",
                "normalization",
                "base_variable",
                "normalization_origin",
                "lookback_observations",
                "min_observations",
            ]
        )

    return pd.concat(frames, ignore_index=True).sort_values(
        ["variable", "country", "date"]
    ).reset_index(drop=True)


def build_normalized_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    panel = _load_candidate_rows(con)
    if panel.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "country",
                "value",
                "variable",
                "source",
                "normalization",
                "base_variable",
                "normalization_origin",
                "lookback_observations",
                "min_observations",
            ]
        )

    cross_sectional = _build_cross_sectional(panel)
    time_series = _build_time_series(panel)
    normalized = pd.concat([cross_sectional, time_series], ignore_index=True)
    if normalized.empty:
        return normalized

    normalized["date"] = pd.to_datetime(normalized["date"]).dt.date
    normalized["source"] = normalized["source"].astype(str)
    normalized["variable"] = normalized["variable"].astype(str)
    normalized["base_variable"] = normalized["base_variable"].astype(str)
    normalized["normalization"] = normalized["normalization"].astype(str)
    normalized["normalization_origin"] = normalized["normalization_origin"].astype(str)
    normalized["value"] = pd.to_numeric(normalized["value"], errors="coerce")
    normalized = normalized.dropna(subset=["date", "country", "value", "variable", "source"])
    normalized = normalized.drop_duplicates(
        subset=["date", "country", "variable", "source"],
        keep="last",
    ).reset_index(drop=True)
    return normalized


def write_outputs(con: duckdb.DuckDBPyConnection, normalized: pd.DataFrame) -> None:
    con.execute(f"DROP VIEW IF EXISTS {FEATURE_VIEW_T2}")
    con.execute(f"DROP VIEW IF EXISTS {FEATURE_VIEW}")
    con.execute(f"DROP TABLE IF EXISTS {NORMALIZED_TABLE}")

    if normalized.empty:
        con.execute(
            f"""
            CREATE TABLE {NORMALIZED_TABLE} (
                date DATE,
                country VARCHAR,
                value DOUBLE,
                variable VARCHAR,
                source VARCHAR,
                normalization VARCHAR,
                base_variable VARCHAR,
                normalization_origin VARCHAR,
                lookback_observations INTEGER,
                min_observations INTEGER
            )
            """
        )
    else:
        con.register("normalized_df", normalized)
        con.execute(
            f"""
            CREATE TABLE {NORMALIZED_TABLE} AS
            SELECT
                CAST(date AS DATE) AS date,
                country,
                CAST(value AS DOUBLE) AS value,
                variable,
                source,
                normalization,
                base_variable,
                normalization_origin,
                CAST(lookback_observations AS INTEGER) AS lookback_observations,
                CAST(min_observations AS INTEGER) AS min_observations
            FROM normalized_df
            """
        )
        con.unregister("normalized_df")

    con.execute(
        f"""
        CREATE VIEW {FEATURE_VIEW} AS
        SELECT date, country, value, variable, source
        FROM unified_panel
        UNION ALL
        SELECT date, country, value, variable, source
        FROM {NORMALIZED_TABLE}
        """
    )

    # R3 (2026-07-01): the documented default consumer surface. feature_panel
    # leaks non-T2 countries from multi-country sources; this view pins the
    # canonical 34-name universe so consumers stop re-filtering by hand.
    t2_quoted = ", ".join("'" + n.replace("'", "''") + "'" for n in load_t2_names())
    con.execute(
        f"""
        CREATE VIEW {FEATURE_VIEW_T2} AS
        SELECT date, country, value, variable, source
        FROM {FEATURE_VIEW}
        WHERE country IN ({t2_quoted})
        """
    )

    con.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{NORMALIZED_TABLE}_ctry_date ON {NORMALIZED_TABLE}(country, date)"
    )
    con.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{NORMALIZED_TABLE}_var ON {NORMALIZED_TABLE}(variable)"
    )
    con.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{NORMALIZED_TABLE}_base_norm ON {NORMALIZED_TABLE}(base_variable, normalization, date)"
    )


def check_outputs() -> None:
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        if NORMALIZED_TABLE not in tables:
            print(f"{NORMALIZED_TABLE} not found in {DB_PATH}")
            return

        row_count = con.execute(f"SELECT COUNT(*) FROM {NORMALIZED_TABLE}").fetchone()[0]
        variable_count = con.execute(
            f"SELECT COUNT(DISTINCT variable) FROM {NORMALIZED_TABLE}"
        ).fetchone()[0]
        base_count = con.execute(
            f"SELECT COUNT(DISTINCT base_variable) FROM {NORMALIZED_TABLE}"
        ).fetchone()[0]
        date_min, date_max = con.execute(
            f"SELECT MIN(date), MAX(date) FROM {NORMALIZED_TABLE}"
        ).fetchone()

        print(f"{NORMALIZED_TABLE}: {row_count:,} rows")
        print(f"  normalized variables: {variable_count}")
        print(f"  base variables:       {base_count}")
        print(f"  date range:           {date_min} -> {date_max}")

        if FEATURE_VIEW in tables:
            feature_rows = con.execute(f"SELECT COUNT(*) FROM {FEATURE_VIEW}").fetchone()[0]
            feature_vars = con.execute(
                f"SELECT COUNT(DISTINCT variable) FROM {FEATURE_VIEW}"
            ).fetchone()[0]
            print(f"{FEATURE_VIEW}: {feature_rows:,} rows, {feature_vars} variables")

        views = {row[0] for row in con.execute("SELECT view_name FROM duckdb_views()").fetchall()}
        if FEATURE_VIEW_T2 in views:
            t2_rows, t2_countries = con.execute(
                f"SELECT COUNT(*), COUNT(DISTINCT country) FROM {FEATURE_VIEW_T2}"
            ).fetchone()
            print(f"{FEATURE_VIEW_T2}: {t2_rows:,} rows, {t2_countries} countries (must be <= 34)")
        else:
            print(f"{FEATURE_VIEW_T2}: MISSING — rerun build_normalized_panel.py")

        print("\nSample normalized variables:")
        sample = con.execute(
            f"""
            SELECT variable, source, COUNT(*) AS rows
            FROM {NORMALIZED_TABLE}
            GROUP BY variable, source
            ORDER BY variable, source
            LIMIT 20
            """
        ).fetchdf()
        if sample.empty:
            print("  (no rows)")
        else:
            print(sample.to_string(index=False))
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ASADO normalized DuckDB features")
    parser.add_argument("--check", action="store_true", help="Inspect normalized DuckDB artifacts only")
    args = parser.parse_args()

    if args.check:
        check_outputs()
        return

    if not DB_PATH.exists():
        raise SystemExit(f"DuckDB database not found: {DB_PATH}")

    start = time.time()
    print("=" * 60)
    print("ASADO Normalization Layer")
    print("=" * 60)
    print(f"Database: {DB_PATH}")

    con = duckdb.connect(str(DB_PATH))
    try:
        normalized = build_normalized_features(con)
        write_outputs(con, normalized)

        raw_count = con.execute("SELECT COUNT(*) FROM unified_panel").fetchone()[0]
        raw_vars = con.execute("SELECT COUNT(DISTINCT variable) FROM unified_panel").fetchone()[0]
        norm_count = con.execute(f"SELECT COUNT(*) FROM {NORMALIZED_TABLE}").fetchone()[0]
        norm_vars = con.execute(f"SELECT COUNT(DISTINCT variable) FROM {NORMALIZED_TABLE}").fetchone()[0]
        feature_count = con.execute(f"SELECT COUNT(*) FROM {FEATURE_VIEW}").fetchone()[0]
        feature_vars = con.execute(f"SELECT COUNT(DISTINCT variable) FROM {FEATURE_VIEW}").fetchone()[0]
        t2_count, t2_countries = con.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT country) FROM {FEATURE_VIEW_T2}"
        ).fetchone()

        print(f"  unified_panel:    {raw_count:,} rows, {raw_vars} variables")
        print(f"  normalized_panel: {norm_count:,} rows, {norm_vars} variables")
        print(f"  feature_panel:    {feature_count:,} rows, {feature_vars} variables")
        print(f"  feature_panel_t2: {t2_count:,} rows, {t2_countries} countries (T2-only default view)")

        sample = con.execute(
            f"""
            SELECT variable, COUNT(*) AS rows
            FROM {NORMALIZED_TABLE}
            GROUP BY variable
            ORDER BY rows DESC, variable
            LIMIT 12
            """
        ).fetchdf()
        if not sample.empty:
            print("\n  Top normalized variables by row count:")
            print(sample.to_string(index=False))
    finally:
        con.close()

    elapsed = time.time() - start
    print(f"\nCompleted in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
