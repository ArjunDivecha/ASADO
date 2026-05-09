"""
=============================================================================
SCRIPT NAME: scripts/qa/step_validators.py
=============================================================================

INPUT FILES:
- All pipeline output files (read-only validation, no writes)

OUTPUT FILES:
- None (raises ValidationError on failure, prints stats on success)

VERSION: 1.0
LAST UPDATED: 2026-04-29
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
Post-step output validators for the ASADO monthly update pipeline.
Each validator function checks that the expected outputs exist, are non-empty,
have correct schema, and contain plausible data (row counts, country coverage,
date recency). Called from run.py as inline I() steps after each script step.

Validators are lightweight and read-only — no side effects, no writes.
All failures raise ValidationError with a clear message.

DEPENDENCIES:
- pandas, pyarrow (for parquet checks)
- duckdb (for database checks)
- neo4j (optional, for graph checks)

USAGE:
  Imported by run.py; not run standalone.
=============================================================================
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Paths ──────────────────────────────────────────────────────────────────────

_HERE          = Path(__file__).resolve().parent
BASE_DIR       = _HERE.parent.parent           # ASADO root
DATA_DIR       = BASE_DIR / "Data"
PROCESSED_DIR  = DATA_DIR / "processed"

GDELT_DIR      = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT")
GDELT_DEEP_DIR = GDELT_DIR / "Deep"

T2_FUZZY_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy")
T2_GDELT_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 GDELT")
T2_ECON_DIR  = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Econ")


# ── Base helpers ───────────────────────────────────────────────────────────────

class ValidationError(Exception):
    pass


def _check_file(path: Path, min_kb: float = 0.1) -> float:
    """Assert file exists and is non-trivially sized. Returns size in KB."""
    if not path.exists():
        raise ValidationError(f"missing output file: {path.name}")
    kb = path.stat().st_size / 1024
    if kb < min_kb:
        raise ValidationError(f"file too small ({kb:.1f} KB, min {min_kb} KB): {path.name}")
    return kb


def _read_parquet(path: Path, min_rows: int = 1) -> pd.DataFrame:
    _check_file(path)
    try:
        df = pd.read_parquet(path)
    except Exception as exc:
        raise ValidationError(f"cannot read parquet {path.name}: {exc}")
    if len(df) < min_rows:
        raise ValidationError(
            f"only {len(df):,} rows in {path.name}, expected ≥{min_rows:,}"
        )
    return df


def _check_recency(max_date, max_age_days: int, label: str = "latest") -> None:
    """Raise ValidationError if max_date is older than threshold."""
    if max_date is None:
        return
    if hasattr(max_date, "date"):
        max_date = max_date.date()
    elif isinstance(max_date, str):
        max_date = datetime.strptime(max_date[:10], "%Y-%m-%d").date()
    age = (date.today() - max_date).days
    if age > max_age_days:
        raise ValidationError(
            f"{label} is {age}d old (threshold {max_age_days}d) — "
            f"data may not have been updated"
        )
    print(f"    {label}: {max_date}  ({age}d ago) ✓")


def _validate_tidy_panel(
    path: Path,
    min_rows: int,
    min_countries: int,
    required_vars: list[str] | None = None,
    max_age_days: int = 60,
) -> pd.DataFrame:
    """Validate a tidy (date, country, value, variable, source) parquet panel."""
    df = _read_parquet(path, min_rows=min_rows)

    required_cols = {"date", "country", "value", "variable", "source"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        raise ValidationError(f"missing tidy columns {missing_cols} in {path.name}")

    countries = df["country"].nunique()
    if countries < min_countries:
        raise ValidationError(
            f"only {countries} countries in {path.name}, expected ≥{min_countries}"
        )

    if required_vars:
        present = set(df["variable"].unique())
        missing_vars = set(required_vars) - present
        if missing_vars:
            raise ValidationError(
                f"missing key variables {missing_vars} in {path.name}"
            )

    dates = pd.to_datetime(df["date"])
    max_date = dates.max().date()

    variables = df["variable"].nunique()
    print(f"    {len(df):,} rows | {countries} countries | {variables} variables "
          f"| {dates.min().strftime('%Y-%m')} → {max_date}")
    _check_recency(max_date, max_age_days, label="latest data")
    return df


# ── GDELT Shallow ──────────────────────────────────────────────────────────────

def validate_gdelt_shallow() -> None:
    """Shallow: country_day/ has recent parquet files."""
    country_day_dir = GDELT_DIR / "data" / "country_day"
    if not country_day_dir.exists():
        raise ValidationError(f"country_day/ dir not found: {country_day_dir}")

    files = sorted(country_day_dir.glob("*.parquet"))
    if len(files) < 100:
        raise ValidationError(
            f"only {len(files)} country-day parquet files, expected ≥100"
        )

    latest_label = files[-1].stem  # YYYY-MM-DD
    try:
        latest_date = datetime.strptime(latest_label, "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError(f"unrecognised date stem in country_day/: {latest_label}")

    print(f"    {len(files):,} country-day files cached")
    _check_recency(latest_date, max_age_days=30, label="latest GDELT day")


# ── GDELT Deep Article backfill ────────────────────────────────────────────────

def validate_gdelt_deep_articles() -> None:
    feats = GDELT_DEEP_DIR / "data" / "features"
    for subdir in ("article_themes_daily", "article_gcam_daily"):
        d = feats / subdir
        if not d.exists():
            raise ValidationError(f"missing dir: {subdir}")
        files = sorted(d.glob("*.parquet"))
        if len(files) < 10:
            raise ValidationError(
                f"only {len(files)} files in {subdir}, expected ≥10"
            )
        latest = files[-1].stem
        latest_date = datetime.strptime(latest, "%Y-%m-%d").date()
        age = (date.today() - latest_date).days
        print(f"    {subdir}: {len(files):,} files, latest {latest} ({age}d ago)")
        if age > 45:
            raise ValidationError(f"{subdir} is {age}d old — article backfill may have failed")


# ── GDELT Deep feature aggregates ─────────────────────────────────────────────

def _validate_deep_feature_parquet(
    path: Path,
    col_prefix: str,
    min_cols: int,
    max_age_days: int = 60,
) -> None:
    df = _read_parquet(path, min_rows=100)
    feature_cols = [c for c in df.columns if c.startswith(col_prefix)]
    if len(feature_cols) < min_cols:
        raise ValidationError(
            f"only {len(feature_cols)} {col_prefix}* columns in {path.name}, expected ≥{min_cols}"
        )
    if "date" in df.columns:
        max_date = pd.to_datetime(df["date"]).dt.date.max()
        print(f"    {path.name}: {len(df):,} rows | {len(feature_cols)} {col_prefix}* cols")
        _check_recency(max_date, max_age_days)
    else:
        print(f"    {path.name}: {len(df):,} rows | {len(feature_cols)} {col_prefix}* cols")


def validate_gdelt_deep_themes() -> None:
    _validate_deep_feature_parquet(
        GDELT_DEEP_DIR / "data" / "features" / "country_themes_daily.parquet",
        col_prefix="theme_", min_cols=20,
    )


def validate_gdelt_deep_gcam() -> None:
    _validate_deep_feature_parquet(
        GDELT_DEEP_DIR / "data" / "features" / "country_gcam_daily.parquet",
        col_prefix="gcam_", min_cols=10,
    )


def validate_gdelt_deep_events() -> None:
    path = GDELT_DEEP_DIR / "data" / "features" / "country_events_daily.parquet"
    if not path.exists():
        # Events pipeline requires a separate BigQuery/normalize_events init step
        print(f"    ⚠ {path.name} not found — events pipeline not yet initialised (skipping)")
        return
    _validate_deep_feature_parquet(path, col_prefix="event_", min_cols=5)


def validate_gdelt_deep_join() -> None:
    path = GDELT_DIR / "data" / "panels" / "country_signal_daily_deep.parquet"
    df = _read_parquet(path, min_rows=1_000)
    required = {"date", "country_iso3"}
    missing = required - set(df.columns)
    if missing:
        raise ValidationError(f"missing columns {missing} in {path.name}")
    deep_cols = [c for c in df.columns if c.startswith(("theme_", "gcam_", "event_"))]
    if not deep_cols:
        raise ValidationError(
            f"no deep feature columns (theme_*, gcam_*, event_*) in {path.name} — join may have failed"
        )
    max_date = pd.to_datetime(df["date"]).dt.date.max()
    print(f"    {path.name}: {len(df):,} rows | {df['country_iso3'].nunique()} countries | {len(deep_cols)} deep cols")
    _check_recency(max_date, max_age_days=60)


def validate_gdelt_deep_monthly() -> None:
    path = GDELT_DEEP_DIR / "data" / "features" / "country_signal_monthly_deep.parquet"
    df = _read_parquet(path, min_rows=100)
    iso_col = "country_iso3" if "country_iso3" in df.columns else None
    month_col = "signal_month" if "signal_month" in df.columns else None
    countries = df[iso_col].nunique() if iso_col else "?"
    months = df[month_col].nunique() if month_col else "?"
    print(f"    {path.name}: {len(df):,} rows | {countries} countries | {months} months")


def validate_gdelt_deep_treatments() -> None:
    path = GDELT_DEEP_DIR / "data" / "features" / "country_signal_monthly_deep_treated.parquet"
    df = _read_parquet(path, min_rows=100)
    treated = [c for c in df.columns if c.endswith(("_fast", "_slow", "_trend", "_z", "_fast_z"))]
    if len(treated) < 50:
        raise ValidationError(
            f"only {len(treated)} EWMA-treated columns in {path.name}, expected ≥50"
        )
    print(f"    {path.name}: {len(df):,} rows | {len(df.columns)} total cols | {len(treated)} treated cols")


# ── ASADO data collectors ──────────────────────────────────────────────────────

def validate_external_collector() -> None:
    _validate_tidy_panel(
        PROCESSED_DIR / "external_factors_panel.parquet",
        min_rows=50_000, min_countries=20,
        required_vars=["EPU", "GPR"],
    )


def validate_extended_collector() -> None:
    _validate_tidy_panel(
        PROCESSED_DIR / "extended_factors_panel.parquet",
        min_rows=30_000, min_countries=15,
    )


def validate_imf_collector() -> None:
    _validate_tidy_panel(
        PROCESSED_DIR / "imf_factors_panel.parquet",
        min_rows=30_000, min_countries=20,
    )


def validate_bilateral_collector() -> None:
    found = 0
    for name in ("bilateral_trade_matrix.parquet", "bilateral_banking_matrix.parquet",
                 "bilateral_portfolio_matrix.parquet"):
        path = PROCESSED_DIR / name
        if path.exists():
            df = _read_parquet(path, min_rows=10)
            print(f"    {name}: {len(df):,} rows")
            found += 1
        else:
            print(f"    ⚠ {name} not found (may be optional)")
    if found == 0:
        raise ValidationError("no bilateral matrix parquet files found")


def validate_macrostructure_collector() -> None:
    _validate_tidy_panel(
        PROCESSED_DIR / "macrostructure_panel.parquet",
        min_rows=10_000, min_countries=15,
    )


def validate_bloomberg_collector() -> None:
    _validate_tidy_panel(
        PROCESSED_DIR / "bloomberg_factors_panel.parquet",
        min_rows=10_000, min_countries=10,
    )


def validate_t2_master() -> None:
    for label, t2_dir in [
        ("T2 Fuzzy", T2_FUZZY_DIR),
        ("T2 GDELT", T2_GDELT_DIR),
        ("T2 Econ",  T2_ECON_DIR),
    ]:
        master = t2_dir / "T2 Master.xlsx"
        kb = _check_file(master, min_kb=10)
        print(f"    {label}/T2 Master.xlsx  {kb:,.0f} KB")


def validate_gdelt_deep_ingest() -> None:
    _validate_tidy_panel(
        PROCESSED_DIR / "gdelt_deep_panel.parquet",
        min_rows=100_000, min_countries=20,
    )


# ── DuckDB ─────────────────────────────────────────────────────────────────────

def _open_duckdb():
    db_path = DATA_DIR / "asado.duckdb"
    _check_file(db_path, min_kb=500)
    try:
        import duckdb
        return duckdb.connect(str(db_path), read_only=True)
    except Exception as exc:
        raise ValidationError(f"cannot open asado.duckdb: {exc}")


def _duckdb_table_count(con, table: str) -> int:
    try:
        return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception as exc:
        raise ValidationError(f"cannot query table {table}: {exc}")


def validate_duckdb_pass1() -> None:
    con = _open_duckdb()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        required = {"external_factors", "extended_factors", "imf_factors"}
        missing = required - tables
        if missing:
            raise ValidationError(f"missing DuckDB tables after pass 1: {missing}")
        for tbl, min_n in [
            ("external_factors", 50_000),
            ("extended_factors", 30_000),
            ("imf_factors",      30_000),
        ]:
            n = _duckdb_table_count(con, tbl)
            if n < min_n:
                raise ValidationError(f"{tbl}: {n:,} rows, expected ≥{min_n:,}")
            print(f"    {tbl}: {n:,} rows ✓")
        print(f"    {len(tables)} total tables in DuckDB")
    finally:
        con.close()


def validate_normalization_pass1() -> None:
    con = _open_duckdb()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        for tbl in ("normalized_panel", "feature_panel"):
            if tbl not in tables:
                raise ValidationError(f"table {tbl} missing after normalization pass 1")
            n = _duckdb_table_count(con, tbl)
            if n < 10_000:
                raise ValidationError(f"{tbl}: only {n:,} rows")
            print(f"    {tbl}: {n:,} rows ✓")
    finally:
        con.close()


def validate_econ_workbook() -> None:
    path = T2_ECON_DIR / "Econ.xlsx"
    kb = _check_file(path, min_kb=100)
    print(f"    Econ.xlsx: {kb:,.0f} KB ✓")


def validate_gdelt_workbook() -> None:
    path = T2_GDELT_DIR / "GDELT.xlsx"
    kb = _check_file(path, min_kb=100)
    print(f"    GDELT.xlsx: {kb:,.0f} KB ✓")


def validate_t2_step_two_fuzzy() -> None:
    path = T2_FUZZY_DIR / "Normalized_T2_MasterCSV.csv"
    kb = _check_file(path, min_kb=10)
    # Quick column count without loading the whole file
    with open(path) as f:
        header = f.readline()
    ncols = len(header.split(","))
    print(f"    Normalized_T2_MasterCSV.csv: {kb:,.0f} KB | {ncols} columns ✓")


def validate_t2_step_two_gdelt() -> None:
    path = T2_GDELT_DIR / "GDELT_Factors_MasterCSV.csv"
    kb = _check_file(path, min_kb=10)
    with open(path) as f:
        ncols = len(f.readline().split(","))
    print(f"    GDELT_Factors_MasterCSV.csv: {kb:,.0f} KB | {ncols} columns ✓")


def validate_t2_step_two_econ() -> None:
    path = T2_ECON_DIR / "Econ_Factors_MasterCSV.csv"
    kb = _check_file(path, min_kb=10)
    with open(path) as f:
        ncols = len(f.readline().split(","))
    print(f"    Econ_Factors_MasterCSV.csv: {kb:,.0f} KB | {ncols} columns ✓")


def validate_t2_steps_34_fuzzy() -> None:
    for fname, min_kb in [("T2_Top_20_Exposure.csv", 1), ("T2_Optimizer.xlsx", 50)]:
        kb = _check_file(T2_FUZZY_DIR / fname, min_kb=min_kb)
        print(f"    {fname}: {kb:,.0f} KB ✓")


def validate_t2_steps_34_gdelt() -> None:
    for fname, min_kb in [("GDELT_Top_20_Exposure.csv", 1), ("GDELT_Optimizer.xlsx", 50)]:
        kb = _check_file(T2_GDELT_DIR / fname, min_kb=min_kb)
        print(f"    {fname}: {kb:,.0f} KB ✓")


def validate_t2_steps_34_econ() -> None:
    for fname, min_kb in [("Econ_Top_20_Exposure.csv", 1), ("Econ_Optimizer.xlsx", 50)]:
        kb = _check_file(T2_ECON_DIR / fname, min_kb=min_kb)
        print(f"    {fname}: {kb:,.0f} KB ✓")


def validate_optimizer_ingest() -> None:
    con = _open_duckdb()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        for tbl, min_n in [("factor_returns", 10_000), ("factor_top20_membership", 100_000)]:
            if tbl not in tables:
                raise ValidationError(f"table {tbl} missing after optimizer ingest")
            n = _duckdb_table_count(con, tbl)
            if n < min_n:
                raise ValidationError(f"{tbl}: only {n:,} rows, expected ≥{min_n:,}")
            print(f"    {tbl}: {n:,} rows ✓")
    finally:
        con.close()


def validate_duckdb_pass2() -> None:
    con = _open_duckdb()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        for tbl, min_n in [
            ("feature_panel",    1_000_000),
            ("unified_panel",    1_000_000),
            ("normalized_panel",   100_000),
        ]:
            if tbl not in tables:
                raise ValidationError(f"table {tbl} missing after DuckDB pass 2")
            n = _duckdb_table_count(con, tbl)
            if n < min_n:
                raise ValidationError(f"{tbl}: {n:,} rows, expected ≥{min_n:,}")
            print(f"    {tbl}: {n:,} rows ✓")
        print(f"    {len(tables)} total tables ✓")
    finally:
        con.close()


def validate_gdelt_deep_duckdb() -> None:
    con = _open_duckdb()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "gdelt_deep_factors" not in tables:
            raise ValidationError("table gdelt_deep_factors missing from DuckDB")
        n = _duckdb_table_count(con, "gdelt_deep_factors")
        if n < 100_000:
            raise ValidationError(f"gdelt_deep_factors: only {n:,} rows, expected ≥100,000")
        print(f"    gdelt_deep_factors: {n:,} rows ✓")
    finally:
        con.close()


# ── Neo4j ──────────────────────────────────────────────────────────────────────

def validate_neo4j() -> None:
    try:
        from neo4j import GraphDatabase  # type: ignore
    except ImportError:
        raise ValidationError("neo4j driver not installed (pip install neo4j)")

    try:
        driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "mythos2026"))
        with driver.session() as s:
            country_n = s.run("MATCH (c:Country) RETURN count(c) AS n").single()["n"]
            factor_n  = s.run("MATCH (f:Factor) RETURN count(f) AS n").single()["n"]
            edge_n    = s.run("MATCH ()-[r]->() RETURN count(r) AS n").single()["n"]
        driver.close()
    except Exception as exc:
        raise ValidationError(f"Neo4j query failed: {exc}")

    if country_n < 30:
        raise ValidationError(f"only {country_n} Country nodes, expected 34")
    if factor_n < 100:
        raise ValidationError(f"only {factor_n} Factor nodes, expected ≥100")
    print(f"    {country_n} Country nodes | {factor_n} Factor nodes | {edge_n:,} edges ✓")


# ── Schema + Factor Reference ──────────────────────────────────────────────────

def validate_schema_registry() -> None:
    cache_dir = DATA_DIR / "cache" / "query_assistant"
    if not cache_dir.exists():
        raise ValidationError(f"schema cache directory missing: {cache_dir}")
    files = list(cache_dir.glob("*.json"))
    if not files:
        raise ValidationError(f"no JSON files in schema cache: {cache_dir}")
    print(f"    schema cache: {len(files)} file(s) in {cache_dir.name}/ ✓")


def validate_factor_reference() -> None:
    path = BASE_DIR / "docs" / "factor_reference.md"
    kb = _check_file(path, min_kb=1)
    # Count number of variable entries (lines starting with '|')
    lines = path.read_text().count("\n| ")
    print(f"    docs/factor_reference.md: {kb:,.0f} KB | ~{lines} table rows ✓")
