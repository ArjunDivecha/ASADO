#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/collect_gmd_annual.py
=============================================================================

DESCRIPTION:
Ingests the Global Macro Database (GMD) into ASADO as an ISOLATED annual
structural macro reference corpus.

GMD is useful for long-run sovereign macro state, crisis analogs, and
cross-source QA. It is deliberately NOT a live factor feed: this collector
writes its own versioned parquet artifacts, and setup_duckdb.py loads them
into external_reference_gmd_* tables that are not unioned into unified_panel
or feature_panel. Derived structural priors can be promoted later through the
loop DB with explicit publication-lag and point-in-time rules.

INPUTS:
- Python package `global-macro-data` (official GMD client).
- config/country_mapping.json and scripts/loop/loopdb.py::T2_UNIVERSE for
  ASADO country/ISO3 mapping.

OUTPUTS:
- Data/raw/gmd/<version>/metadata/*.parquet
- Data/raw/gmd/<version>/raw_sources/*.parquet
- Data/processed/gmd_annual_panel.parquet
- Data/processed/gmd_raw_source_panel.parquet
- Data/processed/gmd_variable_meta.parquet
- Data/processed/gmd_country_meta.parquet
- Data/processed/gmd_release_manifest.parquet

USAGE:
  ./venv/bin/python scripts/collect_gmd_annual.py
  ./venv/bin/python scripts/collect_gmd_annual.py --raw-sources
  ./venv/bin/python scripts/collect_gmd_annual.py --check

NOTES:
- Date convention matches ASADO's JST annual corpus: YYYY-12-01.
- Forecast marking in the harmonized panel is conservative: year >= release
  year is flagged as forecast-like. Raw-source rows carry GMD's own per-row
  forecast flag when raw data is collected.
- The default license_status is a user-provided local-use assertion. It is
  stored in every row so future consumers can gate export/product use.
=============================================================================
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

try:
    import global_macro_data as gmd_pkg
    from global_macro_data import gmd
except ImportError as exc:  # pragma: no cover - exercised by CLI environment
    raise SystemExit(
        "Missing dependency `global-macro-data`. Install with:\n"
        "  ./venv/bin/python -m pip install global-macro-data"
    ) from exc


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Data"
CONFIG_PATH = BASE_DIR / "config" / "country_mapping.json"

RAW_ROOT = DATA_DIR / "raw" / "gmd"
PROCESSED_DIR = DATA_DIR / "processed"
BACKUP_DIR = DATA_DIR / "backups"

OUT_PANEL = PROCESSED_DIR / "gmd_annual_panel.parquet"
OUT_RAW = PROCESSED_DIR / "gmd_raw_source_panel.parquet"
OUT_VAR_META = PROCESSED_DIR / "gmd_variable_meta.parquet"
OUT_COUNTRY_META = PROCESSED_DIR / "gmd_country_meta.parquet"
OUT_MANIFEST = PROCESSED_DIR / "gmd_release_manifest.parquet"

SOURCE_URL = "https://www.globalmacrodata.com/"
SOURCE = "gmd_harmonized"
RAW_SOURCE = "gmd_raw_source"

# A first-pass raw-source set: enough to inspect provenance/revisions without
# pulling 73 separate raw files every routine monthly run.
RAW_SOURCE_PRIORITY = [
    "infl",
    "govdebt_GDP",
    "govdef_GDP",
    "CA_GDP",
    "rGDP_pc",
    "unemp",
    "REER",
    "USDfx",
    "ltrate",
    "cbrate",
    "BankingCrisis",
    "SovDebtCrisis",
    "CurrencyCrisis",
]

MARKET_SLEEVE_COUNTRIES = {"ChinaH", "NASDAQ", "US SmallCap"}
SOVEREIGN_PROXY_COUNTRIES = {"ChinaA"}


def log(msg: str) -> None:
    print(f"[gmd] {msg}", flush=True)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def selected_version(requested: str | None) -> str:
    if requested is None or requested == "" or requested == "current":
        return gmd_pkg.get_current_version()
    available = set(gmd_pkg.get_available_versions())
    if requested not in available:
        raise SystemExit(
            f"GMD version {requested!r} not found. Available examples: "
            f"{', '.join(gmd_pkg.get_available_versions()[:8])}"
        )
    return requested


def gmd_date(year: pd.Series) -> pd.Series:
    years = pd.to_numeric(year, errors="coerce").astype("Int64")
    return pd.to_datetime(years.astype(str) + "-12-01", errors="coerce")


def graph_role(country: str) -> str:
    if country in MARKET_SLEEVE_COUNTRIES:
        return "market_sleeve"
    if country in SOVEREIGN_PROXY_COUNTRIES:
        return "sovereign_proxy"
    return "sovereign"


def load_t2_mapping() -> pd.DataFrame:
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    from scripts.loop.loopdb import T2_UNIVERSE

    mapping = json.loads(CONFIG_PATH.read_text())["countries"]
    rows = []
    missing = []
    for country in T2_UNIVERSE:
        codes = mapping.get(country)
        if not codes or not codes.get("iso3"):
            missing.append(country)
            continue
        rows.append(
            {
                "country": country,
                "iso3": str(codes["iso3"]).upper(),
                "iso2": codes.get("iso2"),
                "graph_role": graph_role(country),
                "is_market_sleeve": country in MARKET_SLEEVE_COUNTRIES,
            }
        )
    if missing:
        raise SystemExit(f"Missing ISO3 mapping for T2 countries: {missing}")
    return pd.DataFrame(rows)


def parse_csv_list(value: str | None) -> list[str]:
    if value is None or value.strip() == "":
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def official_variables() -> list[str]:
    meta = gmd(vars="load")
    if meta is not None and not meta.empty and "variables" in meta.columns:
        return meta["variables"].dropna().astype(str).tolist()
    return list(gmd_pkg.VALID_VARIABLES)


def variable_list(arg: str | None) -> list[str]:
    official = official_variables()
    if arg is None or arg.strip().lower() in {"", "all"}:
        return official
    requested = parse_csv_list(arg)
    valid = set(official)
    invalid = [v for v in requested if v not in valid]
    if invalid:
        raise SystemExit(f"Invalid GMD variable(s): {invalid}")
    return requested


def raw_variable_list(arg: str | None, all_vars: bool) -> list[str]:
    official = official_variables()
    if all_vars:
        return official
    requested = parse_csv_list(arg)
    if not requested:
        requested = list(RAW_SOURCE_PRIORITY)
    valid = set(official)
    invalid = [v for v in requested if v not in valid]
    if invalid:
        raise SystemExit(f"Invalid raw-source variable(s): {invalid}")
    return requested


def backup_existing(paths: Iterable[Path]) -> None:
    ts = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    for path in paths:
        if path.exists():
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            dest = BACKUP_DIR / f"{path.stem}_{ts}{path.suffix}"
            shutil.copy2(path, dest)
            log(f"backed up {path.name} -> {dest}")


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)


def replicate_to_asado_countries(df: pd.DataFrame, t2_map: pd.DataFrame) -> pd.DataFrame:
    out = df.merge(t2_map, left_on="ISO3", right_on="iso3", how="inner")
    out = out.rename(columns={"countryname": "gmd_countryname"})
    return out


def build_harmonized_panel(version: str, variables: list[str], t2_map: pd.DataFrame,
                           license_status: str) -> pd.DataFrame:
    iso3 = sorted(t2_map["iso3"].unique())
    log(f"pulling harmonized GMD {version}: {len(variables)} variables, {len(iso3)} ISO3 codes")
    wide = gmd(variables=variables, country=iso3, version=version, fast="yes")
    if wide is None or wide.empty:
        raise RuntimeError("GMD harmonized pull returned no rows")

    id_cols = [c for c in ["ISO3", "year", "id", "countryname"] if c in wide.columns]
    value_cols = [c for c in variables if c in wide.columns]
    tidy = wide.melt(id_vars=id_cols, value_vars=value_cols,
                     var_name="variable", value_name="value")
    tidy = tidy.dropna(subset=["value"]).copy()
    tidy["ISO3"] = tidy["ISO3"].astype(str).str.upper()
    tidy = replicate_to_asado_countries(tidy, t2_map)
    tidy["year"] = pd.to_numeric(tidy["year"], errors="coerce").astype("Int64")
    tidy["date"] = gmd_date(tidy["year"])
    release_year = int(version.split("_", 1)[0])
    tidy["is_forecast"] = tidy["year"].astype("Int64") >= release_year
    tidy["forecast_flag_method"] = "year>=gmd_release_year"
    tidy["gmd_version"] = version
    tidy["source"] = SOURCE
    tidy["source_layer"] = "harmonized"
    tidy["license_status"] = license_status
    tidy["source_url"] = SOURCE_URL
    tidy["downloaded_at"] = now_utc()

    cols = [
        "date", "year", "country", "iso3", "iso2", "graph_role",
        "is_market_sleeve", "gmd_countryname", "variable", "value",
        "is_forecast", "forecast_flag_method", "gmd_version", "source",
        "source_layer", "license_status", "source_url", "downloaded_at",
    ]
    return tidy[cols].sort_values(["country", "variable", "year"]).reset_index(drop=True)


def build_variable_meta() -> pd.DataFrame:
    meta = gmd(vars="load")
    if meta is None or meta.empty:
        raise RuntimeError("GMD variable metadata pull returned no rows")
    meta = meta.rename(columns={"variables": "variable"})
    meta["source"] = SOURCE
    meta["retrieved_at"] = now_utc()
    return meta.sort_values("variable").reset_index(drop=True)


def build_country_meta(t2_map: pd.DataFrame) -> pd.DataFrame:
    countries = gmd(country="load")
    if countries is None or countries.empty:
        raise RuntimeError("GMD country metadata pull returned no rows")
    countries["ISO3"] = countries["ISO3"].astype(str).str.upper()
    out = countries.merge(t2_map, left_on="ISO3", right_on="iso3", how="inner")
    out = out.rename(columns={"countryname": "gmd_countryname"})
    out["source"] = SOURCE
    out["retrieved_at"] = now_utc()
    cols = [
        "country", "iso3", "iso2", "graph_role", "is_market_sleeve",
        "gmd_countryname", "ISO2", "ISOnum", "IFS", "tiny", "source",
        "retrieved_at",
    ]
    return out[cols].sort_values(["country"]).reset_index(drop=True)


def raw_source_columns(raw: pd.DataFrame, variable: str) -> list[str]:
    meta = {
        "ISO3", "countryname", "year", variable, "source", "source_change",
        "source_change_count", "forecast", "chainlinking_ratio",
    }
    return [c for c in raw.columns if c not in meta]


def build_raw_source_panel(version: str, raw_vars: list[str], t2_map: pd.DataFrame,
                           license_status: str, raw_dir: Path,
                           force: bool = False) -> pd.DataFrame:
    iso3 = set(t2_map["iso3"].unique())
    frames = []
    raw_dir.mkdir(parents=True, exist_ok=True)
    for i, variable in enumerate(raw_vars, start=1):
        raw_path = raw_dir / f"{variable}.parquet"
        if raw_path.exists() and not force:
            log(f"using cached raw-source GMD {version}: {variable} ({i}/{len(raw_vars)})")
            raw = pd.read_parquet(raw_path)
        else:
            log(f"pulling raw-source GMD {version}: {variable} ({i}/{len(raw_vars)})")
            raw = gmd(variables=variable, raw=True, version=version)
        if raw is None or raw.empty:
            log(f"raw-source pull empty for {variable}; skipping")
            continue
        raw["ISO3"] = raw["ISO3"].astype(str).str.upper()
        raw = raw[raw["ISO3"].isin(iso3)].copy()
        if raw.empty:
            log(f"raw-source pull had no T2 ISO3 rows for {variable}; skipping")
            continue
        write_parquet(raw, raw_path)

        src_cols = raw_source_columns(raw, variable)
        long = raw.melt(
            id_vars=[
                c for c in [
                    "ISO3", "countryname", "year", variable, "source",
                    "source_change", "source_change_count", "forecast",
                    "chainlinking_ratio",
                ] if c in raw.columns
            ],
            value_vars=src_cols,
            var_name="raw_source",
            value_name="raw_value",
        ).dropna(subset=["raw_value"]).copy()
        if long.empty:
            continue
        long = long.rename(columns={variable: "harmonized_value", "source": "chosen_source"})
        long = replicate_to_asado_countries(long, t2_map)
        long["year"] = pd.to_numeric(long["year"], errors="coerce").astype("Int64")
        long["date"] = gmd_date(long["year"])
        long["variable"] = variable
        if "forecast" not in long.columns:
            long["forecast"] = False
        else:
            long["forecast"] = long["forecast"].fillna(False).astype(bool)
        long["is_chosen_source"] = (
            long["raw_source"].astype(str).str.lower()
            == long["chosen_source"].astype(str).str.lower()
        )
        for optional_col in ["source_change", "source_change_count", "chainlinking_ratio"]:
            if optional_col not in long.columns:
                long[optional_col] = pd.NA
        for numeric_col in [
            "harmonized_value",
            "raw_value",
            "source_change_count",
            "chainlinking_ratio",
        ]:
            long[numeric_col] = pd.to_numeric(long[numeric_col], errors="coerce")
        long["gmd_version"] = version
        long["source"] = RAW_SOURCE
        long["license_status"] = license_status
        long["downloaded_at"] = now_utc()
        frames.append(
            long[
                [
                    "date", "year", "country", "iso3", "graph_role",
                    "is_market_sleeve", "gmd_countryname", "variable",
                    "harmonized_value", "raw_source", "raw_value",
                    "chosen_source", "is_chosen_source", "source_change",
                    "source_change_count", "forecast", "chainlinking_ratio",
                    "gmd_version", "source", "license_status", "downloaded_at",
                ]
            ]
        )

    if not frames:
        return pd.DataFrame(
            columns=[
                "date", "year", "country", "iso3", "graph_role",
                "is_market_sleeve", "gmd_countryname", "variable",
                "harmonized_value", "raw_source", "raw_value", "chosen_source",
                "is_chosen_source", "source_change", "source_change_count",
                "forecast", "chainlinking_ratio", "gmd_version", "source",
                "license_status", "downloaded_at",
            ]
        )
    return pd.concat(frames, ignore_index=True).sort_values(
        ["country", "variable", "year", "raw_source"]
    ).reset_index(drop=True)


def build_manifest(version: str, panel: pd.DataFrame, raw_panel: pd.DataFrame,
                   variables: list[str], raw_vars: list[str],
                   license_status: str) -> pd.DataFrame:
    row = {
        "gmd_version": version,
        "package_version": getattr(gmd_pkg, "PACKAGE_VERSION", None),
        "retrieved_at": now_utc(),
        "source_url": SOURCE_URL,
        "license_status": license_status,
        "harmonized_variables": len(variables),
        "raw_source_variables": len(raw_vars),
        "row_count_harmonized": int(len(panel)),
        "row_count_raw_source": int(len(raw_panel)),
        "country_count": int(panel["country"].nunique()) if not panel.empty else 0,
        "iso3_count": int(panel["iso3"].nunique()) if not panel.empty else 0,
        "min_year": int(panel["year"].min()) if not panel.empty else None,
        "max_year": int(panel["year"].max()) if not panel.empty else None,
        "variables_json": json.dumps(variables),
        "raw_source_variables_json": json.dumps(raw_vars),
        "note": (
            "Isolated annual structural macro reference corpus; not in "
            "unified_panel or feature_panel."
        ),
    }
    return pd.DataFrame([row])


def check_outputs() -> int:
    paths = [OUT_PANEL, OUT_VAR_META, OUT_COUNTRY_META, OUT_MANIFEST]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        print("MISSING:")
        for p in missing:
            print(f"  {p}")
        return 1

    panel = pd.read_parquet(OUT_PANEL)
    manifest = pd.read_parquet(OUT_MANIFEST)
    raw = pd.read_parquet(OUT_RAW) if OUT_RAW.exists() else pd.DataFrame()

    print("GMD CHECK")
    print(f"  version: {manifest.loc[0, 'gmd_version']}")
    print(f"  harmonized rows: {len(panel):,}")
    print(f"  countries: {panel['country'].nunique()}  iso3: {panel['iso3'].nunique()}")
    print(f"  variables: {panel['variable'].nunique()}")
    print(f"  years: {int(panel['year'].min())}-{int(panel['year'].max())}")
    print(f"  forecast-like rows: {int(panel['is_forecast'].sum()):,}")
    if not raw.empty:
        print(f"  raw-source rows: {len(raw):,}")
        print(f"  raw-source variables: {raw['variable'].nunique()}")
        print(f"  raw-source providers: {raw['raw_source'].nunique()}")

    latest = (
        panel[~panel["is_forecast"]]
        .groupby("variable", as_index=False)
        .agg(last_year=("year", "max"), countries=("country", "nunique"))
        .sort_values(["countries", "last_year", "variable"], ascending=[True, True, True])
        .head(12)
    )
    print("  thinnest non-forecast variable snapshots:")
    print(latest.to_string(index=False))

    ok = not panel.empty and panel["country"].nunique() == 34 and panel["variable"].nunique() >= 40
    print("CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect Global Macro Database annual panel for ASADO.")
    ap.add_argument("--version", default="current", help="GMD version, e.g. 2026_06, or current.")
    ap.add_argument("--variables", default="all", help="Comma-separated GMD variables, or all.")
    ap.add_argument("--raw-sources", action="store_true", help="Also collect raw-source evidence.")
    ap.add_argument("--raw-source-vars", default="",
                    help="Comma-separated raw-source variables. Default is priority set.")
    ap.add_argument("--raw-source-all", action="store_true",
                    help="Collect raw-source evidence for every valid GMD variable.")
    ap.add_argument("--license-status", default="personal_research",
                    help="Stored in output rows for downstream use gating.")
    ap.add_argument("--force", action="store_true", help="Accepted for monthly_update compatibility.")
    ap.add_argument("--dry-run", action="store_true", help="Print planned pull, write nothing.")
    ap.add_argument("--check", action="store_true", help="Validate existing outputs and exit.")
    args = ap.parse_args()

    if args.check:
        return check_outputs()

    version = selected_version(args.version)
    variables = variable_list(args.variables)
    raw_vars = raw_variable_list(args.raw_source_vars, args.raw_source_all) if args.raw_sources else []
    t2_map = load_t2_mapping()

    print("=" * 72)
    print("  GMD ANNUAL INGEST (isolated structural macro reference)")
    print("=" * 72)
    print(f"  version:        {version}")
    print(f"  variables:      {len(variables)}")
    print(f"  T2 countries:   {len(t2_map)} ({t2_map['iso3'].nunique()} unique ISO3)")
    print(f"  raw sources:    {len(raw_vars)} variables" if args.raw_sources else "  raw sources:    skipped")
    print(f"  license_status: {args.license_status}")
    print("  target:         Data/processed/gmd_*.parquet")
    print("  architecture:   isolated; NOT unified_panel / feature_panel")

    if args.dry_run:
        return 0

    raw_version_dir = RAW_ROOT / version
    meta_dir = raw_version_dir / "metadata"
    raw_source_dir = raw_version_dir / "raw_sources"

    backup_existing([OUT_PANEL, OUT_RAW, OUT_VAR_META, OUT_COUNTRY_META, OUT_MANIFEST])

    var_meta = build_variable_meta()
    country_meta = build_country_meta(t2_map)
    panel = build_harmonized_panel(version, variables, t2_map, args.license_status)
    raw_panel = (
        build_raw_source_panel(version, raw_vars, t2_map, args.license_status, raw_source_dir,
                               force=args.force)
        if args.raw_sources else pd.DataFrame()
    )
    manifest = build_manifest(version, panel, raw_panel, variables, raw_vars, args.license_status)

    write_parquet(panel, OUT_PANEL)
    write_parquet(var_meta, OUT_VAR_META)
    write_parquet(country_meta, OUT_COUNTRY_META)
    write_parquet(manifest, OUT_MANIFEST)
    write_parquet(var_meta, meta_dir / "variable_meta.parquet")
    write_parquet(country_meta, meta_dir / "country_meta.parquet")
    write_parquet(manifest, meta_dir / "release_manifest.parquet")
    if args.raw_sources:
        write_parquet(raw_panel, OUT_RAW)

    log(f"wrote {OUT_PANEL} ({len(panel):,} rows)")
    if args.raw_sources:
        log(f"wrote {OUT_RAW} ({len(raw_panel):,} rows)")
    log(f"version {version}: {panel['country'].nunique()} countries, "
        f"{panel['variable'].nunique()} variables, "
        f"{int(panel['year'].min())}-{int(panel['year'].max())}")
    return check_outputs()


if __name__ == "__main__":
    raise SystemExit(main())
