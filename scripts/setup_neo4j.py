#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: setup_neo4j.py
=============================================================================

INPUT FILES:
- config/country_mapping.json                       (34-country code mapping)
- Data/processed/extended_factors_panel.parquet      (OFAC sanctions data)
- Data/processed/bilateral_trade_matrix.parquet      (IMF IMTS bilateral trade)
- Data/processed/bilateral_banking_matrix.parquet    (BIS LBS banking claims)
- Data/asado.duckdb                                 (for latest factor values)

OUTPUT FILES:
- Neo4j graph database (bolt://localhost:7687)

VERSION: 1.1
LAST UPDATED: 2026-04-12
AUTHOR: Arjun Divecha

DESCRIPTION:
Populates the Neo4j knowledge graph with entity nodes and relationship edges
for the ASADO country research platform. Creates Country, Factor, Commodity,
CentralBank, DataSource, SanctionsProgram, and CrisisEvent nodes, then
connects them with typed edges including bilateral trade and banking networks.

Node types:
  - Country (34)         — from country_mapping.json + enrichment data
  - Factor (~315)        — from T2 + external + extended + GDELT + IMF variables
  - Commodity (4)        — Oil, Copper, Gold, Agriculture
  - CentralBank (30)     — one per unique ISO3 country
  - DataSource (26)      — each data source in the pipeline
  - SanctionsProgram     — from OFAC data
  - CrisisEvent (9)      — major historical crises

Edge types:
  - HAS_CENTRAL_BANK, EXPORT_EXPOSED_TO, SUBJECT_TO,
    HAS_CRISIS_HISTORY, DATA_AVAILABLE_FROM, HAS_FACTOR_EXPOSURE,
    TRADES_WITH, HAS_BANKING_EXPOSURE_TO

DEPENDENCIES:
- neo4j, duckdb, pandas

USAGE:
  python scripts/setup_neo4j.py                # populate graph (clears first)
  python scripts/setup_neo4j.py --check        # verify existing graph

NOTES:
- Clears all existing nodes/edges on each run (idempotent rebuild)
- Neo4j must be running: brew services start neo4j
- Default credentials: neo4j / mythos2026
=============================================================================
"""

import argparse
import json
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd
from neo4j import GraphDatabase

BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "Data"
DB_PATH = DATA_DIR / "asado.duckdb"

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "mythos2026"

# ── Country enrichment data ───────────────────────────────────────────────

COUNTRY_META = {
    "AUS": {"region": "Asia-Pacific", "dm_em": "DM", "currency": "AUD", "cb_name": "Reserve Bank of Australia"},
    "BRA": {"region": "Latin America", "dm_em": "EM", "currency": "BRL", "cb_name": "Banco Central do Brasil"},
    "CAN": {"region": "North America", "dm_em": "DM", "currency": "CAD", "cb_name": "Bank of Canada"},
    "CHL": {"region": "Latin America", "dm_em": "EM", "currency": "CLP", "cb_name": "Banco Central de Chile"},
    "CHN": {"region": "Asia-Pacific", "dm_em": "EM", "currency": "CNY", "cb_name": "People's Bank of China"},
    "DNK": {"region": "Europe", "dm_em": "DM", "currency": "DKK", "cb_name": "Danmarks Nationalbank"},
    "FRA": {"region": "Europe", "dm_em": "DM", "currency": "EUR", "cb_name": "Banque de France"},
    "DEU": {"region": "Europe", "dm_em": "DM", "currency": "EUR", "cb_name": "Deutsche Bundesbank"},
    "HKG": {"region": "Asia-Pacific", "dm_em": "DM", "currency": "HKD", "cb_name": "Hong Kong Monetary Authority"},
    "IND": {"region": "Asia-Pacific", "dm_em": "EM", "currency": "INR", "cb_name": "Reserve Bank of India"},
    "IDN": {"region": "Asia-Pacific", "dm_em": "EM", "currency": "IDR", "cb_name": "Bank Indonesia"},
    "ITA": {"region": "Europe", "dm_em": "DM", "currency": "EUR", "cb_name": "Banca d'Italia"},
    "JPN": {"region": "Asia-Pacific", "dm_em": "DM", "currency": "JPY", "cb_name": "Bank of Japan"},
    "KOR": {"region": "Asia-Pacific", "dm_em": "EM", "currency": "KRW", "cb_name": "Bank of Korea"},
    "MYS": {"region": "Asia-Pacific", "dm_em": "EM", "currency": "MYR", "cb_name": "Bank Negara Malaysia"},
    "MEX": {"region": "Latin America", "dm_em": "EM", "currency": "MXN", "cb_name": "Banco de México"},
    "NLD": {"region": "Europe", "dm_em": "DM", "currency": "EUR", "cb_name": "De Nederlandsche Bank"},
    "PHL": {"region": "Asia-Pacific", "dm_em": "EM", "currency": "PHP", "cb_name": "Bangko Sentral ng Pilipinas"},
    "POL": {"region": "Europe", "dm_em": "EM", "currency": "PLN", "cb_name": "Narodowy Bank Polski"},
    "SAU": {"region": "Middle East", "dm_em": "EM", "currency": "SAR", "cb_name": "Saudi Central Bank"},
    "SGP": {"region": "Asia-Pacific", "dm_em": "DM", "currency": "SGD", "cb_name": "Monetary Authority of Singapore"},
    "ZAF": {"region": "Africa", "dm_em": "EM", "currency": "ZAR", "cb_name": "South African Reserve Bank"},
    "ESP": {"region": "Europe", "dm_em": "DM", "currency": "EUR", "cb_name": "Banco de España"},
    "SWE": {"region": "Europe", "dm_em": "DM", "currency": "SEK", "cb_name": "Sveriges Riksbank"},
    "CHE": {"region": "Europe", "dm_em": "DM", "currency": "CHF", "cb_name": "Swiss National Bank"},
    "TWN": {"region": "Asia-Pacific", "dm_em": "EM", "currency": "TWD", "cb_name": "Central Bank of the Republic of China"},
    "THA": {"region": "Asia-Pacific", "dm_em": "EM", "currency": "THB", "cb_name": "Bank of Thailand"},
    "TUR": {"region": "Europe", "dm_em": "EM", "currency": "TRY", "cb_name": "Central Bank of the Republic of Türkiye"},
    "GBR": {"region": "Europe", "dm_em": "DM", "currency": "GBP", "cb_name": "Bank of England"},
    "USA": {"region": "North America", "dm_em": "DM", "currency": "USD", "cb_name": "Federal Reserve"},
    "VNM": {"region": "Asia-Pacific", "dm_em": "EM", "currency": "VND", "cb_name": "State Bank of Vietnam"},
}

# ── Factor categories ─────────────────────────────────────────────────────

FACTOR_CATEGORIES = {
    "momentum": ["1MRet", "3MRet", "6MRet", "9MRet", "12MRet", "1MTR", "3MTR", "6MTR",
                  "12MTR", "12-1MTR", "120MA Signal", "120MA", "RSI14", "P2P",
                  "Advance Decline", "Tot Return Index ", "PX_LAST"],
    "valuation": ["Best PE ", "Positive PE ", "Trailing PE", "Best PBK", "Best Price Sales",
                   "EV to EBITDA", "Earnings Yield", "Shiller PE", "Best Div Yield",
                   "Debt to EV"],
    "quality": ["Best ROE", "Operating Margin", "Best Cash Flow", "Best EPS",
                "BEST EPS", "LT Growth", "Trailing EPS", "Trailing EPS 36"],
    "macro": ["GDP", "Inflation", "Budget Def", "Current Account", "Debt to GDP",
              "Bloom Country Risk"],
    "technical": ["20 Day Vol", "360 Day Vol", "Currency Vol", "10Yr Bond",
                  "10Yr Bond 12", "REER"],
    "commodity": ["Oil", "Oil 12", "Copper", "Copper 12", "Gold", "Gold 12",
                  "Agriculture", "Agriculture 12"],
    "size": ["MCAP", "MCAP Adj", "Mcap Weights"],
    "currency": ["Currency", "Currency 12"],
}

# ── Data sources catalog ──────────────────────────────────────────────────

DATA_SOURCES = [
    {"name": "EPU", "url": "policyuncertainty.com", "frequency": "monthly", "api_type": "download", "status": "active"},
    {"name": "GPR", "url": "matteoiacoviello.com", "frequency": "monthly", "api_type": "download", "status": "active"},
    {"name": "BIS Credit Gap", "url": "stats.bis.org", "frequency": "quarterly", "api_type": "sdmx", "status": "active"},
    {"name": "BIS Property", "url": "stats.bis.org", "frequency": "quarterly", "api_type": "sdmx", "status": "active"},
    {"name": "OECD CLI", "url": "sdmx.oecd.org", "frequency": "monthly", "api_type": "sdmx", "status": "active"},
    {"name": "World Bank", "url": "api.worldbank.org", "frequency": "annual", "api_type": "rest", "status": "active"},
    {"name": "BIS REER", "url": "stats.bis.org", "frequency": "monthly", "api_type": "sdmx", "status": "active"},
    {"name": "BIS Policy Rates", "url": "stats.bis.org", "frequency": "daily", "api_type": "sdmx", "status": "active"},
    {"name": "BIS Debt Service", "url": "stats.bis.org", "frequency": "quarterly", "api_type": "sdmx", "status": "active"},
    {"name": "OECD BCI", "url": "sdmx.oecd.org", "frequency": "monthly", "api_type": "rest", "status": "active"},
    {"name": "OECD CCI", "url": "sdmx.oecd.org", "frequency": "monthly", "api_type": "rest", "status": "active"},
    {"name": "ECB FX", "url": "data-api.ecb.europa.eu", "frequency": "monthly", "api_type": "sdmx", "status": "active"},
    {"name": "ND-GAIN", "url": "gain.nd.edu", "frequency": "annual", "api_type": "download", "status": "active"},
    {"name": "ILOSTAT", "url": "sdmx.ilo.org", "frequency": "annual", "api_type": "sdmx", "status": "active"},
    {"name": "UNDP HDI", "url": "hdr.undp.org", "frequency": "annual", "api_type": "download", "status": "active"},
    {"name": "OFAC", "url": "treasury.gov", "frequency": "event-driven", "api_type": "download", "status": "active"},
    {"name": "FAOSTAT", "url": "fao.org", "frequency": "annual", "api_type": "download", "status": "active"},
    {"name": "FRED", "url": "fred.stlouisfed.org", "frequency": "monthly", "api_type": "rest", "status": "active"},
    {"name": "EIA", "url": "api.eia.gov", "frequency": "annual", "api_type": "rest", "status": "active"},
    {"name": "IMF CPI", "url": "api.imf.org", "frequency": "monthly", "api_type": "sdmx3", "status": "active"},
    {"name": "IMF WEO", "url": "api.imf.org", "frequency": "annual", "api_type": "sdmx3", "status": "active"},
    {"name": "IMF BOP", "url": "api.imf.org", "frequency": "annual", "api_type": "sdmx3", "status": "active"},
    {"name": "IMF MFS_IR", "url": "api.imf.org", "frequency": "monthly", "api_type": "sdmx3", "status": "active"},
    {"name": "IMF ER", "url": "api.imf.org", "frequency": "monthly", "api_type": "sdmx3", "status": "active"},
    {"name": "IMF LS", "url": "api.imf.org", "frequency": "monthly", "api_type": "sdmx3", "status": "active"},
    {"name": "IMF ITG", "url": "api.imf.org", "frequency": "monthly", "api_type": "sdmx3", "status": "active"},
    {"name": "Bloomberg Bonds", "url": "bloomberg.com", "frequency": "monthly", "api_type": "blpapi", "status": "active"},
    {"name": "Bloomberg CDS", "url": "bloomberg.com", "frequency": "monthly", "api_type": "blpapi", "status": "active"},
    {"name": "Bloomberg Breakevens", "url": "bloomberg.com", "frequency": "monthly", "api_type": "blpapi", "status": "active"},
    {"name": "Bloomberg Ratings", "url": "bloomberg.com", "frequency": "snapshot", "api_type": "blpapi", "status": "active"},
]

# ── Crisis events ─────────────────────────────────────────────────────────

CRISIS_EVENTS = [
    {"name": "Asian Financial Crisis", "start": "1997-07-01", "end": "1998-12-01", "type": "financial",
     "countries": ["THA", "IDN", "KOR", "MYS", "PHL", "HKG", "SGP", "TWN"]},
    {"name": "Russian/LTCM Crisis", "start": "1998-08-01", "end": "1999-03-01", "type": "financial",
     "countries": ["BRA", "USA", "GBR", "DEU", "JPN"]},
    {"name": "Dot-com Bust", "start": "2000-03-01", "end": "2002-10-01", "type": "equity",
     "countries": ["USA", "GBR", "DEU", "JPN", "FRA", "SWE", "KOR", "TWN"]},
    {"name": "Global Financial Crisis", "start": "2007-07-01", "end": "2009-03-01", "type": "financial",
     "countries": ["USA", "GBR", "DEU", "FRA", "ESP", "ITA", "NLD", "CHE", "JPN", "KOR",
                   "AUS", "CAN", "BRA", "MEX", "IND", "CHN", "IDN", "SGP", "HKG"]},
    {"name": "European Debt Crisis", "start": "2010-04-01", "end": "2012-07-01", "type": "sovereign",
     "countries": ["ESP", "ITA", "FRA", "DEU", "GBR", "NLD", "POL", "TUR"]},
    {"name": "Taper Tantrum", "start": "2013-05-01", "end": "2013-09-01", "type": "rates",
     "countries": ["BRA", "IND", "IDN", "TUR", "ZAF", "MEX", "THA", "MYS", "PHL"]},
    {"name": "China Devaluation", "start": "2015-08-01", "end": "2016-02-01", "type": "fx",
     "countries": ["CHN", "HKG", "KOR", "TWN", "BRA", "AUS", "SGP", "MYS", "THA", "IDN"]},
    {"name": "COVID-19 Crash", "start": "2020-02-01", "end": "2020-04-01", "type": "pandemic",
     "countries": list(COUNTRY_META.keys())},
    {"name": "Ukraine/Inflation Shock", "start": "2022-02-01", "end": "2022-10-01", "type": "geopolitical",
     "countries": ["POL", "DEU", "FRA", "ITA", "ESP", "GBR", "NLD", "SWE", "DNK", "CHE",
                   "TUR", "IND", "BRA", "ZAF"]},
]

# ── Commodity reference ───────────────────────────────────────────────────

COMMODITIES = [
    {"name": "Oil", "category": "energy"},
    {"name": "Copper", "category": "industrial_metals"},
    {"name": "Gold", "category": "precious_metals"},
    {"name": "Agriculture", "category": "agricultural"},
]

COMMODITY_EXPORTERS = {
    "Oil": ["SAU", "CAN", "BRA", "MEX", "IDN", "MYS", "VNM", "GBR"],
    "Copper": ["CHL", "AUS", "MEX", "BRA", "ZAF", "POL"],
    "Gold": ["AUS", "ZAF", "CAN", "BRA", "MEX", "CHN"],
    "Agriculture": ["BRA", "AUS", "THA", "IDN", "IND", "VNM", "CAN", "USA"],
}

# ── Source coverage (which sources cover which ISO3 codes) ────────────────

SOURCE_COVERAGE = {
    "EPU": ["AUS", "BRA", "CAN", "CHL", "CHN", "FRA", "DEU", "HKG", "IND", "ITA",
            "JPN", "KOR", "MEX", "NLD", "SGP", "ESP", "SWE", "GBR", "USA"],
    "GPR": ["AUS", "BRA", "CAN", "CHN", "FRA", "DEU", "IND", "ITA", "JPN", "KOR",
            "MEX", "PHL", "SAU", "ESP", "SWE", "TUR", "TWN", "GBR", "USA"],
    "BIS Credit Gap": list(set(COUNTRY_META.keys()) - {"PHL", "VNM", "SAU"}),
    "BIS Property": list(set(COUNTRY_META.keys()) - {"PHL", "VNM", "SAU"}),
    "OECD CLI": ["AUS", "BRA", "CAN", "CHE", "CHL", "CHN", "DEU", "DNK", "ESP", "FRA",
                 "GBR", "IDN", "IND", "ITA", "JPN", "KOR", "MEX", "NLD", "POL", "SAU",
                 "SWE", "TUR", "USA", "ZAF"],
    "World Bank": list(set(COUNTRY_META.keys()) - {"TWN"}),
    "BIS REER": list(set(COUNTRY_META.keys()) - {"VNM"}),
    "BIS Policy Rates": list(set(COUNTRY_META.keys()) - {"HKG", "SGP", "TWN", "VNM",
                                                          "PHL", "SAU", "NLD", "ESP"}),
    "BIS Debt Service": list(set(COUNTRY_META.keys()) - {"VNM", "PHL", "SAU", "HKG",
                                                          "SGP", "MYS"}),
    "OECD BCI": ["AUS", "BRA", "CAN", "CHE", "CHL", "DEU", "DNK", "ESP", "FRA", "GBR",
                 "ITA", "JPN", "KOR", "MEX", "NLD", "POL", "SWE", "TUR", "USA", "ZAF"],
    "OECD CCI": ["AUS", "BRA", "CAN", "CHE", "CHL", "DEU", "DNK", "ESP", "FRA", "GBR",
                 "IDN", "ITA", "JPN", "KOR", "MEX", "NLD", "POL", "SWE", "TUR", "USA",
                 "ZAF"],
    "ECB FX": list(set(COUNTRY_META.keys()) - {"SAU", "VNM"}),
    "ND-GAIN": list(set(COUNTRY_META.keys()) - {"HKG", "TWN"}),
    "ILOSTAT": list(COUNTRY_META.keys()),
    "UNDP HDI": list(set(COUNTRY_META.keys()) - {"TWN"}),
    "OFAC": list(COUNTRY_META.keys()),
    "FAOSTAT": list(set(COUNTRY_META.keys()) - {"TWN"}),
    "FRED": list(COUNTRY_META.keys()),
    "EIA": list(COUNTRY_META.keys()),
    "IMF CPI": ["AUS", "BRA", "CAN", "CHE", "CHL", "CHN", "DEU", "DNK", "ESP", "FRA", "GBR",
                 "HKG", "IDN", "IND", "ITA", "JPN", "KOR", "MEX", "MYS", "NLD", "PHL", "POL",
                 "SAU", "SGP", "SWE", "THA", "TUR", "USA", "VNM", "ZAF"],
    "IMF WEO": ["AUS", "BRA", "CAN", "CHE", "CHL", "CHN", "DEU", "DNK", "ESP", "FRA", "GBR",
                 "HKG", "IDN", "IND", "ITA", "JPN", "KOR", "MEX", "MYS", "NLD", "PHL", "POL",
                 "SAU", "SGP", "SWE", "THA", "TUR", "TWN", "USA", "VNM", "ZAF"],
    "IMF BOP": ["AUS", "BRA", "CAN", "CHE", "CHL", "CHN", "DEU", "DNK", "ESP", "FRA", "GBR",
                 "HKG", "IDN", "IND", "ITA", "JPN", "KOR", "MEX", "MYS", "NLD", "PHL", "POL",
                 "SAU", "SGP", "SWE", "THA", "TUR", "TWN", "USA", "VNM", "ZAF"],
    "IMF MFS_IR": ["AUS", "BRA", "CAN", "CHL", "DEU", "DNK", "ESP", "FRA", "HKG", "IDN",
                    "ITA", "JPN", "KOR", "MEX", "MYS", "NLD", "PHL", "POL", "SWE", "THA",
                    "TUR", "USA", "ZAF"],
    "IMF ER": ["AUS", "BRA", "CAN", "CHE", "CHL", "CHN", "DNK", "GBR", "HKG", "IDN", "IND",
                "JPN", "KOR", "MEX", "MYS", "PHL", "POL", "SAU", "SGP", "SWE", "THA", "TUR",
                "TWN", "USA", "VNM", "ZAF"],
    "IMF LS": ["AUS", "CAN", "DEU", "HKG", "JPN", "KOR", "MYS", "SWE", "THA", "USA"],
    "IMF ITG": ["AUS", "BRA", "CAN", "CHE", "CHL", "CHN", "DEU", "DNK", "ESP", "FRA", "GBR",
                 "HKG", "IDN", "IND", "ITA", "JPN", "KOR", "MEX", "MYS", "NLD", "PHL", "POL",
                 "SAU", "SGP", "SWE", "THA", "TUR", "TWN", "USA", "VNM", "ZAF"],
}


def clear_graph(session):
    """Delete all nodes and edges."""
    session.run("MATCH (n) DETACH DELETE n")
    print("  Cleared existing graph")


def create_constraints(session):
    """Create uniqueness constraints for key node types."""
    existing = [dict(r) for r in session.run("SHOW CONSTRAINTS")]
    for row in existing:
        cname = row["name"]
        session.run(f"DROP CONSTRAINT `{cname}` IF EXISTS")

    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Country) REQUIRE c.t2_name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (f:Factor) REQUIRE f.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (com:Commodity) REQUIRE com.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (cb:CentralBank) REQUIRE cb.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (ds:DataSource) REQUIRE ds.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (sp:SanctionsProgram) REQUIRE sp.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (ce:CrisisEvent) REQUIRE ce.name IS UNIQUE",
    ]
    for c in constraints:
        session.run(c)
    print("  Constraints created")


def create_country_nodes(session):
    """Create Country nodes from country_mapping.json."""
    mapping_path = CONFIG_DIR / "country_mapping.json"
    with open(mapping_path) as f:
        mapping = json.load(f)

    count = 0
    for t2_name, codes in mapping["countries"].items():
        iso3 = codes["iso3"]
        iso2 = codes["iso2"]
        meta = COUNTRY_META.get(iso3, {})

        session.run("""
            MERGE (c:Country {t2_name: $t2_name})
            SET c.iso3 = $iso3,
                c.iso2 = $iso2,
                c.name = $t2_name,
                c.dm_em = $dm_em,
                c.region = $region,
                c.currency_code = $currency
        """, t2_name=t2_name, iso3=iso3, iso2=iso2,
            dm_em=meta.get("dm_em", ""),
            region=meta.get("region", ""),
            currency=meta.get("currency", ""))
        count += 1

    print(f"  Country nodes: {count}")
    return count


def _categorize_factor(name: str) -> str:
    """Determine category for a factor variable name."""
    base = name.replace("_CS", "").replace("_TS", "").strip()

    for cat, patterns in FACTOR_CATEGORIES.items():
        for p in patterns:
            if base.startswith(p):
                return cat

    if name.startswith("WB_"):
        if any(k in name for k in ["Governance", "Corruption", "Rule_of_Law",
                                    "Political", "Regulatory", "Voice"]):
            return "governance"
        if any(k in name for k in ["GDP", "Inflation", "Debt", "Credit",
                                    "Current_Account", "FDI", "Unemployment"]):
            return "macro"
        if any(k in name for k in ["Population", "Labor", "Female", "OldAge"]):
            return "demographics"
        if any(k in name for k in ["Reserve", "Import_Cover", "External_Debt"]):
            return "reserves"
        if any(k in name for k in ["CO2", "Renewable", "Climate"]):
            return "climate"
        return "macro"

    if name.startswith("BIS_"):
        return "macro"
    if name.startswith("OECD_"):
        return "macro"
    if name.startswith("ECB_FX"):
        return "currency"
    if name.startswith("NDGAIN"):
        return "climate"
    if name.startswith("ILO_"):
        return "labor"
    if name.startswith("UNDP_"):
        return "development"
    if name.startswith("OFAC_"):
        return "sanctions"
    if name.startswith("FAO_"):
        return "trade"
    if name.startswith("FRED_"):
        return "macro"
    if name.startswith("EIA_"):
        return "energy"
    if name.startswith("IMF_"):
        if any(k in name for k in ["CPI", "Inflation"]):
            return "macro"
        if any(k in name for k in ["WEO", "GDP", "Debt", "CA_GDP", "Unemployment", "Population"]):
            return "macro"
        if any(k in name for k in ["BOP", "Current_Account", "Financial", "Direct_Investment",
                                    "Portfolio_Investment", "Goods_Services"]):
            return "macro"
        if any(k in name for k in ["Rate", "Discount", "Bond", "TBill", "Money_Market"]):
            return "rates"
        if "XRate" in name or "Exchange" in name:
            return "currency"
        if "Employment" in name:
            return "labor"
        if any(k in name for k in ["Export", "Import", "Trade"]):
            return "trade"
        return "macro"
    if name.startswith("GDELT_"):
        return "sentiment"
    if name.startswith("EPU"):
        return "uncertainty"
    if name.startswith("GPR") or name.startswith("Global_GPR"):
        return "geopolitical"
    if name.startswith("BBG_"):
        if "Bond" in name or "Yield_Curve" in name:
            return "rates"
        if "CDS" in name or "MIPD" in name:
            return "sovereign_risk"
        if "Breakeven" in name:
            return "inflation"
        if "Rating" in name:
            return "sovereign_risk"
        if "OIS" in name or "ZSpread" in name:
            return "rates"
        if "WIRP" in name:
            return "monetary_policy"
        if "ECFC" in name:
            return "macro_forecast"
        if "Debt" in name:
            return "fiscal"
        if "PMI" in name:
            return "activity"
        if "M2" in name:
            return "monetary_policy"
        return "rates"

    return "other"


def _factor_source(name: str) -> str:
    """Determine the data source for a factor variable."""
    if name.startswith("GDELT_"):
        return "gdelt"
    if name.startswith("WB_"):
        return "worldbank"
    if name.startswith("BIS_"):
        return "bis"
    if name.startswith("OECD_"):
        return "oecd"
    if name.startswith("ECB_"):
        return "ecb"
    if name.startswith("NDGAIN"):
        return "ndgain"
    if name.startswith("ILO_"):
        return "ilostat"
    if name.startswith("UNDP_"):
        return "undp"
    if name.startswith("OFAC_"):
        return "ofac"
    if name.startswith("FAO_"):
        return "faostat"
    if name.startswith("FRED_"):
        return "fred"
    if name.startswith("EIA_"):
        return "eia"
    if name.startswith("IMF_"):
        return "imf"
    if name.startswith("EPU"):
        return "epu"
    if name.startswith("GPR") or name.startswith("Global_GPR"):
        return "gpr"
    if name.startswith("BBG_"):
        return "bloomberg"
    return "t2"


def create_factor_nodes(session):
    """Create Factor nodes from DuckDB variable list."""
    con = duckdb.connect(str(DB_PATH), read_only=True)
    variables = con.execute(
        "SELECT DISTINCT variable FROM unified_panel ORDER BY variable"
    ).fetchall()
    con.close()

    count = 0
    for (var_name,) in variables:
        category = _categorize_factor(var_name)
        source = _factor_source(var_name)
        session.run("""
            MERGE (f:Factor {name: $name})
            SET f.category = $category,
                f.source = $source
        """, name=var_name, category=category, source=source)
        count += 1

    print(f"  Factor nodes: {count}")
    return count


def create_commodity_nodes(session):
    """Create Commodity nodes."""
    for com in COMMODITIES:
        session.run("""
            MERGE (c:Commodity {name: $name})
            SET c.category = $category
        """, name=com["name"], category=com["category"])
    print(f"  Commodity nodes: {len(COMMODITIES)}")


def create_central_bank_nodes(session):
    """Create CentralBank nodes (one per unique ISO3)."""
    count = 0
    for iso3, meta in COUNTRY_META.items():
        cb_name = meta.get("cb_name")
        if cb_name:
            session.run("""
                MERGE (cb:CentralBank {name: $name})
                SET cb.country_iso3 = $iso3
            """, name=cb_name, iso3=iso3)
            count += 1
    print(f"  CentralBank nodes: {count}")


def create_datasource_nodes(session):
    """Create DataSource nodes."""
    for ds in DATA_SOURCES:
        session.run("""
            MERGE (d:DataSource {name: $name})
            SET d.url = $url,
                d.frequency = $frequency,
                d.api_type = $api_type,
                d.status = $status
        """, **ds)
    print(f"  DataSource nodes: {len(DATA_SOURCES)}")


def create_sanctions_nodes(session):
    """Create SanctionsProgram nodes from OFAC data."""
    programs = [
        {"name": "Iran Sanctions", "active": True},
        {"name": "Russia/Ukraine Sanctions", "active": True},
        {"name": "North Korea Sanctions", "active": True},
        {"name": "Cuba Sanctions", "active": True},
        {"name": "Syria Sanctions", "active": True},
        {"name": "Venezuela Sanctions", "active": True},
    ]
    for sp in programs:
        session.run("""
            MERGE (s:SanctionsProgram {name: $name})
            SET s.active = $active
        """, **sp)
    print(f"  SanctionsProgram nodes: {len(programs)}")


def create_crisis_nodes(session):
    """Create CrisisEvent nodes."""
    for ce in CRISIS_EVENTS:
        session.run("""
            MERGE (c:CrisisEvent {name: $name})
            SET c.start_date = date($start),
                c.end_date = date($end),
                c.type = $type
        """, name=ce["name"], start=ce["start"], end=ce["end"], type=ce["type"])
    print(f"  CrisisEvent nodes: {len(CRISIS_EVENTS)}")


def create_central_bank_edges(session):
    """Link Country -> CentralBank (all T2 names sharing an iso3 get the edge)."""
    count = 0
    for iso3, meta in COUNTRY_META.items():
        cb_name = meta.get("cb_name")
        if cb_name:
            result = session.run("""
                MATCH (c:Country WHERE c.iso3 = $iso3)
                MATCH (cb:CentralBank {name: $cb_name})
                MERGE (c)-[:HAS_CENTRAL_BANK]->(cb)
                RETURN COUNT(*) AS cnt
            """, iso3=iso3, cb_name=cb_name)
            count += result.single()["cnt"]
    print(f"  HAS_CENTRAL_BANK edges: {count}")


def create_commodity_edges(session):
    """Link Country -> Commodity (exporters, all T2 names per iso3)."""
    count = 0
    for commodity, exporters in COMMODITY_EXPORTERS.items():
        for iso3 in exporters:
            result = session.run("""
                MATCH (c:Country WHERE c.iso3 = $iso3)
                MATCH (com:Commodity {name: $commodity})
                MERGE (c)-[:EXPORT_EXPOSED_TO]->(com)
                RETURN COUNT(*) AS cnt
            """, iso3=iso3, commodity=commodity)
            count += result.single()["cnt"]
    print(f"  EXPORT_EXPOSED_TO edges: {count}")


def create_sanctions_edges(session):
    """Link sanctioned countries to SanctionsProgram nodes using OFAC data."""
    try:
        pq_path = DATA_DIR / "processed" / "extended_factors_panel.parquet"
        df = pd.read_parquet(pq_path)
        sanctioned = df[
            (df["variable"] == "OFAC_Sanctioned") & (df["value"] == 1.0)
        ]["country"].unique()

        mapping_path = CONFIG_DIR / "country_mapping.json"
        with open(mapping_path) as f:
            mapping = json.load(f)

        t2_to_iso3 = {name: codes["iso3"]
                      for name, codes in mapping["countries"].items()}

        count = 0
        for t2_name in sanctioned:
            result = session.run("""
                MATCH (c:Country {t2_name: $t2_name})
                MATCH (s:SanctionsProgram)
                WHERE s.active = true
                WITH c, collect(s)[0] AS sp
                WHERE sp IS NOT NULL
                MERGE (c)-[:SUBJECT_TO]->(sp)
                RETURN COUNT(*) AS cnt
            """, t2_name=t2_name)
            count += result.single()["cnt"]
        print(f"  SUBJECT_TO edges: {count}")
    except Exception as e:
        print(f"  SUBJECT_TO edges: SKIPPED ({e})")


def create_crisis_edges(session):
    """Link Country -> CrisisEvent (all T2 names per iso3)."""
    count = 0
    for ce in CRISIS_EVENTS:
        for iso3 in ce["countries"]:
            result = session.run("""
                MATCH (c:Country WHERE c.iso3 = $iso3)
                MATCH (ce:CrisisEvent {name: $name})
                MERGE (c)-[:HAS_CRISIS_HISTORY]->(ce)
                RETURN COUNT(*) AS cnt
            """, iso3=iso3, name=ce["name"])
            count += result.single()["cnt"]
    print(f"  HAS_CRISIS_HISTORY edges: {count}")


def create_datasource_edges(session):
    """Link Country -> DataSource (coverage)."""
    mapping_path = CONFIG_DIR / "country_mapping.json"
    with open(mapping_path) as f:
        mapping = json.load(f)

    iso3_set = set()
    for codes in mapping["countries"].values():
        iso3_set.add(codes["iso3"])

    count = 0
    for ds_name, iso3_list in SOURCE_COVERAGE.items():
        for iso3 in iso3_list:
            if iso3 in iso3_set:
                result = session.run("""
                    MATCH (c:Country WHERE c.iso3 = $iso3)
                    MATCH (ds:DataSource {name: $ds_name})
                    MERGE (c)-[:DATA_AVAILABLE_FROM]->(ds)
                    RETURN COUNT(*) AS cnt
                """, iso3=iso3, ds_name=ds_name)
                count += result.single()["cnt"]
    print(f"  DATA_AVAILABLE_FROM edges: {count}")


def create_factor_exposure_edges(session):
    """Link Country -> Factor with latest values from DuckDB."""
    con = duckdb.connect(str(DB_PATH), read_only=True)

    latest_date = con.execute(
        "SELECT MAX(date) FROM unified_panel WHERE variable = '1MRet'"
    ).fetchone()[0]

    latest = con.execute("""
        SELECT country, variable, value
        FROM unified_panel
        WHERE date = ?
        AND value IS NOT NULL
    """, [latest_date]).fetchdf()
    con.close()

    count = 0
    batch_size = 500
    rows = latest.to_dict("records")

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        session.run("""
            UNWIND $batch AS row
            MATCH (c:Country {t2_name: row.country})
            MATCH (f:Factor {name: row.variable})
            MERGE (c)-[r:HAS_FACTOR_EXPOSURE]->(f)
            SET r.value = row.value, r.date = date($date)
        """, batch=batch, date=str(latest_date))
        count += len(batch)

    print(f"  HAS_FACTOR_EXPOSURE edges: {count} (as of {latest_date})")


def create_trade_edges(session):
    """
    Create TRADES_WITH edges from bilateral trade matrix.

    Reads Data/processed/bilateral_trade_matrix.parquet (produced by
    collect_bilateral.py) and creates directed edges between Country nodes.
    Only keeps edges where total_trade_usd > $100M to avoid noise.
    """
    pq_path = DATA_DIR / "processed" / "bilateral_trade_matrix.parquet"
    if not pq_path.exists():
        print("  TRADES_WITH edges: SKIPPED (bilateral_trade_matrix.parquet not found)")
        return

    df = pd.read_parquet(pq_path)
    if df.empty:
        print("  TRADES_WITH edges: 0 (empty parquet)")
        return

    df = df[df["total_trade_usd"] > 100_000_000].copy()

    year = int(df["year"].iloc[0]) if "year" in df.columns else 0
    records = df.to_dict("records")

    batch_size = 200
    count = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        result = session.run("""
            UNWIND $batch AS row
            MATCH (r:Country WHERE r.iso3 = row.reporter_iso3)
            MATCH (cp:Country WHERE cp.iso3 = row.counterpart_iso3)
            MERGE (r)-[e:TRADES_WITH]->(cp)
            SET e.exports_usd = row.exports_usd,
                e.imports_usd = row.imports_usd,
                e.total_trade_usd = row.total_trade_usd,
                e.trade_share_pct = coalesce(row.trade_share_pct, 0.0),
                e.year = $year
            RETURN COUNT(e) AS cnt
        """, batch=batch, year=year)
        count += result.single()["cnt"]

    print(f"  TRADES_WITH edges: {count} (year={year}, threshold=$100M)")


def create_banking_edges(session):
    """
    Create HAS_BANKING_EXPOSURE_TO edges from bilateral banking matrix.

    Reads Data/processed/bilateral_banking_matrix.parquet (produced by
    collect_bilateral.py) and creates directed edges between Country nodes.
    """
    pq_path = DATA_DIR / "processed" / "bilateral_banking_matrix.parquet"
    if not pq_path.exists():
        print("  HAS_BANKING_EXPOSURE_TO edges: SKIPPED (bilateral_banking_matrix.parquet not found)")
        return

    df = pd.read_parquet(pq_path)
    if df.empty:
        print("  HAS_BANKING_EXPOSURE_TO edges: 0 (empty parquet)")
        return

    quarter = str(df["quarter"].iloc[0]) if "quarter" in df.columns else ""
    records = df.to_dict("records")

    batch_size = 200
    count = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        result = session.run("""
            UNWIND $batch AS row
            MATCH (r:Country WHERE r.iso3 = row.reporter_iso3)
            MATCH (cp:Country WHERE cp.iso3 = row.counterpart_iso3)
            MERGE (r)-[e:HAS_BANKING_EXPOSURE_TO]->(cp)
            SET e.claims_usd_millions = row.claims_usd_millions,
                e.share_of_total_claims_pct = coalesce(row.share_of_total_claims_pct, 0.0),
                e.quarter = $quarter
            RETURN COUNT(e) AS cnt
        """, batch=batch, quarter=quarter)
        count += result.single()["cnt"]

    print(f"  HAS_BANKING_EXPOSURE_TO edges: {count} (quarter={quarter})")


def check_graph():
    """Print summary of existing graph."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    with driver.session() as session:
        labels = session.run(
            "CALL db.labels() YIELD label RETURN label ORDER BY label"
        ).values()
        print("Node labels:")
        for (label,) in labels:
            count = session.run(
                f"MATCH (n:{label}) RETURN COUNT(n)"
            ).single()[0]
            print(f"  {label}: {count}")

        print("\nRelationship types:")
        rel_types = session.run(
            "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
        ).values()
        for (rt,) in rel_types:
            count = session.run(
                f"MATCH ()-[r:{rt}]->() RETURN COUNT(r)"
            ).single()[0]
            print(f"  {rt}: {count}")

    driver.close()


def main():
    parser = argparse.ArgumentParser(description="ASADO Neo4j Setup")
    parser.add_argument("--check", action="store_true", help="Check existing graph")
    args = parser.parse_args()

    if args.check:
        check_graph()
        return

    if not DB_PATH.exists():
        print(f"DuckDB not found at {DB_PATH} — run setup_duckdb.py first")
        sys.exit(1)

    start = time.time()
    print("=" * 60)
    print("ASADO Neo4j Knowledge Graph Setup")
    print("=" * 60)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    driver.verify_connectivity()
    print("Connected to Neo4j")
    print()

    with driver.session() as session:
        print("Clearing graph ...")
        clear_graph(session)
        print()

        print("Creating constraints ...")
        create_constraints(session)
        print()

        print("Creating nodes ...")
        create_country_nodes(session)
        create_factor_nodes(session)
        create_commodity_nodes(session)
        create_central_bank_nodes(session)
        create_datasource_nodes(session)
        create_sanctions_nodes(session)
        create_crisis_nodes(session)
        print()

        print("Creating edges ...")
        create_central_bank_edges(session)
        create_commodity_edges(session)
        create_sanctions_edges(session)
        create_crisis_edges(session)
        create_datasource_edges(session)
        create_factor_exposure_edges(session)
        create_trade_edges(session)
        create_banking_edges(session)

    driver.close()
    elapsed = time.time() - start

    print()
    print("=" * 60)
    print(f"Graph populated in {elapsed:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
