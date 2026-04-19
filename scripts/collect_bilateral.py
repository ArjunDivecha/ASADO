#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: collect_bilateral.py
=============================================================================

INPUT FILES:
- config/country_mapping.json: Maps 34 T2 countries to ISO-3 and BIS codes

OUTPUT FILES:
- Data/processed/bilateral_trade_matrix.parquet     (34x34 trade matrix)
- Data/processed/bilateral_banking_matrix.parquet   (reporting x counterparty banking claims)
- Data/processed/bilateral_portfolio_matrix.parquet (portfolio ownership matrix)

VERSION: 1.1
LAST UPDATED: 2026-04-18
AUTHOR: Arjun Divecha

DESCRIPTION:
Collects bilateral (country-to-country) data for Neo4j graph enrichment:

  1. IMF IMTS  — bilateral merchandise trade (exports, imports) between all
                 34 T2 country pairs via SDMX 3.0 API. Annual frequency.
  2. BIS LBS  — cross-border banking claims from BIS Locational Banking
                 Statistics via BIS SDMX CSV API. Quarterly frequency.
  3. IMF PIP  — annual bilateral portfolio holdings benchmark.
  4. U.S. TIC — monthly U.S.-resident holdings of foreign long-term securities.

These are NOT panel variables — they produce adjacency matrices that become
directed edges in the Neo4j knowledge graph:
  - (:Country)-[:TRADES_WITH]->(:Country)
  - (:Country)-[:HAS_BANKING_EXPOSURE_TO]->(:Country)
  - (:Country)-[:HOLDS_PORTFOLIO]->(:Country)

DEPENDENCIES:
- pandas, numpy, requests, pyarrow, tqdm

USAGE:
  python scripts/collect_bilateral.py              # collect both
  python scripts/collect_bilateral.py --trade-only  # trade matrix only
  python scripts/collect_bilateral.py --bank-only   # banking matrix only
  python scripts/collect_bilateral.py --portfolio-only  # portfolio matrix only

NOTES:
- IMF IMTS uses SDMX 3.0 at api.imf.org — no API key needed
- BIS LBS uses CSV API at stats.bis.org — no API key needed
- IMF PIP (formerly CPIS) uses SDMX 3.0 at api.imf.org — no API key needed
- Rate limits: IMF ~10 req/5s, BIS ~1 req/s
- Only ~25 of 34 T2 countries are BIS reporting countries
- ChinaA/ChinaH share CHN; U.S./NASDAQ/US SmallCap share USA
=============================================================================
"""

import argparse
import io
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "country_mapping.json"
PROCESSED_DIR = BASE_DIR / "Data" / "processed"
RAW_DIR = BASE_DIR / "Data" / "raw" / "bilateral" / "us_tic"
TRADE_PQ = PROCESSED_DIR / "bilateral_trade_matrix.parquet"
BANK_PQ = PROCESSED_DIR / "bilateral_banking_matrix.parquet"
PORTFOLIO_PQ = PROCESSED_DIR / "bilateral_portfolio_matrix.parquet"
TIC_RAW_PATH = RAW_DIR / "slt_table2.txt"

IMF_BASE = "https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/IMTS/~"
BIS_BASE = "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_LBS_D_PUB/1.0"
PIP_BASE = "https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/PIP/~"
TIC_TABLE2_URL = "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table2.txt"
PIP_ACCOUNTING_ENTRY = "A"
PIP_SECTOR = "S1"
PIP_COUNTERPART_SECTOR = "S1"
PIP_INDICATORS = {
    # PIP does not split equity from fund shares, so keep the combined label explicit.
    "equity_fund_shares": "P_F51_P_USD",
    "debt_long": "P_F3_L_P_USD",
    "debt_short": "P_F3_S_P_USD",
}

MULTI_MAP = {
    "ChinaA": "CHN", "ChinaH": "CHN",
    "U.S.": "USA", "NASDAQ": "USA", "US SmallCap": "USA",
}

TIC_COUNTRY_TO_ISO3 = {
    "Australia": "AUS",
    "Brazil": "BRA",
    "Canada": "CAN",
    "Chile": "CHL",
    "China, Mainland": "CHN",
    "Denmark": "DNK",
    "France": "FRA",
    "Germany": "DEU",
    "Hong Kong": "HKG",
    "India": "IND",
    "Indonesia": "IDN",
    "Italy": "ITA",
    "Japan": "JPN",
    "Korea, South": "KOR",
    "Malaysia": "MYS",
    "Mexico": "MEX",
    "Netherlands": "NLD",
    "Philippines": "PHL",
    "Poland": "POL",
    "Saudi Arabia": "SAU",
    "Singapore": "SGP",
    "South Africa": "ZAF",
    "Spain": "ESP",
    "Sweden": "SWE",
    "Switzerland": "CHE",
    "Taiwan": "TWN",
    "Thailand": "THA",
    "Turkey": "TUR",
    "United Kingdom": "GBR",
    "Vietnam": "VNM",
}

TIC_INSTRUMENT_MAP = {
    "us_lt_govt_bond_pos": "debt_long_govt",
    "us_lt_corp_bond_pos": "debt_long_corp",
    "us_lt_eqty_pos": "equity",
}


def load_countries():
    """Load country mapping, return unique ISO3 list and reverse map."""
    with open(CONFIG_PATH) as f:
        data = json.load(f)

    iso3_set = {}
    t2_to_iso3 = {}
    for t2_name, codes in data["countries"].items():
        iso3 = codes["iso3"]
        t2_to_iso3[t2_name] = iso3
        if iso3 not in iso3_set:
            iso3_set[iso3] = t2_name

    iso3_to_bis = {}
    for t2_name, codes in data["countries"].items():
        iso3 = codes["iso3"]
        bis = codes.get("bis")
        if bis and iso3 not in iso3_to_bis:
            iso3_to_bis[iso3] = bis

    return list(iso3_set.keys()), iso3_set, t2_to_iso3, iso3_to_bis


def period_to_date(period: str) -> pd.Timestamp | None:
    """Convert IMF period strings to ASADO's aligned period dates."""
    try:
        if "-M" in period:
            year, month = period.split("-M")
            return pd.Timestamp(int(year), int(month), 1)
        if "-Q" in period:
            year, quarter = period.split("-Q")
            return pd.Timestamp(int(year), int(quarter) * 3, 1)
        if len(period) == 4 and period.isdigit():
            return pd.Timestamp(int(period), 12, 1)
    except Exception:
        return None
    return None


def collect_trade(iso3_list: list, iso3_to_t2: dict) -> pd.DataFrame:
    """
    Collect bilateral merchandise trade from IMF IMTS (SDMX 3.0).

    For each unique ISO3 reporter, fetches annual exports (XG_FOB_USD) and
    imports (MG_CIF_USD) to/from every other T2 ISO3 counterpart.

    Returns DataFrame with columns:
      reporter_iso3, counterpart_iso3, exports_usd, imports_usd, year
    """
    print("=" * 60)
    print("Collecting bilateral trade from IMF IMTS ...")
    print("=" * 60)

    records = []
    failed = []

    for reporter in tqdm(iso3_list, desc="  IMF IMTS reporters"):
        others = [c for c in iso3_list if c != reporter]
        cp_str = "+".join(others)

        for indicator, var_name in [("XG_FOB_USD", "exports_usd"), ("MG_CIF_USD", "imports_usd")]:
            url = f"{IMF_BASE}/{reporter}.{indicator}.{cp_str}.A"
            try:
                r = requests.get(url, timeout=60, headers={"Accept": "application/json"})
                if r.status_code != 200:
                    failed.append(f"{reporter}/{indicator}: HTTP {r.status_code}")
                    continue

                data = r.json()
                structs = data.get("data", {}).get("structures", [])
                datasets = data.get("data", {}).get("dataSets", [])
                if not structs or not datasets:
                    continue

                struct = structs[0]
                series_dims = struct.get("dimensions", {}).get("series", [])
                obs_dims = struct.get("dimensions", {}).get("observation", [])

                cp_dim = next((d for d in series_dims if d["id"] == "COUNTERPART_COUNTRY"), None)
                if not cp_dim:
                    continue
                cp_vals = [v["id"] for v in cp_dim.get("values", [])]
                cp_pos = cp_dim.get("keyPosition", 2)

                time_vals = []
                if obs_dims:
                    time_vals = [v.get("value", v.get("id", "")) for v in obs_dims[0].get("values", [])]

                for series_key, series_data in datasets[0].get("series", {}).items():
                    key_parts = series_key.split(":")
                    cp_idx = int(key_parts[cp_pos]) if len(key_parts) > cp_pos else 0
                    cp_iso3 = cp_vals[cp_idx] if cp_idx < len(cp_vals) else None
                    if not cp_iso3 or cp_iso3 not in iso3_list:
                        continue

                    for obs_key, obs_val in series_data.get("observations", {}).items():
                        yr_idx = int(obs_key)
                        year = time_vals[yr_idx] if yr_idx < len(time_vals) else None
                        value = obs_val[0] if obs_val else None
                        if year and value is not None:
                            try:
                                records.append({
                                    "reporter_iso3": reporter,
                                    "counterpart_iso3": cp_iso3,
                                    "year": int(year),
                                    var_name: float(value),
                                })
                            except (ValueError, TypeError):
                                pass

            except Exception as e:
                failed.append(f"{reporter}/{indicator}: {e}")

            time.sleep(0.6)

    if not records:
        print("  No trade data collected")
        return pd.DataFrame()

    df = pd.DataFrame(records)

    exports = df[df["exports_usd"].notna()][["reporter_iso3", "counterpart_iso3", "year", "exports_usd"]]
    imports = df[df["imports_usd"].notna()][["reporter_iso3", "counterpart_iso3", "year", "imports_usd"]]

    merged = pd.merge(exports, imports, on=["reporter_iso3", "counterpart_iso3", "year"], how="outer")
    merged["exports_usd"] = merged["exports_usd"].fillna(0)
    merged["imports_usd"] = merged["imports_usd"].fillna(0)
    merged["total_trade_usd"] = merged["exports_usd"] + merged["imports_usd"]

    latest_year = merged["year"].max()
    latest = merged[merged["year"] == latest_year].copy()

    latest["trade_share_pct"] = 0.0
    for reporter in latest["reporter_iso3"].unique():
        mask = latest["reporter_iso3"] == reporter
        total = latest.loc[mask, "total_trade_usd"].sum()
        if total > 0:
            latest.loc[mask, "trade_share_pct"] = (
                latest.loc[mask, "total_trade_usd"] / total * 100
            )

    n_pairs = len(latest)
    n_reporters = latest["reporter_iso3"].nunique()
    print(f"\n  Trade matrix: {n_pairs} pairs, {n_reporters} reporters, year={latest_year}")
    if failed:
        print(f"  Failed queries: {len(failed)}")

    return latest


def collect_banking(iso3_list: list, iso3_to_bis: dict) -> pd.DataFrame:
    """
    Collect cross-border banking claims from BIS Locational Banking Statistics.

    Uses BIS SDMX CSV API. For each T2 reporting country, fetches total claims
    (stocks, all instruments, all currencies) against each T2 counterparty.

    Returns DataFrame with columns:
      reporter_iso3, counterpart_iso3, claims_usd_millions, quarter
    """
    print("\n" + "=" * 60)
    print("Collecting banking exposure from BIS LBS ...")
    print("=" * 60)

    bis_to_iso3 = {v: k for k, v in iso3_to_bis.items()}
    bis_reporters = list(iso3_to_bis.values())
    bis_counterparts = list(iso3_to_bis.values())

    records = []
    failed = []

    for reporter_bis in tqdm(bis_reporters, desc="  BIS LBS reporters"):
        cp_str = "+".join([c for c in bis_counterparts if c != reporter_bis])
        url = (
            f"{BIS_BASE}/Q.S.C.A.TO1.A.5J.A.{reporter_bis}.A.{cp_str}.N"
            f"?startPeriod=2020&format=csv"
        )

        try:
            r = requests.get(url, timeout=60)
            if r.status_code != 200:
                failed.append(f"{reporter_bis}: HTTP {r.status_code}")
                continue

            df = pd.read_csv(io.StringIO(r.text))
            if df.empty:
                continue

            required_cols = {"L_REP_CTY", "L_CP_COUNTRY", "TIME_PERIOD", "OBS_VALUE"}
            if not required_cols.issubset(df.columns):
                obs_col = [c for c in df.columns if "OBS" in c.upper()]
                if obs_col:
                    df = df.rename(columns={obs_col[0]: "OBS_VALUE"})

            if "OBS_VALUE" not in df.columns:
                continue

            df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
            df = df.dropna(subset=["OBS_VALUE"])

            latest_q = df["TIME_PERIOD"].max()
            latest = df[df["TIME_PERIOD"] == latest_q]

            for _, row in latest.iterrows():
                cp_bis = row["L_CP_COUNTRY"]
                if cp_bis in bis_to_iso3:
                    records.append({
                        "reporter_iso3": bis_to_iso3.get(reporter_bis, reporter_bis),
                        "counterpart_iso3": bis_to_iso3[cp_bis],
                        "claims_usd_millions": float(row["OBS_VALUE"]),
                        "quarter": latest_q,
                    })

        except Exception as e:
            failed.append(f"{reporter_bis}: {e}")

        time.sleep(1.0)

    if not records:
        print("  No banking data collected")
        return pd.DataFrame()

    result = pd.DataFrame(records)
    result = result.groupby(
        ["reporter_iso3", "counterpart_iso3", "quarter"], as_index=False
    ).agg({"claims_usd_millions": "sum"})

    for reporter in result["reporter_iso3"].unique():
        mask = result["reporter_iso3"] == reporter
        total = result.loc[mask, "claims_usd_millions"].sum()
        if total > 0:
            result.loc[mask, "share_of_total_claims_pct"] = (
                result.loc[mask, "claims_usd_millions"] / total * 100
            )

    n_pairs = len(result)
    n_reporters = result["reporter_iso3"].nunique()
    quarter = result["quarter"].iloc[0] if not result.empty else "?"
    print(f"\n  Banking matrix: {n_pairs} pairs, {n_reporters} reporters, quarter={quarter}")
    if failed:
        print(f"  Failed queries: {len(failed)}")

    return result


def collect_portfolio_cpis(iso3_list: list) -> pd.DataFrame:
    """
    Collect bilateral portfolio holdings from IMF PIP (formerly CPIS).

    Query shape:
      COUNTRY.ACCOUNTING_ENTRY.INDICATOR.SECTOR.COUNTERPART_SECTOR.COUNTERPART_COUNTRY.FREQUENCY

    For Phase 1 we use:
      - accounting entry = A (asset-side holdings)
      - sector = S1 (total economy)
      - counterpart sector = S1 (total economy)
      - frequency = A (annual; this is the consistently populated PIP path)
    """
    print("\n" + "=" * 60)
    print("Collecting bilateral portfolio ownership from IMF PIP ...")
    print("=" * 60)

    records = []
    failed = []

    for instrument_type, indicator in PIP_INDICATORS.items():
        for reporter_iso3 in tqdm(iso3_list, desc=f"  IMF PIP {instrument_type}"):
            counterparts = [iso3 for iso3 in iso3_list if iso3 != reporter_iso3]
            if not counterparts:
                continue

            counterpart_key = "+".join(counterparts)
            key = (
                f"{reporter_iso3}.{PIP_ACCOUNTING_ENTRY}.{indicator}."
                f"{PIP_SECTOR}.{PIP_COUNTERPART_SECTOR}.{counterpart_key}.A"
            )
            url = f"{PIP_BASE}/{key}?c[TIME_PERIOD]=ge:2000"

            try:
                response = requests.get(
                    url,
                    timeout=60,
                    headers={"Accept": "application/vnd.sdmx.data+json"},
                )
                if response.status_code != 200:
                    failed.append(f"{reporter_iso3}/{indicator}: HTTP {response.status_code}")
                    continue

                data = response.json().get("data", {})
                datasets = data.get("dataSets", [])
                structures = data.get("structures", [])
                if not datasets or not structures:
                    continue

                structure = structures[0]
                series_dims = structure.get("dimensions", {}).get("series", [])
                observation_dims = structure.get("dimensions", {}).get("observation", [])
                time_values = observation_dims[0].get("values", []) if observation_dims else []
                series = datasets[0].get("series", {})
                if not series:
                    continue

                counterpart_dim = next(
                    (dim for dim in series_dims if dim["id"] == "COUNTERPART_COUNTRY"),
                    None,
                )
                if not counterpart_dim:
                    failed.append(f"{reporter_iso3}/{indicator}: missing COUNTERPART_COUNTRY dimension")
                    continue

                counterpart_values = [value.get("id") for value in counterpart_dim.get("values", [])]
                counterpart_position = counterpart_dim["keyPosition"]

                for series_key, series_data in series.items():
                    key_parts = series_key.split(":")
                    if len(key_parts) <= counterpart_position:
                        continue

                    counterpart_idx = int(key_parts[counterpart_position])
                    if counterpart_idx >= len(counterpart_values):
                        continue
                    counterpart_iso3 = counterpart_values[counterpart_idx]
                    if counterpart_iso3 not in iso3_list:
                        continue

                    for observation_key, observation_value in series_data.get("observations", {}).items():
                        time_idx = int(observation_key)
                        if time_idx >= len(time_values):
                            continue
                        period = time_values[time_idx].get("value", time_values[time_idx].get("id", ""))
                        dt = period_to_date(period)
                        value = observation_value[0] if observation_value else None
                        if dt is None or value is None:
                            continue

                        records.append(
                            {
                                "date": dt,
                                "reporter_iso3": reporter_iso3,
                                "counterpart_iso3": counterpart_iso3,
                                "instrument_type": instrument_type,
                                "amount_usd": float(value),
                                "source": "imf_pip",
                                "frequency": "annual",
                                "is_official_sector": False,
                            }
                        )
            except Exception as exc:
                failed.append(f"{reporter_iso3}/{indicator}: {exc}")

            time.sleep(0.6)

    if not records:
        print("  No portfolio ownership data collected from IMF PIP")
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = (
        df.groupby(
            ["date", "reporter_iso3", "counterpart_iso3", "instrument_type", "source", "frequency", "is_official_sector"],
            as_index=False,
        )
        .agg({"amount_usd": "sum"})
        .sort_values(["date", "reporter_iso3", "instrument_type", "counterpart_iso3"])
        .reset_index(drop=True)
    )

    df["share_of_reporter_portfolio_pct"] = (
        df["amount_usd"]
        / df.groupby(["date", "reporter_iso3", "instrument_type"])["amount_usd"].transform("sum")
        * 100.0
    )
    df["share_of_counterpart_inbound_pct"] = (
        df["amount_usd"]
        / df.groupby(["date", "counterpart_iso3", "instrument_type"])["amount_usd"].transform("sum")
        * 100.0
    )

    latest_date = df["date"].max()
    latest = df[df["date"] == latest_date]
    print(
        f"\n  Portfolio matrix: {len(df):,} rows, "
        f"{latest['reporter_iso3'].nunique()} reporters on latest date {latest_date.date()}"
    )
    if failed:
        print(f"  Failed PIP queries: {len(failed)}")

    return df


def _load_tic_text() -> str | None:
    """Fetch the TIC text file, falling back to the last saved raw copy on error."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(TIC_TABLE2_URL, timeout=60)
        response.raise_for_status()
        TIC_RAW_PATH.write_text(response.text, encoding="utf-8")
        return response.text
    except Exception:
        if TIC_RAW_PATH.exists():
            return TIC_RAW_PATH.read_text(encoding="utf-8")
        return None


def collect_portfolio_tic(iso3_list: list) -> pd.DataFrame:
    """
    Collect the U.S. Treasury TIC Table 2 workaround feed.

    Table 2 reports foreign long-term securities held by U.S. residents.
    We normalize the monthly holdings columns into the same portfolio matrix
    contract used by IMF PIP, but keep the source-specific instrument classes.
    """
    print("\n" + "=" * 60)
    print("Collecting U.S. TIC Table 2 supplement ...")
    print("=" * 60)

    text = _load_tic_text()
    if not text:
        print("  U.S. TIC supplement: unavailable (no live fetch and no cached raw file)")
        return pd.DataFrame()

    lines = text.splitlines()
    header_idx = next(
        (idx for idx, line in enumerate(lines) if line.startswith("country\tcountry_code\tdate\t")),
        None,
    )
    if header_idx is None:
        print("  U.S. TIC supplement: header not found in raw text")
        return pd.DataFrame()

    df = pd.read_csv(io.StringIO("\n".join(lines[header_idx:])), sep="\t")
    if df.empty:
        print("  U.S. TIC supplement: parsed file is empty")
        return pd.DataFrame()

    df = df[df["date"].astype(str).str.fullmatch(r"\d{4}-\d{2}")].copy()
    df = df[df["country"].isin(TIC_COUNTRY_TO_ISO3)].copy()
    df["counterpart_iso3"] = df["country"].map(TIC_COUNTRY_TO_ISO3)
    df = df[df["counterpart_iso3"].isin(iso3_list)].copy()
    if df.empty:
        print("  U.S. TIC supplement: no tracked countries present in parsed file")
        return pd.DataFrame()

    df["reporter_iso3"] = "USA"
    df["date"] = pd.to_datetime(df["date"] + "-01", errors="coerce")
    df = df.dropna(subset=["date"])

    for column in TIC_INSTRUMENT_MAP:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    frames = []
    for column, instrument_type in TIC_INSTRUMENT_MAP.items():
        subset = (
            df[["date", "reporter_iso3", "counterpart_iso3", column]]
            .dropna(subset=[column])
            .rename(columns={column: "amount_millions_usd"})
        )
        if subset.empty:
            continue

        subset["instrument_type"] = instrument_type
        subset["amount_usd"] = subset["amount_millions_usd"] * 1_000_000.0
        subset["source"] = "us_tic"
        subset["frequency"] = "monthly"
        subset["is_official_sector"] = False
        frames.append(
            subset[
                [
                    "date",
                    "reporter_iso3",
                    "counterpart_iso3",
                    "instrument_type",
                    "amount_usd",
                    "source",
                    "frequency",
                    "is_official_sector",
                ]
            ]
        )

    if not frames:
        print("  U.S. TIC supplement: no TIC holdings columns populated for tracked countries")
        return pd.DataFrame()

    result = (
        pd.concat(frames, ignore_index=True)
        .groupby(
            [
                "date",
                "reporter_iso3",
                "counterpart_iso3",
                "instrument_type",
                "source",
                "frequency",
                "is_official_sector",
            ],
            as_index=False,
        )
        .agg({"amount_usd": "sum"})
        .sort_values(["date", "instrument_type", "counterpart_iso3"])
        .reset_index(drop=True)
    )

    reporter_totals = result.groupby(
        ["date", "reporter_iso3", "instrument_type", "source"]
    )["amount_usd"].transform("sum")
    result["share_of_reporter_portfolio_pct"] = np.where(
        reporter_totals > 0,
        result["amount_usd"] / reporter_totals * 100.0,
        np.nan,
    )
    result["share_of_counterpart_inbound_pct"] = np.nan

    latest_date = result["date"].max()
    latest = result[result["date"] == latest_date]
    print(
        f"\n  U.S. TIC supplement: {len(result):,} rows, "
        f"{latest['counterpart_iso3'].nunique()} tracked counterparts on latest date {latest_date.date()}"
    )
    return result


def normalize_portfolio_holdings(*frames: pd.DataFrame) -> pd.DataFrame:
    """Combine portfolio sources and compute normalized ownership shares."""
    non_empty = [frame for frame in frames if frame is not None and not frame.empty]
    if not non_empty:
        return pd.DataFrame(
            columns=[
                "date",
                "reporter_iso3",
                "counterpart_iso3",
                "instrument_type",
                "amount_usd",
                "share_of_reporter_portfolio_pct",
                "share_of_counterpart_inbound_pct",
                "source",
                "frequency",
                "is_official_sector",
            ]
        )

    df = pd.concat(non_empty, ignore_index=True)
    df = (
        df.sort_values(["date", "reporter_iso3", "counterpart_iso3", "instrument_type", "source"])
        .drop_duplicates(
            subset=["date", "reporter_iso3", "counterpart_iso3", "instrument_type", "source"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    # Recompute shares after combining sources so the saved matrix is internally consistent.
    reporter_totals = df.groupby(
        ["date", "reporter_iso3", "instrument_type", "source"]
    )["amount_usd"].transform("sum")
    df["share_of_reporter_portfolio_pct"] = np.where(
        reporter_totals > 0,
        df["amount_usd"] / reporter_totals * 100.0,
        np.nan,
    )

    inbound_totals = df.groupby(
        ["date", "counterpart_iso3", "instrument_type", "source"]
    )["amount_usd"].transform("sum")
    inbound_reporters = df.groupby(
        ["date", "counterpart_iso3", "instrument_type", "source"]
    )["reporter_iso3"].transform("nunique")
    df["share_of_counterpart_inbound_pct"] = np.where(
        (inbound_totals > 0) & (inbound_reporters > 1),
        df["amount_usd"] / inbound_totals * 100.0,
        np.nan,
    )
    return df


def main():
    parser = argparse.ArgumentParser(description="ASADO Bilateral Data Collector")
    parser.add_argument("--trade-only", action="store_true", help="Collect trade data only")
    parser.add_argument("--bank-only", action="store_true", help="Collect banking data only")
    parser.add_argument("--portfolio-only", action="store_true", help="Collect portfolio ownership data only")
    parser.add_argument("--skip-portfolio", action="store_true", help="Skip portfolio ownership collection")
    args = parser.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    iso3_list, iso3_to_t2, t2_to_iso3, iso3_to_bis = load_countries()
    print(f"Universe: {len(iso3_list)} unique ISO3 codes from 34 T2 countries\n")

    do_trade = not args.bank_only and not args.portfolio_only
    do_bank = not args.trade_only and not args.portfolio_only
    do_portfolio = not args.trade_only and not args.bank_only and not args.skip_portfolio

    if do_trade:
        trade_df = collect_trade(iso3_list, iso3_to_t2)
        if not trade_df.empty:
            trade_df.to_parquet(TRADE_PQ, index=False)
            print(f"  Saved: {TRADE_PQ}")
        else:
            print("  WARNING: No trade data to save")

    if do_bank:
        bank_df = collect_banking(iso3_list, iso3_to_bis)
        if not bank_df.empty:
            bank_df.to_parquet(BANK_PQ, index=False)
            print(f"  Saved: {BANK_PQ}")
        else:
            print("  WARNING: No banking data to save")

    if do_portfolio or args.portfolio_only:
        pip_df = collect_portfolio_cpis(iso3_list)
        tic_df = collect_portfolio_tic(iso3_list)
        portfolio_df = normalize_portfolio_holdings(pip_df, tic_df)
        if not portfolio_df.empty:
            portfolio_df.to_parquet(PORTFOLIO_PQ, index=False)
            print(f"  Saved: {PORTFOLIO_PQ}")
        else:
            print("  WARNING: No portfolio ownership data to save")

    print("\nDone.")


if __name__ == "__main__":
    main()
