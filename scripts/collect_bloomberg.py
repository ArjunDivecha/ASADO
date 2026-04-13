#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: collect_bloomberg.py
=============================================================================

INPUT FILES:
- config/country_mapping.json: Maps 34 T2 countries to source-specific codes

OUTPUT FILES:
- Data/processed/bloomberg_factors_panel.parquet  (primary — tidy panel)
- Data/processed/bloomberg_factors_panel.csv      (secondary — CSV copy)
- Data/processed/bloomberg_variable_catalog.csv   (metadata per variable)

VERSION: 1.0
LAST UPDATED: 2026-04-12
AUTHOR: Arjun Divecha

DESCRIPTION:
Downloads country-level sovereign data from Bloomberg via the OpusBloomberg
BLPAPI connection (macOS → Parallels → bbcomm → Bloomberg Terminal), aligns
to the 34-country T2 Master universe, and outputs a tidy panel matching the
same schema as all other ASADO collector scripts.

Bloomberg connection uses the OpusBloomberg pathway:
  macOS Python ──TCP:8194──> Windows 11 VM (Parallels, IP auto-detected)
                                 │ netsh port forward
                             bbcomm.exe (127.0.0.1:8194)
                                 │
                             Bloomberg Terminal → Bloomberg Servers

Data collected (Phase 1 + Phase 2 + Phase 3):

  Phase 1 — Market-Implied (daily → monthly):
    1. Government bond yields: 2Y, 5Y, 10Y, 30Y per country
    2. Sovereign 5Y CDS spreads per country
    3. Inflation breakeven rates (where available)
    4. Sovereign credit ratings (S&P, Moody's, Fitch — LC + FC)

  Phase 2 — Forward-Looking & Derived:
    5. MIPD: Market-implied default probability (derived from CDS)
    6. OIS 10Y swap rates + sovereign Z-spread vs OIS
    7. WIRP: Central bank rate change probabilities
    8. ECFC: Consensus GDP/CPI forecasts (with GDP fallback tickers)
    9. DDIS: Sovereign debt maturity distribution (snapshot)

  Phase 3 — ECST Activity & Monetary:
   10. PMI: S&P Global Manufacturing & Services indices per country
   11. M2: Money supply YoY growth per country

PREREQUISITES:
- Bloomberg Terminal open and logged in on Windows (Parallels)
- Run via OpusBloomberg conda env:
    conda run -p "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv" \\
        python scripts/collect_bloomberg.py

DEPENDENCIES:
- blpapi (from OpusBloomberg conda env), pandas, numpy, pyarrow, openpyxl

USAGE:
  conda run -p "...OpusBloomberg/.venv" python scripts/collect_bloomberg.py
  conda run -p "...OpusBloomberg/.venv" python scripts/collect_bloomberg.py --force
  conda run -p "...OpusBloomberg/.venv" python scripts/collect_bloomberg.py --dry-run

NOTES:
- Caches pulled data to Data/raw/bloomberg/ as parquet (24h expiry)
- Each data category in try/except — partial failures keep existing data
- Timestamped backup before every overwrite
- Bloomberg data is precious — always backed up before overwriting
- Designed to run as part of monthly_update.py pipeline
=============================================================================
"""

import argparse
import json
import logging
import shutil
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ── OpusBloomberg import ──────────────────────────────────────────────────
sys.path.insert(0, '/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg')
from bbg import BBG, bloomberg_setup

# ── Paths ─────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "Data"
RAW_DIR = DATA_DIR / "raw" / "bloomberg"
PROCESSED_DIR = DATA_DIR / "processed"
BACKUP_DIR = DATA_DIR / "backups"
CONFIG_DIR = BASE_DIR / "config"

PANEL_PQ = PROCESSED_DIR / "bloomberg_factors_panel.parquet"
PANEL_CSV = PROCESSED_DIR / "bloomberg_factors_panel.csv"
CATALOG_CSV = PROCESSED_DIR / "bloomberg_variable_catalog.csv"
HISTORY_JSON = PROCESSED_DIR / "bloomberg_run_history.json"

CACHE_HOURS = 24
HIST_START = "20000101"

for d in [RAW_DIR, PROCESSED_DIR, BACKUP_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            RAW_DIR / f"collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ),
    ],
)
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────
T2_COUNTRIES = [
    "Australia", "Brazil", "Canada", "Chile", "ChinaA", "ChinaH",
    "Denmark", "France", "Germany", "Hong Kong", "India", "Indonesia",
    "Italy", "Japan", "Korea", "Malaysia", "Mexico", "NASDAQ",
    "Netherlands", "Philippines", "Poland", "Saudi Arabia", "Singapore",
    "South Africa", "Spain", "Sweden", "Switzerland", "Taiwan",
    "Thailand", "Turkey", "U.K.", "U.S.", "US SmallCap", "Vietnam",
]

# Bloomberg country codes differ from ISO — these are the BBG ticker prefixes
# Each entry: t2_name → { tickers for govt bonds, CDS name, breakeven ticker, etc. }
# Tickers verified against Bloomberg terminal on 2026-04-12
COUNTRY_TICKERS = {
    # Verified tickers — Bloomberg generic government bond naming convention:
    #   DM: G[CC][tenor] Index  (e.g. GDBR10 for Germany 10Y)
    #   EM: varies — some use USGG style, some country-specific
    # CDS: [ISSUER] CDS USD SR 5Y Corp  (ISDA 2014 standard)
    # Breakevens: [CC]GGBE10 Index
    "Australia":     {"bond_2y": "GACGB2 Index",   "bond_5y": "GACGB5 Index",   "bond_10y": "GACGB10 Index",   "bond_30y": "GACGB30 Index",  "cds_5y": "AUSTLA CDS USD SR 5Y Corp",   "breakeven_10y": None},
    "Brazil":        {"bond_2y": "GEBR2Y Index",    "bond_5y": "GEBR5Y Index",    "bond_10y": "GEBR10Y Index",   "bond_30y": None,              "cds_5y": "BRAZIL CDS USD SR 5Y Corp",   "breakeven_10y": None},
    "Canada":        {"bond_2y": "GCAN2YR Index",   "bond_5y": "GCAN5YR Index",   "bond_10y": "GCAN10YR Index",  "bond_30y": "GCAN30YR Index",  "cds_5y": None,                           "breakeven_10y": "C90510Y Index"},
    "Chile":         {"bond_2y": None,               "bond_5y": None,               "bond_10y": "CHILE10 Index",   "bond_30y": None,              "cds_5y": "CHILE CDS USD SR 5Y Corp",    "breakeven_10y": None},
    "ChinaA":        {"bond_2y": "GCNY2YR Index",   "bond_5y": "GCNY5YR Index",   "bond_10y": "GCNY10YR Index",  "bond_30y": "GCNY30YR Index",  "cds_5y": "CHINAG CDS USD SR 5Y Corp",   "breakeven_10y": None},
    "ChinaH":        {"bond_2y": "GCNY2YR Index",   "bond_5y": "GCNY5YR Index",   "bond_10y": "GCNY10YR Index",  "bond_30y": "GCNY30YR Index",  "cds_5y": "CHINAG CDS USD SR 5Y Corp",   "breakeven_10y": None},
    "Denmark":       {"bond_2y": "GDGB2YR Index",   "bond_5y": "GDGB5YR Index",   "bond_10y": "GDGB10YR Index",  "bond_30y": None,              "cds_5y": None,                           "breakeven_10y": None},
    "France":        {"bond_2y": "GFRN2 Index",     "bond_5y": "GFRN5 Index",     "bond_10y": "GFRN10 Index",    "bond_30y": "GFRN30 Index",    "cds_5y": "FRTR CDS EUR SR 5Y Corp",     "breakeven_10y": "JGFR10 Index"},
    "Germany":       {"bond_2y": "GDBR2 Index",     "bond_5y": "GDBR5 Index",     "bond_10y": "GDBR10 Index",    "bond_30y": "GDBR30 Index",    "cds_5y": None,                           "breakeven_10y": "DBIBE10 Index"},
    "Hong Kong":     {"bond_2y": None,               "bond_5y": None,               "bond_10y": None,              "bond_30y": None,              "cds_5y": None,                           "breakeven_10y": None},
    "India":         {"bond_2y": "GIND2YR Index",   "bond_5y": "GIND5YR Index",   "bond_10y": "GIND10YR Index",  "bond_30y": None,              "cds_5y": None,                           "breakeven_10y": None},
    "Indonesia":     {"bond_2y": "GIDN2YR Index",   "bond_5y": "GIDN5YR Index",   "bond_10y": "GIDN10YR Index",  "bond_30y": None,              "cds_5y": "INDON CDS USD SR 5Y Corp",    "breakeven_10y": None},
    "Italy":         {"bond_2y": "GBTPGR2 Index",   "bond_5y": "GBTPGR5 Index",   "bond_10y": "GBTPGR10 Index",  "bond_30y": "GBTPGR30 Index",  "cds_5y": "ITALY CDS EUR SR 5Y Corp",    "breakeven_10y": "ITIBY10 Index"},
    "Japan":         {"bond_2y": "GJGB2 Index",     "bond_5y": "GJGB5 Index",     "bond_10y": "GJGB10 Index",    "bond_30y": "GJGB30 Index",    "cds_5y": "JAPAN CDS USD SR 5Y Corp",    "breakeven_10y": "JYGGBE10 Index"},
    "Korea":         {"bond_2y": "GVSK2YR Index",   "bond_5y": "GVSK5YR Index",   "bond_10y": "GVSK10YR Index",  "bond_30y": "GVSK30YR Index",  "cds_5y": "KOREA CDS USD SR 5Y Corp",    "breakeven_10y": None},
    "Malaysia":      {"bond_2y": "MALAY2Y Index",   "bond_5y": "MALAY5Y Index",   "bond_10y": "MALAY10Y Index",  "bond_30y": None,              "cds_5y": "MALAYS CDS USD SR 5Y Corp",   "breakeven_10y": None},
    "Mexico":        {"bond_2y": "GMXN02YR Index",  "bond_5y": "GMXN05YR Index",  "bond_10y": "GMXN10YR Index",  "bond_30y": "GMXN30YR Index",  "cds_5y": "MEXICO CDS USD SR 5Y Corp",   "breakeven_10y": None},
    "NASDAQ":        {"bond_2y": "USGG2YR Index",   "bond_5y": "USGG5YR Index",   "bond_10y": "USGG10YR Index",  "bond_30y": "USGG30YR Index",  "cds_5y": None,                           "breakeven_10y": "USGGBE10 Index"},
    "Netherlands":   {"bond_2y": "GNTH2YR Index",   "bond_5y": "GNTH5YR Index",   "bond_10y": "GNTH10YR Index",  "bond_30y": "GNTH30YR Index",  "cds_5y": None,                           "breakeven_10y": None},
    "Philippines":   {"bond_2y": None,               "bond_5y": "PHLGB5Y Index",   "bond_10y": "PHLGB10Y Index",  "bond_30y": None,              "cds_5y": "PHILIP CDS USD SR 5Y Corp",   "breakeven_10y": None},
    "Poland":        {"bond_2y": "POGB2YR Index",   "bond_5y": "POGB5YR Index",   "bond_10y": "POGB10YR Index",  "bond_30y": None,              "cds_5y": "POLAND CDS EUR SR 5Y Corp",   "breakeven_10y": None},
    "Saudi Arabia":  {"bond_2y": None,               "bond_5y": "GSAB5YR Index",   "bond_10y": "GSAB10YR Index",  "bond_30y": "GSAB30YR Index",  "cds_5y": "SAUDI CDS USD SR 5Y Corp",    "breakeven_10y": None},
    "Singapore":     {"bond_2y": "MASB2Y Index",    "bond_5y": "MASB5Y Index",    "bond_10y": "MASB10Y Index",   "bond_30y": None,              "cds_5y": None,                           "breakeven_10y": None},
    "South Africa":  {"bond_2y": "GSAB2YR Index",   "bond_5y": "GSAB5Y Index",    "bond_10y": "SAGB10Y Index",   "bond_30y": None,              "cds_5y": "SOAFR CDS USD SR 5Y Corp",    "breakeven_10y": None},
    "Spain":         {"bond_2y": "GSPG2YR Index",   "bond_5y": "GSPG5YR Index",   "bond_10y": "GSPG10YR Index",  "bond_30y": "GSPG30YR Index",  "cds_5y": "SPAIN CDS EUR SR 5Y Corp",    "breakeven_10y": None},
    "Sweden":        {"bond_2y": "GSGB2YR Index",   "bond_5y": "GSGB5YR Index",   "bond_10y": "GSGB10YR Index",  "bond_30y": None,              "cds_5y": None,                           "breakeven_10y": None},
    "Switzerland":   {"bond_2y": "GSWISS2 Index",   "bond_5y": None,               "bond_10y": "GSWISS10 Index",  "bond_30y": None,              "cds_5y": None,                           "breakeven_10y": None},
    "Taiwan":        {"bond_2y": None,               "bond_5y": None,               "bond_10y": "TAIBON10 Index",  "bond_30y": None,              "cds_5y": None,                           "breakeven_10y": None},
    "Thailand":      {"bond_2y": "THAI2Y Index",    "bond_5y": "THAI5Y Index",    "bond_10y": "THAI10Y Index",   "bond_30y": None,              "cds_5y": "THAI CDS USD SR 5Y Corp",     "breakeven_10y": None},
    "Turkey":        {"bond_2y": "TURKBON2 Index",  "bond_5y": "TURKBON5 Index",  "bond_10y": "TURKBON10 Index", "bond_30y": None,              "cds_5y": "TURKEY CDS USD SR 5Y Corp",   "breakeven_10y": None},
    "U.K.":          {"bond_2y": "GUKG2 Index",     "bond_5y": "GUKG5 Index",     "bond_10y": "GUKG10 Index",    "bond_30y": "GUKG30 Index",    "cds_5y": None,                           "breakeven_10y": "UKGGBE10 Index"},
    "U.S.":          {"bond_2y": "USGG2YR Index",   "bond_5y": "USGG5YR Index",   "bond_10y": "USGG10YR Index",  "bond_30y": "USGG30YR Index",  "cds_5y": None,                           "breakeven_10y": "USGGBE10 Index"},
    "US SmallCap":   {"bond_2y": "USGG2YR Index",   "bond_5y": "USGG5YR Index",   "bond_10y": "USGG10YR Index",  "bond_30y": "USGG30YR Index",  "cds_5y": None,                           "breakeven_10y": "USGGBE10 Index"},
    "Vietnam":       {"bond_2y": None,               "bond_5y": None,               "bond_10y": None,              "bond_30y": None,              "cds_5y": "VIETNM CDS USD SR 5Y Corp",   "breakeven_10y": None},
}

# Sovereign credit rating fields (BDP reference data, not time series)
RATING_FIELDS = {
    "RTG_SP_LT_LC_ISSUER_CREDIT":   "BBG_Rating_SP_LC",
    "RTG_SP_LT_FC_ISSUER_CREDIT":   "BBG_Rating_SP_FC",
    "RTG_MOODY_LT_LC_DEBT_RATING":  "BBG_Rating_Moody_LC",
    "RTG_MOODY_LT_FC_DEBT_RATING":  "BBG_Rating_Moody_FC",
    "RTG_FITCH_LT_LC_ISSUER_DEFAULT": "BBG_Rating_Fitch_LC",
    "RTG_FITCH_LT_FC_ISSUER_DEFAULT": "BBG_Rating_Fitch_FC",
}

# Sovereign tickers for ratings — these map T2 country names to a valid Bloomberg
# security that carries sovereign rating fields. For most countries we use the
# 10Y generic govt bond; for countries where bond tickers are unavailable we skip.
RATING_TICKER_OVERRIDES = {
    "ChinaH": "GCNY10YR Index",
    "NASDAQ":  "USGG10YR Index",
    "US SmallCap": "USGG10YR Index",
    "Hong Kong": None,
    "Vietnam": None,
}

# ── Phase 2: OIS Swap Rate tickers ───────────────────────────────────────
# Maps each T2 country to the 10Y OIS (or IRS) swap rate ticker for its currency.
# Multiple countries share the same currency (EUR, USD) so they share the OIS ticker.
COUNTRY_OIS_10Y = {
    "Australia":     "ADSWAP10 Curncy",
    "Brazil":        "BCSW10 Curncy",
    "Canada":        "CDSW10 Curncy",
    "Chile":         None,
    "ChinaA":        None,
    "ChinaH":        None,
    "Denmark":       "DKSW10 Curncy",
    "France":        "EUSA10 Curncy",
    "Germany":       "EUSA10 Curncy",
    "Hong Kong":     None,
    "India":         "IRSW10 Curncy",
    "Indonesia":     None,
    "Italy":         "EUSA10 Curncy",
    "Japan":         "JYSW10 Curncy",
    "Korea":         "KWSW10 Curncy",
    "Malaysia":      None,
    "Mexico":        "MPSW10 Curncy",
    "NASDAQ":        "USSW10 Curncy",
    "Netherlands":   "EUSA10 Curncy",
    "Philippines":   None,
    "Poland":        "PZSW10 Curncy",
    "Saudi Arabia":  None,
    "Singapore":     None,
    "South Africa":  "SASW10 Curncy",
    "Spain":         "EUSA10 Curncy",
    "Sweden":        "SKSW10 Curncy",
    "Switzerland":   "SFSW10 Curncy",
    "Taiwan":        None,
    "Thailand":      "THSW10 Curncy",
    "Turkey":        "TYSW10 Curncy",
    "U.K.":          "BPSW10 Curncy",
    "U.S.":          "USSW10 Curncy",
    "US SmallCap":   "USSW10 Curncy",
    "Vietnam":       None,
}

# ── Phase 2: WIRP — Central bank policy rate tickers ─────────────────────
# Each entry: T2 country name → central bank policy rate ticker for WIRP
# Countries sharing a central bank (Eurozone) share the same ticker.
COUNTRY_CB_TICKER = {
    "Australia":     "RBATCTR Index",
    "Brazil":        "BZSTSETA Index",
    "Canada":        "CABROVER Index",
    "Chile":         "CHOVCHOV Index",
    "ChinaA":        "CHLR12M Index",
    "ChinaH":        "CHLR12M Index",
    "Denmark":       None,
    "France":        "EURR002W Index",
    "Germany":       "EURR002W Index",
    "Hong Kong":     None,
    "India":         "INRPYLDP Index",
    "Indonesia":     "IDBIRATE Index",
    "Italy":         "EURR002W Index",
    "Japan":         "BOJDPBAL Index",
    "Korea":         "KORP7DR Index",
    "Malaysia":      "MAOPRATE Index",
    "Mexico":        "MXONBR Index",
    "NASDAQ":        "FDTR Index",
    "Netherlands":   "EURR002W Index",
    "Philippines":   "PPCBKRPO Index",
    "Poland":        "PORTEFCT Index",
    "Saudi Arabia":  None,
    "Singapore":     None,
    "South Africa":  "SARPRT Index",
    "Spain":         "EURR002W Index",
    "Sweden":        "SWRRATEI Index",
    "Switzerland":   "SZLTTR Index",
    "Taiwan":        "TABIRATE Index",
    "Thailand":      "BTRR1DAY Index",
    "Turkey":        "TRINT1W Index",
    "U.K.":          "UKBRBASE Index",
    "U.S.":          "FDTR Index",
    "US SmallCap":   "FDTR Index",
    "Vietnam":       None,
}

# ── Phase 2: ECFC — Consensus forecast tickers ──────────────────────────
# Bloomberg consensus GDP/CPI forecast tickers by country.
# Pattern: CO[indicator][country_code] Index
# These are Bloomberg ECFC survey-derived time series pullable via bdh().
COUNTRY_ECFC_TICKERS = {
    # GDP: try ECGD[CC] (consensus forecast) first, fallback to EHGD[CC]Y (actual YoY).
    # CPI: country-specific CPI YoY tickers (no uniform pattern).
    # BBG country codes: CH=China, SW=Switzerland, JN=Japan, BZ=Brazil, etc.
    "Australia":     {"gdp": "ECGDAU Index", "gdp_fallback": "EHGDAUY Index", "cpi": "AUCPIYOY Index"},
    "Brazil":        {"gdp": "ECGDBZ Index", "gdp_fallback": "EHGDBZY Index", "cpi": "BZCPIYOY Index"},
    "Canada":        {"gdp": "ECGDCA Index", "gdp_fallback": "EHGDCAY Index", "cpi": "CACPIYOY Index"},
    "Chile":         {"gdp": "ECGDCL Index", "gdp_fallback": "EHGDCLY Index", "cpi": "CLCPIYOY Index"},
    "ChinaA":        {"gdp": "ECGDCH Index", "gdp_fallback": "EHGDCHY Index", "cpi": "CHCPIYOY Index"},
    "ChinaH":        {"gdp": "ECGDCH Index", "gdp_fallback": "EHGDCHY Index", "cpi": "CHCPIYOY Index"},
    "Denmark":       {"gdp": "ECGDDK Index", "gdp_fallback": "EHGDDKY Index", "cpi": None},
    "France":        {"gdp": "ECGDFR Index", "gdp_fallback": "EHGDFRY Index", "cpi": "FRCPIYOY Index"},
    "Germany":       {"gdp": "ECGDDE Index", "gdp_fallback": "EHGDDEY Index", "cpi": "GRCP20YY Index"},
    "Hong Kong":     {"gdp": "ECGDHK Index", "gdp_fallback": "EHGDHKY Index", "cpi": "HKCPIY Index"},
    "India":         {"gdp": "ECGDIN Index", "gdp_fallback": "EHGDINY Index", "cpi": "INCPIYOY Index"},
    "Indonesia":     {"gdp": "ECGDID Index", "gdp_fallback": "EHGDIDY Index", "cpi": "IDCPIY Index"},
    "Italy":         {"gdp": "ECGDIT Index", "gdp_fallback": "EHGDITY Index", "cpi": "ITCPNICY Index"},
    "Japan":         {"gdp": "ECGDJN Index", "gdp_fallback": "EHGDJNY Index", "cpi": "JNCPIYOY Index"},
    "Korea":         {"gdp": "ECGDKO Index", "gdp_fallback": "EHGDKOY Index", "cpi": "KOCPIYOY Index"},
    "Malaysia":      {"gdp": "ECGDMY Index", "gdp_fallback": "EHGDMYY Index", "cpi": "MACPIYOY Index"},
    "Mexico":        {"gdp": "ECGDMX Index", "gdp_fallback": "EHGDMXY Index", "cpi": "MXCPIYOY Index"},
    "NASDAQ":        {"gdp": "ECGDUS Index", "gdp_fallback": "EHGDUSY Index", "cpi": "CPI YOY Index"},
    "Netherlands":   {"gdp": "ECGDNL Index", "gdp_fallback": "EHGDNLY Index", "cpi": None},
    "Philippines":   {"gdp": "ECGDPH Index", "gdp_fallback": "EHGDPHY Index", "cpi": "PHCPIYOY Index"},
    "Poland":        {"gdp": "ECGDPL Index", "gdp_fallback": "EHGDPLY Index", "cpi": "POCPIYOY Index"},
    "Saudi Arabia":  {"gdp": "ECGDSA Index", "gdp_fallback": "EHGDSAY Index", "cpi": None},
    "Singapore":     {"gdp": "ECGDSG Index", "gdp_fallback": "EHGDSGY Index", "cpi": "SICPIYOY Index"},
    "South Africa":  {"gdp": "ECGDZA Index", "gdp_fallback": "EHGDZAY Index", "cpi": "SACPIYOY Index"},
    "Spain":         {"gdp": "ECGDES Index", "gdp_fallback": "EHGDESY Index", "cpi": "SPCPIYOY Index"},
    "Sweden":        {"gdp": "ECGDSE Index", "gdp_fallback": "EHGDSEY Index", "cpi": "SWCPIYOY Index"},
    "Switzerland":   {"gdp": "ECGDSW Index", "gdp_fallback": "EHGDSWY Index", "cpi": "SZCPIYOY Index"},
    "Taiwan":        {"gdp": "ECGDTW Index", "gdp_fallback": "EHGDTWY Index", "cpi": "TWCPIYOY Index"},
    "Thailand":      {"gdp": "ECGDTH Index", "gdp_fallback": "EHGDTHY Index", "cpi": "THCPIYOY Index"},
    "Turkey":        {"gdp": "ECGDTU Index", "gdp_fallback": "EHGDTUY Index", "cpi": "TUCPIYOY Index"},
    "U.K.":          {"gdp": "ECGDGB Index", "gdp_fallback": "EHGDGBY Index", "cpi": "UKRPCJYR Index"},
    "U.S.":          {"gdp": "ECGDUS Index", "gdp_fallback": "EHGDUSY Index", "cpi": "CPI YOY Index"},
    "US SmallCap":   {"gdp": "ECGDUS Index", "gdp_fallback": "EHGDUSY Index", "cpi": "CPI YOY Index"},
    "Vietnam":       {"gdp": "ECGDVN Index", "gdp_fallback": "EHGDVNY Index", "cpi": None},
}

# ── Phase 2: DDIS — Sovereign external debt metrics ──────────────────────
# Bloomberg sovereign external debt tickers accessible via BLPAPI.
# These pull total external debt (in USD millions) from IMF/BIS data relayed
# through Bloomberg. Ticker pattern: [CC]EXDBT Index or [CC]EXDBTG Index.
# NOTE: DDIS proper maturity distribution requires terminal-side ticker
# discovery (DDIS function on Bloomberg Terminal). These tickers are best-effort;
# if unavailable, DDIS data will be empty — not critical since IMF WEO
# debt data already in the ASADO database covers debt-to-GDP.
COUNTRY_DEBT_TICKERS = {
    "Australia":     {"debt_gdp": "AUDEGDP Index"},
    "Brazil":        {"debt_gdp": "BZDEGDP Index"},
    "Canada":        {"debt_gdp": "CADEGDP Index"},
    "Chile":         {"debt_gdp": None},
    "ChinaA":        {"debt_gdp": None},
    "ChinaH":        {"debt_gdp": None},
    "Denmark":       {"debt_gdp": None},
    "France":        {"debt_gdp": "FRDEGDP Index"},
    "Germany":       {"debt_gdp": "DEDEGDP Index"},
    "Hong Kong":     {"debt_gdp": None},
    "India":         {"debt_gdp": "INDEGDP Index"},
    "Indonesia":     {"debt_gdp": "IDDEGDP Index"},
    "Italy":         {"debt_gdp": "ITDEGDP Index"},
    "Japan":         {"debt_gdp": "JPDEGDP Index"},
    "Korea":         {"debt_gdp": "KODEGDP Index"},
    "Malaysia":      {"debt_gdp": None},
    "Mexico":        {"debt_gdp": "MXDEGDP Index"},
    "NASDAQ":        {"debt_gdp": "USDEGDP Index"},
    "Netherlands":   {"debt_gdp": None},
    "Philippines":   {"debt_gdp": None},
    "Poland":        {"debt_gdp": "PLDEGDP Index"},
    "Saudi Arabia":  {"debt_gdp": None},
    "Singapore":     {"debt_gdp": None},
    "South Africa":  {"debt_gdp": "ZADEGDP Index"},
    "Spain":         {"debt_gdp": "ESDEGDP Index"},
    "Sweden":        {"debt_gdp": None},
    "Switzerland":   {"debt_gdp": None},
    "Taiwan":        {"debt_gdp": None},
    "Thailand":      {"debt_gdp": "THDEGDP Index"},
    "Turkey":        {"debt_gdp": "TRDEGDP Index"},
    "U.K.":          {"debt_gdp": "GBDEGDP Index"},
    "U.S.":          {"debt_gdp": "USDEGDP Index"},
    "US SmallCap":   {"debt_gdp": "USDEGDP Index"},
    "Vietnam":       {"debt_gdp": None},
}

# ── Phase 3: PMI — Purchasing Managers' Indices ──────────────────────────
# S&P Global/Markit PMI tickers follow pattern: MPMI[CC]MA (Manufacturing),
# MPMI[CC]SA (Services). Gotcha: Japan uses "JA" not "JN" in PMI tickers.
COUNTRY_PMI_TICKERS = {
    "Australia":     {"mfg": "MPMIAUMA Index", "svc": "MPMIAUSA Index"},
    "Brazil":        {"mfg": "MPMIBZMA Index", "svc": "MPMIBZSA Index"},
    "Canada":        {"mfg": "MPMICAMA Index", "svc": "MPMICASA Index"},
    "Chile":         {"mfg": None,              "svc": None},
    "ChinaA":        {"mfg": "MPMICNMA Index", "svc": "MPMICNSA Index"},
    "ChinaH":        {"mfg": "MPMICNMA Index", "svc": "MPMICNSA Index"},
    "Denmark":       {"mfg": None,              "svc": None},
    "France":        {"mfg": "MPMIFRMA Index", "svc": "MPMIFRSA Index"},
    "Germany":       {"mfg": "MPMIDEMA Index", "svc": "MPMIDESA Index"},
    "Hong Kong":     {"mfg": "MPMIHKMA Index", "svc": None},
    "India":         {"mfg": "MPMIINMA Index", "svc": "MPMIINSA Index"},
    "Indonesia":     {"mfg": "MPMIIDMA Index", "svc": None},
    "Italy":         {"mfg": "MPMIITMA Index", "svc": "MPMIITSA Index"},
    "Japan":         {"mfg": "JNPMMAFI Index", "svc": "JNPMSVFI Index"},
    "Korea":         {"mfg": "MPMIKOMA Index", "svc": None},
    "Malaysia":      {"mfg": "MPMIMYMA Index", "svc": None},
    "Mexico":        {"mfg": "MPMIMXMA Index", "svc": None},
    "NASDAQ":        {"mfg": "MPMIUSMA Index", "svc": "MPMIUSSA Index"},
    "Netherlands":   {"mfg": "MPMINLMA Index", "svc": None},
    "Philippines":   {"mfg": "MPMIPHMA Index", "svc": None},
    "Poland":        {"mfg": "MPMIPLMA Index", "svc": None},
    "Saudi Arabia":  {"mfg": "MPMISAMA Index", "svc": None},
    "Singapore":     {"mfg": "MPMISGMA Index", "svc": None},
    "South Africa":  {"mfg": "MPMIZAMA Index", "svc": None},
    "Spain":         {"mfg": "MPMIESMA Index", "svc": "MPMIESSA Index"},
    "Sweden":        {"mfg": "MPMISEMA Index", "svc": "MPMISESA Index"},
    "Switzerland":   {"mfg": None,              "svc": None},
    "Taiwan":        {"mfg": "MPMITWMA Index", "svc": None},
    "Thailand":      {"mfg": "MPMITHMA Index", "svc": None},
    "Turkey":        {"mfg": "MPMITRMA Index", "svc": None},
    "U.K.":          {"mfg": "MPMIGBMA Index", "svc": "MPMIGBSA Index"},
    "U.S.":          {"mfg": "MPMIUSMA Index", "svc": "MPMIUSSA Index"},
    "US SmallCap":   {"mfg": "MPMIUSMA Index", "svc": "MPMIUSSA Index"},
    "Vietnam":       {"mfg": "MPMIVNMA Index", "svc": None},
}

# ── Phase 3: M2 Money Supply YoY ─────────────────────────────────────────
# No uniform pattern; some confirmed tickers plus two candidate patterns
# tried per country: [CC]M2YOY Index and [CC]MSM2Y Index.
COUNTRY_M2_TICKERS = {
    "Australia":     ["AUM2YOY Index",   "AUMSM2Y Index"],
    "Brazil":        ["BZM2YOY Index",   "BZMSM2Y Index"],
    "Canada":        ["CAM2YOY Index",   "CAMSM2Y Index"],
    "Chile":         ["CLM2YOY Index",   "CLMSM2Y Index"],
    "ChinaA":        ["CNMS2YOY Index"],
    "ChinaH":        ["CNMS2YOY Index"],
    "Denmark":       ["DKM2YOY Index",   "DKMSM2Y Index"],
    "France":        ["FRM2YOY Index",   "FRMSM2Y Index"],
    "Germany":       ["DEM2YOY Index",   "DEMSM2Y Index"],
    "Hong Kong":     ["HKM2YOY Index",   "HKMSM2Y Index"],
    "India":         ["INM2YOY Index",   "INMSM2Y Index"],
    "Indonesia":     ["IDM2YOY Index"],
    "Italy":         ["ITM2YOY Index",   "ITMSM2Y Index"],
    "Japan":         ["JMNSM2Y Index"],
    "Korea":         ["KOM2YOY Index",   "KOMSM2Y Index"],
    "Malaysia":      ["MYM2YOY Index",   "MYMSM2Y Index"],
    "Mexico":        ["MXM2YOY Index",   "MXMSM2Y Index"],
    "NASDAQ":        ["M2 YOY Index"],
    "Netherlands":   ["NLM2YOY Index",   "NLMSM2Y Index"],
    "Philippines":   ["PHM2YOY Index",   "PHMSM2Y Index"],
    "Poland":        ["PLM2YOY Index",   "PLMSM2Y Index"],
    "Saudi Arabia":  ["SAM2YOY Index",   "SAMSM2Y Index"],
    "Singapore":     ["SGM2YOY Index",   "SGMSM2Y Index"],
    "South Africa":  ["ZAM2YOY Index",   "ZAMSM2Y Index"],
    "Spain":         ["ESM2YOY Index",   "ESMSM2Y Index"],
    "Sweden":        ["SEM2YOY Index",   "SEMSM2Y Index"],
    "Switzerland":   ["SWM2YOY Index",   "SWMSM2Y Index"],
    "Taiwan":        ["TWM2YOY Index",   "TWMSM2Y Index"],
    "Thailand":      ["THM2YOY Index",   "THMSM2Y Index"],
    "Turkey":        ["TRM2YOY Index",   "TRMSM2Y Index"],
    "U.K.":          ["GBM2YOY Index",   "GBMSM2Y Index"],
    "U.S.":          ["M2 YOY Index"],
    "US SmallCap":   ["M2 YOY Index"],
    "Vietnam":       ["VNM2YOY Index",   "VNMSM2Y Index"],
}


# ── Helpers ───────────────────────────────────────────────────────────────

def load_country_mapping() -> Dict[str, Dict]:
    """Load country_mapping.json."""
    with open(CONFIG_DIR / "country_mapping.json") as f:
        return json.load(f)["countries"]


def _cache_path(category: str) -> Path:
    return RAW_DIR / f"{category}.parquet"


def _is_cached(path: Path, force: bool) -> bool:
    if force or not path.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age < timedelta(hours=CACHE_HOURS)


def backup_panel():
    """Create timestamped backup of existing panel before overwriting."""
    if PANEL_PQ.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = BACKUP_DIR / f"bloomberg_factors_panel_{ts}.parquet"
        shutil.copy2(PANEL_PQ, dest)
        logger.info(f"  Backed up existing panel → {dest.name}")


def load_existing_panel() -> Optional[pd.DataFrame]:
    """Load existing bloomberg panel if it exists (for source-level merge)."""
    if PANEL_PQ.exists():
        df = pd.read_parquet(PANEL_PQ)
        df["date"] = pd.to_datetime(df["date"])
        logger.info(f"  Existing panel loaded: {len(df):,} rows, "
                     f"{df['variable'].nunique()} variables")
        return df
    return None


def to_monthly_first(dates: pd.Series) -> pd.Series:
    """Convert dates to first-of-month for ASADO standard alignment."""
    return dates.dt.to_period("M").dt.to_timestamp()


def _hist_to_df(hist_data: list, ticker: str, variable: str,
                country: str) -> pd.DataFrame:
    """Convert BBG hist() output to a tidy DataFrame row set."""
    if not hist_data:
        return pd.DataFrame()

    rows = []
    for point in hist_data:
        val = point.get("PX_LAST")
        if val is None:
            continue
        try:
            rows.append({
                "date": pd.to_datetime(point["date"]),
                "value": float(val),
            })
        except (ValueError, TypeError):
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["date"] = to_monthly_first(df["date"])
    df = df.groupby("date", as_index=False)["value"].last()
    df["country"] = country
    df["variable"] = variable
    df["source"] = "bloomberg"
    return df[["date", "country", "value", "variable", "source"]]


# =============================================================================
# COLLECTOR 1: GOVERNMENT BOND YIELDS (2Y, 5Y, 10Y, 30Y)
# =============================================================================

def collect_bond_yields(bbg: BBG, force: bool) -> pd.DataFrame:
    """Pull monthly government bond yields for all 34 countries."""
    logger.info("[1/11] Government Bond Yields (2Y, 5Y, 10Y, 30Y) ...")

    cache = _cache_path("bond_yields")
    if _is_cached(cache, force):
        logger.info("  Using cached data")
        return pd.read_parquet(cache)

    end_date = datetime.now().strftime("%Y%m%d")
    frames = []

    tenors = {
        "bond_2y":  "BBG_Govt_Bond_2Y",
        "bond_5y":  "BBG_Govt_Bond_5Y",
        "bond_10y": "BBG_Govt_Bond_10Y",
        "bond_30y": "BBG_Govt_Bond_30Y",
    }

    total_tickers = sum(
        1 for c in COUNTRY_TICKERS.values()
        for t in tenors if c.get(t) is not None
    )
    pulled = 0
    errors = 0

    for country, tickers in COUNTRY_TICKERS.items():
        for tenor_key, variable_name in tenors.items():
            ticker = tickers.get(tenor_key)
            if ticker is None:
                continue

            try:
                hist = bbg.hist(ticker, "PX_LAST", HIST_START, end_date,
                                periodicity="MONTHLY")
                df = _hist_to_df(hist, ticker, variable_name, country)
                if not df.empty:
                    frames.append(df)
                    pulled += 1
                else:
                    logger.debug(f"  No data: {country} {tenor_key} ({ticker})")
            except Exception as e:
                errors += 1
                logger.warning(f"  Error: {country} {tenor_key} ({ticker}): {e}")

    logger.info(f"  Pulled {pulled}/{total_tickers} series ({errors} errors)")

    if frames:
        result = pd.concat(frames, ignore_index=True)
        result.to_parquet(cache, index=False)
        logger.info(f"  Bond yields: {len(result):,} rows, "
                     f"{result['country'].nunique()} countries")
        return result

    return pd.DataFrame()


# =============================================================================
# COLLECTOR 2: SOVEREIGN CDS SPREADS (5Y)
# =============================================================================

def collect_cds_spreads(bbg: BBG, force: bool) -> pd.DataFrame:
    """Pull monthly sovereign 5Y CDS spreads."""
    logger.info("[2/11] Sovereign 5Y CDS Spreads ...")

    cache = _cache_path("cds_spreads")
    if _is_cached(cache, force):
        logger.info("  Using cached data")
        return pd.read_parquet(cache)

    end_date = datetime.now().strftime("%Y%m%d")
    frames = []
    pulled = 0
    errors = 0

    cds_countries = {c: t["cds_5y"] for c, t in COUNTRY_TICKERS.items()
                     if t.get("cds_5y") is not None}

    for country, ticker in cds_countries.items():
        try:
            hist = bbg.hist(ticker, "PX_LAST", HIST_START, end_date,
                            periodicity="MONTHLY")
            df = _hist_to_df(hist, ticker, "BBG_CDS_5Y", country)
            if not df.empty:
                frames.append(df)
                pulled += 1
        except Exception as e:
            errors += 1
            logger.warning(f"  Error: {country} CDS ({ticker}): {e}")

    logger.info(f"  Pulled {pulled}/{len(cds_countries)} countries ({errors} errors)")

    if frames:
        result = pd.concat(frames, ignore_index=True)
        result.to_parquet(cache, index=False)
        logger.info(f"  CDS spreads: {len(result):,} rows, "
                     f"{result['country'].nunique()} countries")
        return result

    return pd.DataFrame()


# =============================================================================
# COLLECTOR 3: INFLATION BREAKEVEN RATES
# =============================================================================

def collect_breakevens(bbg: BBG, force: bool) -> pd.DataFrame:
    """Pull monthly inflation breakeven rates (where available)."""
    logger.info("[3/11] Inflation Breakeven Rates ...")

    cache = _cache_path("breakevens")
    if _is_cached(cache, force):
        logger.info("  Using cached data")
        return pd.read_parquet(cache)

    end_date = datetime.now().strftime("%Y%m%d")
    frames = []
    pulled = 0
    errors = 0

    be_countries = {c: t["breakeven_10y"] for c, t in COUNTRY_TICKERS.items()
                    if t.get("breakeven_10y") is not None}

    for country, ticker in be_countries.items():
        try:
            hist = bbg.hist(ticker, "PX_LAST", HIST_START, end_date,
                            periodicity="MONTHLY")
            df = _hist_to_df(hist, ticker, "BBG_Breakeven_10Y", country)
            if not df.empty:
                frames.append(df)
                pulled += 1
        except Exception as e:
            errors += 1
            logger.warning(f"  Error: {country} breakeven ({ticker}): {e}")

    logger.info(f"  Pulled {pulled}/{len(be_countries)} countries ({errors} errors)")

    if frames:
        result = pd.concat(frames, ignore_index=True)
        result.to_parquet(cache, index=False)
        logger.info(f"  Breakevens: {len(result):,} rows, "
                     f"{result['country'].nunique()} countries")
        return result

    return pd.DataFrame()


# =============================================================================
# COLLECTOR 4: SOVEREIGN CREDIT RATINGS (SNAPSHOT)
# =============================================================================

def collect_credit_ratings(bbg: BBG, force: bool) -> pd.DataFrame:
    """Pull current sovereign credit ratings (S&P, Moody's, Fitch)."""
    logger.info("[4/11] Sovereign Credit Ratings (S&P, Moody's, Fitch) ...")

    cache = _cache_path("credit_ratings")
    if _is_cached(cache, force):
        logger.info("  Using cached data")
        return pd.read_parquet(cache)

    today = pd.Timestamp.now().normalize()
    today_first = to_monthly_first(pd.Series([today]))[0]

    tickers_to_pull = {}
    for country, t in COUNTRY_TICKERS.items():
        if country in RATING_TICKER_OVERRIDES:
            rating_ticker = RATING_TICKER_OVERRIDES[country]
        else:
            rating_ticker = t.get("bond_10y")
        if rating_ticker:
            tickers_to_pull[country] = rating_ticker

    bbg_fields = list(RATING_FIELDS.keys())

    frames = []
    pulled = 0
    errors = 0

    for country, ticker in tickers_to_pull.items():
        try:
            data = bbg.ref(ticker, bbg_fields)
            if "error" in data:
                logger.warning(f"  Error: {country} ratings ({ticker}): {data['error']}")
                errors += 1
                continue

            for bbg_field, variable_name in RATING_FIELDS.items():
                val = data.get(bbg_field)
                if val is not None and val != "":
                    frames.append({
                        "date": today_first,
                        "country": country,
                        "value": val,
                        "variable": variable_name,
                        "source": "bloomberg",
                    })
            pulled += 1

        except Exception as e:
            errors += 1
            logger.warning(f"  Error: {country} ratings ({ticker}): {e}")

    logger.info(f"  Pulled {pulled}/{len(tickers_to_pull)} countries ({errors} errors)")

    if frames:
        result = pd.DataFrame(frames)
        result["date"] = pd.to_datetime(result["date"])
        result.to_parquet(cache, index=False)
        logger.info(f"  Ratings: {len(result):,} rows, "
                     f"{result['country'].nunique()} countries")
        return result

    return pd.DataFrame()


# =============================================================================
# DERIVED SIGNALS
# =============================================================================

def compute_yield_curve_slope(panel: pd.DataFrame) -> pd.DataFrame:
    """Compute 10Y-2Y yield curve slope from existing bond yield data."""
    logger.info("  Computing derived signal: Yield Curve Slope (10Y-2Y) ...")

    y10 = panel[panel["variable"] == "BBG_Govt_Bond_10Y"][["date", "country", "value"]].copy()
    y2 = panel[panel["variable"] == "BBG_Govt_Bond_2Y"][["date", "country", "value"]].copy()

    if y10.empty or y2.empty:
        logger.warning("  Cannot compute slope — missing 10Y or 2Y data")
        return pd.DataFrame()

    merged = y10.merge(y2, on=["date", "country"], suffixes=("_10y", "_2y"))
    if merged.empty:
        return pd.DataFrame()

    merged["value"] = merged["value_10y"] - merged["value_2y"]
    merged["variable"] = "BBG_Yield_Curve_10Y2Y"
    merged["source"] = "bloomberg"

    result = merged[["date", "country", "value", "variable", "source"]].copy()
    logger.info(f"  Yield curve slope: {len(result):,} rows, "
                 f"{result['country'].nunique()} countries")
    return result


# =============================================================================
# COLLECTOR 5: MARKET-IMPLIED DEFAULT PROBABILITY (DERIVED FROM CDS)
# =============================================================================

def compute_mipd(cds_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Market-Implied Probability of Default from CDS spreads.

    Uses the reduced-form hazard rate model:
        MIPD_5Y = 1 - exp(-spread_bps / 10000 * tenor / (1 - recovery))

    Standard assumptions: 5Y tenor, 40% recovery rate (ISDA standard).
    """
    logger.info("  Computing derived signal: MIPD (from CDS spreads) ...")

    if cds_df.empty:
        logger.warning("  Cannot compute MIPD — no CDS data")
        return pd.DataFrame()

    TENOR = 5.0
    RECOVERY = 0.40

    df = cds_df[cds_df["variable"] == "BBG_CDS_5Y"].copy()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])

    if df.empty:
        return pd.DataFrame()

    df["value"] = 1 - np.exp(-df["value"] / 10000 * TENOR / (1 - RECOVERY))
    df["variable"] = "BBG_MIPD_5Y"

    logger.info(f"  MIPD: {len(df):,} rows, {df['country'].nunique()} countries")
    return df[["date", "country", "value", "variable", "source"]].copy()


# =============================================================================
# COLLECTOR 6: OIS SWAP RATES + SOVEREIGN Z-SPREAD
# =============================================================================

def collect_ois_swap_rates(bbg: BBG, force: bool) -> pd.DataFrame:
    """Pull 10Y OIS/IRS swap rates and compute Z-spread vs govt bonds."""
    logger.info("[6/11] OIS 10Y Swap Rates ...")

    cache = _cache_path("ois_swap_rates")
    if _is_cached(cache, force):
        logger.info("  Using cached data")
        return pd.read_parquet(cache)

    end_date = datetime.now().strftime("%Y%m%d")
    frames = []
    pulled = 0
    errors = 0

    ois_countries = {c: t for c, t in COUNTRY_OIS_10Y.items() if t is not None}
    seen_tickers = set()

    for country, ticker in ois_countries.items():
        if ticker in seen_tickers:
            continue
        seen_tickers.add(ticker)

        try:
            hist = bbg.hist(ticker, "PX_LAST", HIST_START, end_date,
                            periodicity="MONTHLY")
            if not hist:
                continue

            rows = []
            for point in hist:
                val = point.get("PX_LAST")
                if val is None:
                    continue
                try:
                    rows.append({
                        "date": pd.to_datetime(point["date"]),
                        "value": float(val),
                    })
                except (ValueError, TypeError):
                    continue

            if rows:
                df_raw = pd.DataFrame(rows)
                df_raw["date"] = to_monthly_first(df_raw["date"])
                df_raw = df_raw.groupby("date", as_index=False)["value"].last()

                for c, t in ois_countries.items():
                    if t == ticker:
                        df_c = df_raw.copy()
                        df_c["country"] = c
                        df_c["variable"] = "BBG_OIS_10Y"
                        df_c["source"] = "bloomberg"
                        frames.append(df_c[["date", "country", "value",
                                           "variable", "source"]])
                pulled += 1
        except Exception as e:
            errors += 1
            logger.warning(f"  Error OIS ({ticker}): {e}")

    logger.info(f"  Pulled {pulled}/{len(seen_tickers)} unique tickers ({errors} errors)")

    if frames:
        result = pd.concat(frames, ignore_index=True)
        result.to_parquet(cache, index=False)
        logger.info(f"  OIS rates: {len(result):,} rows, "
                     f"{result['country'].nunique()} countries")
        return result

    return pd.DataFrame()


def compute_zspread_ois(bond_df: pd.DataFrame,
                        ois_df: pd.DataFrame) -> pd.DataFrame:
    """Compute sovereign Z-spread = 10Y govt yield - 10Y OIS rate."""
    logger.info("  Computing derived signal: Z-Spread vs OIS ...")

    if bond_df.empty or ois_df.empty:
        logger.warning("  Cannot compute Z-spread — missing data")
        return pd.DataFrame()

    b10 = bond_df[bond_df["variable"] == "BBG_Govt_Bond_10Y"][
        ["date", "country", "value"]].copy()
    b10["value"] = pd.to_numeric(b10["value"], errors="coerce")

    ois = ois_df[ois_df["variable"] == "BBG_OIS_10Y"][
        ["date", "country", "value"]].copy()
    ois["value"] = pd.to_numeric(ois["value"], errors="coerce")

    merged = b10.merge(ois, on=["date", "country"], suffixes=("_bond", "_ois"))
    if merged.empty:
        return pd.DataFrame()

    merged["value"] = merged["value_bond"] - merged["value_ois"]
    merged["variable"] = "BBG_ZSpread_OIS_10Y"
    merged["source"] = "bloomberg"

    result = merged[["date", "country", "value", "variable", "source"]].copy()
    logger.info(f"  Z-spread OIS: {len(result):,} rows, "
                 f"{result['country'].nunique()} countries")
    return result


# =============================================================================
# COLLECTOR 7: WIRP — CENTRAL BANK RATE PROBABILITIES
# =============================================================================

def collect_wirp(bbg: BBG, force: bool) -> pd.DataFrame:
    """
    Pull implied policy rate from Bloomberg for each central bank.

    Uses ref() to get the current implied next-meeting rate from the
    central bank policy rate ticker.
    """
    logger.info("[7/11] WIRP — Central Bank Rate Probabilities ...")

    cache = _cache_path("wirp")
    if _is_cached(cache, force):
        logger.info("  Using cached data")
        return pd.read_parquet(cache)

    today = pd.Timestamp.now().normalize()
    today_first = to_monthly_first(pd.Series([today]))[0]

    frames = []
    pulled = 0
    errors = 0
    seen = set()

    cb_countries = {c: t for c, t in COUNTRY_CB_TICKER.items() if t is not None}

    for country, ticker in cb_countries.items():
        if ticker in seen:
            continue
        seen.add(ticker)

        try:
            data = bbg.ref(ticker, ["PX_LAST", "NAME"])
            if "error" in data:
                errors += 1
                logger.warning(f"  Error: {country} WIRP ({ticker}): {data['error']}")
                continue

            px_last = data.get("PX_LAST")
            if px_last is None or px_last == "":
                continue

            for c, t in cb_countries.items():
                if t == ticker:
                    frames.append({
                        "date": today_first,
                        "country": c,
                        "value": float(px_last),
                        "variable": "BBG_WIRP_ImpliedRate",
                        "source": "bloomberg",
                    })
            pulled += 1

        except Exception as e:
            errors += 1
            logger.warning(f"  Error: {country} WIRP ({ticker}): {e}")

    # Also try pulling historical policy rates for time series
    end_date = datetime.now().strftime("%Y%m%d")
    hist_frames = []
    seen_hist = set()

    for country, ticker in cb_countries.items():
        if ticker in seen_hist:
            continue
        seen_hist.add(ticker)

        try:
            hist = bbg.hist(ticker, "PX_LAST", HIST_START, end_date,
                            periodicity="MONTHLY")
            if not hist:
                continue

            rows = []
            for point in hist:
                val = point.get("PX_LAST")
                if val is None:
                    continue
                try:
                    rows.append({
                        "date": pd.to_datetime(point["date"]),
                        "value": float(val),
                    })
                except (ValueError, TypeError):
                    continue

            if rows:
                df_raw = pd.DataFrame(rows)
                df_raw["date"] = to_monthly_first(df_raw["date"])
                df_raw = df_raw.groupby("date", as_index=False)["value"].last()

                for c, t in cb_countries.items():
                    if t == ticker:
                        df_c = df_raw.copy()
                        df_c["country"] = c
                        df_c["variable"] = "BBG_WIRP_ImpliedRate"
                        df_c["source"] = "bloomberg"
                        hist_frames.append(df_c[["date", "country", "value",
                                                 "variable", "source"]])
        except Exception as e:
            logger.debug(f"  WIRP hist skip {ticker}: {e}")

    logger.info(f"  Pulled {pulled}/{len(seen)} unique CB tickers ({errors} errors)")

    all_frames = hist_frames
    if not all_frames and frames:
        all_frames = [pd.DataFrame(frames)]

    if all_frames:
        result = pd.concat(all_frames, ignore_index=True)
        result.to_parquet(cache, index=False)
        logger.info(f"  WIRP: {len(result):,} rows, "
                     f"{result['country'].nunique()} countries")
        return result

    return pd.DataFrame()


# =============================================================================
# COLLECTOR 8: ECFC — CONSENSUS MACRO FORECASTS
# =============================================================================

def collect_ecfc(bbg: BBG, force: bool) -> pd.DataFrame:
    """
    Pull consensus GDP and CPI forecasts from Bloomberg ECFC survey tickers.

    GDP strategy: try ECGD[CC] (consensus) first; if it fails, fall back to
    EHGD[CC]Y (actual GDP YoY).  CPI uses country-specific tickers directly.
    """
    logger.info("[8/11] ECFC — Consensus Macro Forecasts (GDP, CPI) ...")

    cache = _cache_path("ecfc")
    if _is_cached(cache, force):
        logger.info("  Using cached data")
        return pd.read_parquet(cache)

    end_date = datetime.now().strftime("%Y%m%d")
    frames = []
    pulled = 0
    errors = 0
    seen_tickers = set()
    fallback_used = 0

    for country, tickers in COUNTRY_ECFC_TICKERS.items():
        # ── CPI ──
        cpi_ticker = tickers.get("cpi")
        if cpi_ticker is not None and cpi_ticker not in seen_tickers:
            try:
                hist = bbg.hist(cpi_ticker, "PX_LAST", "20100101", end_date,
                                periodicity="MONTHLY")
                df = _hist_to_df(hist, cpi_ticker, "BBG_ECFC_CPI", country)
                if not df.empty:
                    frames.append(df)
                    pulled += 1
                seen_tickers.add(cpi_ticker)
            except Exception as e:
                errors += 1
                seen_tickers.add(cpi_ticker)
                logger.warning(f"  Error: {country} CPI ({cpi_ticker}): {e}")

        # ── GDP with fallback ──
        gdp_ticker = tickers.get("gdp")
        gdp_fallback = tickers.get("gdp_fallback")
        gdp_ok = False

        if gdp_ticker is not None and gdp_ticker not in seen_tickers:
            try:
                hist = bbg.hist(gdp_ticker, "PX_LAST", "20100101", end_date,
                                periodicity="MONTHLY")
                df = _hist_to_df(hist, gdp_ticker, "BBG_ECFC_GDP", country)
                if not df.empty:
                    frames.append(df)
                    pulled += 1
                    gdp_ok = True
                seen_tickers.add(gdp_ticker)
            except Exception as e:
                errors += 1
                seen_tickers.add(gdp_ticker)
                logger.warning(f"  Error: {country} GDP ({gdp_ticker}): {e}")

        if not gdp_ok and gdp_fallback is not None and gdp_fallback not in seen_tickers:
            try:
                hist = bbg.hist(gdp_fallback, "PX_LAST", "20100101", end_date,
                                periodicity="MONTHLY")
                df = _hist_to_df(hist, gdp_fallback, "BBG_ECFC_GDP", country)
                if not df.empty:
                    frames.append(df)
                    pulled += 1
                    fallback_used += 1
                    logger.info(f"  {country}: GDP fallback ticker worked ({gdp_fallback})")
                seen_tickers.add(gdp_fallback)
            except Exception as e:
                errors += 1
                seen_tickers.add(gdp_fallback)
                logger.debug(f"  {country}: GDP fallback also failed ({gdp_fallback}): {e}")

    # Ensure alias groups share data: whichever alias pulled data, copy to all others
    alias_groups = [
        ["ChinaA", "ChinaH"],
        ["U.S.", "NASDAQ", "US SmallCap"],
    ]
    for group in alias_groups:
        for variable_name in ("BBG_ECFC_GDP", "BBG_ECFC_CPI"):
            # Find which alias in the group has data
            source_df = None
            for member in group:
                match = [f for f in frames
                        if isinstance(f, pd.DataFrame) and not f.empty
                        and f["country"].iloc[0] == member
                        and f["variable"].iloc[0] == variable_name]
                if match:
                    source_df = match[0]
                    break
            if source_df is not None:
                for member in group:
                    already = any(isinstance(f, pd.DataFrame) and not f.empty
                                 and f["country"].iloc[0] == member
                                 and f["variable"].iloc[0] == variable_name
                                 for f in frames)
                    if not already:
                        dup = source_df.copy()
                        dup["country"] = member
                        frames.append(dup)

    logger.info(f"  Pulled {pulled} unique ticker series ({errors} errors, "
                f"{fallback_used} GDP fallbacks used)")

    if frames:
        result = pd.concat(frames, ignore_index=True)
        result.to_parquet(cache, index=False)
        logger.info(f"  ECFC: {len(result):,} rows, "
                     f"{result['country'].nunique()} countries")
        return result

    return pd.DataFrame()


# =============================================================================
# COLLECTOR 9: DDIS — SOVEREIGN DEBT MATURITY DISTRIBUTION
# =============================================================================

def collect_ddis(bbg: BBG, force: bool) -> pd.DataFrame:
    """
    Pull sovereign debt-to-GDP ratio time series from Bloomberg.

    Uses bdh() on [CC]DEBT2G Index tickers — the standard Bloomberg
    government debt-to-GDP indicators from ECST/WCDM.
    """
    logger.info("[9/11] DDIS — Sovereign Debt Metrics ...")

    cache = _cache_path("ddis")
    if _is_cached(cache, force):
        logger.info("  Using cached data")
        return pd.read_parquet(cache)

    end_date = datetime.now().strftime("%Y%m%d")
    frames = []
    pulled = 0
    errors = 0
    seen_tickers = set()

    for country, tickers in COUNTRY_DEBT_TICKERS.items():
        ticker = tickers.get("debt_gdp")
        if ticker is None or ticker in seen_tickers:
            if ticker in seen_tickers:
                pass
            continue

        try:
            hist = bbg.hist(ticker, "PX_LAST", "20000101", end_date,
                            periodicity="MONTHLY")
            if not hist:
                seen_tickers.add(ticker)
                continue

            rows = []
            for point in hist:
                val = point.get("PX_LAST")
                if val is None:
                    continue
                try:
                    rows.append({
                        "date": pd.to_datetime(point["date"]),
                        "value": float(val),
                    })
                except (ValueError, TypeError):
                    continue

            if rows:
                df_raw = pd.DataFrame(rows)
                df_raw["date"] = to_monthly_first(df_raw["date"])
                df_raw = df_raw.groupby("date", as_index=False)["value"].last()

                for c, t in COUNTRY_DEBT_TICKERS.items():
                    if t.get("debt_gdp") == ticker:
                        df_c = df_raw.copy()
                        df_c["country"] = c
                        df_c["variable"] = "BBG_Debt_GDP_Ratio"
                        df_c["source"] = "bloomberg"
                        frames.append(df_c[["date", "country", "value",
                                           "variable", "source"]])
                pulled += 1

            seen_tickers.add(ticker)

        except Exception as e:
            errors += 1
            seen_tickers.add(ticker)
            logger.warning(f"  Error: {country} DDIS ({ticker}): {e}")

    logger.info(f"  Pulled {pulled}/{len(seen_tickers)} unique tickers ({errors} errors)")

    if frames:
        result = pd.concat(frames, ignore_index=True)
        result.to_parquet(cache, index=False)
        logger.info(f"  DDIS: {len(result):,} rows, "
                     f"{result['country'].nunique()} countries")
        return result

    return pd.DataFrame()


# =============================================================================
# COLLECTOR 10: PMI — PURCHASING MANAGERS' INDICES
# =============================================================================

def collect_pmi(bbg: BBG, force: bool) -> pd.DataFrame:
    """
    Pull S&P Global/Markit PMI Manufacturing and Services indices.

    Tries MPMI[CC]MA/SA tickers for each country. Countries without
    liquid PMI data will fail gracefully and be skipped.
    """
    logger.info("[10/11] PMI — Manufacturing & Services ...")

    cache = _cache_path("pmi")
    if _is_cached(cache, force):
        logger.info("  Using cached data")
        return pd.read_parquet(cache)

    end_date = datetime.now().strftime("%Y%m%d")
    frames = []
    pulled = 0
    errors = 0
    seen_tickers = set()

    indicator_map = {
        "mfg": "BBG_PMI_Manufacturing",
        "svc": "BBG_PMI_Services",
    }

    for country, tickers in COUNTRY_PMI_TICKERS.items():
        for ind_key, variable_name in indicator_map.items():
            ticker = tickers.get(ind_key)
            if ticker is None or ticker in seen_tickers:
                continue

            try:
                hist = bbg.hist(ticker, "PX_LAST", HIST_START, end_date,
                                periodicity="MONTHLY")
                df = _hist_to_df(hist, ticker, variable_name, country)
                if not df.empty:
                    frames.append(df)
                    pulled += 1
                seen_tickers.add(ticker)
            except Exception as e:
                errors += 1
                seen_tickers.add(ticker)
                logger.warning(f"  Error: {country} {ind_key} ({ticker}): {e}")

    # Ensure alias groups share data
    alias_groups = [
        ["ChinaA", "ChinaH"],
        ["U.S.", "NASDAQ", "US SmallCap"],
    ]
    for group in alias_groups:
        for variable_name in indicator_map.values():
            source_df = None
            for member in group:
                match = [f for f in frames
                        if isinstance(f, pd.DataFrame) and not f.empty
                        and f["country"].iloc[0] == member
                        and f["variable"].iloc[0] == variable_name]
                if match:
                    source_df = match[0]
                    break
            if source_df is not None:
                for member in group:
                    already = any(isinstance(f, pd.DataFrame) and not f.empty
                                 and f["country"].iloc[0] == member
                                 and f["variable"].iloc[0] == variable_name
                                 for f in frames)
                    if not already:
                        dup = source_df.copy()
                        dup["country"] = member
                        frames.append(dup)

    logger.info(f"  Pulled {pulled}/{len(seen_tickers)} unique tickers ({errors} errors)")

    if frames:
        result = pd.concat(frames, ignore_index=True)
        result.to_parquet(cache, index=False)
        logger.info(f"  PMI: {len(result):,} rows, "
                     f"{result['country'].nunique()} countries")
        return result

    return pd.DataFrame()


# =============================================================================
# COLLECTOR 11: M2 — MONEY SUPPLY YEAR-OVER-YEAR
# =============================================================================

def collect_m2(bbg: BBG, force: bool) -> pd.DataFrame:
    """
    Pull M2 money supply YoY growth for each country.

    No uniform ticker pattern exists; for each country we try a list of
    candidate tickers and keep the first one that returns data.
    """
    logger.info("[11/11] M2 — Money Supply YoY ...")

    cache = _cache_path("m2")
    if _is_cached(cache, force):
        logger.info("  Using cached data")
        return pd.read_parquet(cache)

    end_date = datetime.now().strftime("%Y%m%d")
    frames = []
    pulled = 0
    errors = 0
    seen_tickers = set()

    for country, candidates in COUNTRY_M2_TICKERS.items():
        got_data = False
        for ticker in candidates:
            if ticker in seen_tickers:
                # Already pulled this exact ticker for another country alias
                existing_src = [f for f in frames
                               if isinstance(f, pd.DataFrame) and
                               not f.empty and
                               ticker in f.attrs.get("ticker", "")]
                continue

            try:
                hist = bbg.hist(ticker, "PX_LAST", HIST_START, end_date,
                                periodicity="MONTHLY")
                df = _hist_to_df(hist, ticker, "BBG_M2_YoY", country)
                if not df.empty:
                    df.attrs["ticker"] = ticker
                    frames.append(df)
                    pulled += 1
                    got_data = True
                    seen_tickers.add(ticker)
                    break
                seen_tickers.add(ticker)
            except Exception as e:
                errors += 1
                seen_tickers.add(ticker)
                logger.debug(f"  {country}: M2 ticker failed ({ticker}): {e}")

        if not got_data:
            logger.debug(f"  {country}: no M2 ticker worked")

    # Ensure alias groups share data
    alias_groups = [
        ["ChinaA", "ChinaH"],
        ["U.S.", "NASDAQ", "US SmallCap"],
    ]
    for group in alias_groups:
        source_df = None
        for member in group:
            match = [f for f in frames
                    if isinstance(f, pd.DataFrame) and not f.empty
                    and f["country"].iloc[0] == member]
            if match:
                source_df = match[0]
                break
        if source_df is not None:
            for member in group:
                already = any(isinstance(f, pd.DataFrame) and not f.empty
                             and f["country"].iloc[0] == member
                             for f in frames)
                if not already:
                    dup = source_df.copy()
                    dup["country"] = member
                    frames.append(dup)

    logger.info(f"  Pulled {pulled}/{len(seen_tickers)} unique tickers ({errors} errors)")

    if frames:
        result = pd.concat(frames, ignore_index=True)
        result.to_parquet(cache, index=False)
        logger.info(f"  M2: {len(result):,} rows, "
                     f"{result['country'].nunique()} countries")
        return result

    return pd.DataFrame()


# =============================================================================
# MERGE / ASSEMBLY
# =============================================================================

def merge_panels(existing: Optional[pd.DataFrame],
                 fresh: Dict[str, pd.DataFrame],
                 status: Dict[str, str]) -> pd.DataFrame:
    """
    Source-level merge: for each category, if fresh data succeeded, replace
    that category; if it failed, keep existing data for that category.
    """
    category_vars = {
        "Bond Yields":    ["BBG_Govt_Bond_2Y", "BBG_Govt_Bond_5Y",
                           "BBG_Govt_Bond_10Y", "BBG_Govt_Bond_30Y"],
        "CDS Spreads":    ["BBG_CDS_5Y"],
        "Breakevens":     ["BBG_Breakeven_10Y"],
        "Credit Ratings": [v for v in RATING_FIELDS.values()],
        "Yield Curve":    ["BBG_Yield_Curve_10Y2Y"],
        "MIPD":           ["BBG_MIPD_5Y"],
        "OIS Rates":      ["BBG_OIS_10Y"],
        "Z-Spread OIS":   ["BBG_ZSpread_OIS_10Y"],
        "WIRP":           ["BBG_WIRP_ImpliedRate"],
        "ECFC":           ["BBG_ECFC_GDP", "BBG_ECFC_CPI"],
        "DDIS":           ["BBG_Debt_GDP_Ratio"],
        "PMI":            ["BBG_PMI_Manufacturing", "BBG_PMI_Services"],
        "M2":             ["BBG_M2_YoY"],
    }

    parts = []

    for cat_name, df in fresh.items():
        if status.get(cat_name) == "SUCCESS" and not df.empty:
            parts.append(df)
        elif existing is not None and cat_name in category_vars:
            keep_vars = category_vars[cat_name]
            old = existing[existing["variable"].isin(keep_vars)]
            if not old.empty:
                parts.append(old)
                logger.info(f"  Keeping existing data for {cat_name} "
                             f"({len(old):,} rows)")

    if not parts:
        return existing if existing is not None else pd.DataFrame()

    return pd.concat(parts, ignore_index=True)


def create_variable_catalog(panel: pd.DataFrame) -> pd.DataFrame:
    """Create metadata catalog for each variable."""
    if panel.empty:
        return pd.DataFrame()

    numeric = panel[pd.to_numeric(panel["value"], errors="coerce").notna()].copy()
    numeric["value"] = pd.to_numeric(numeric["value"])

    rows = []
    for var in sorted(panel["variable"].unique()):
        sub = panel[panel["variable"] == var]
        nsub = numeric[numeric["variable"] == var]
        rows.append({
            "variable": var,
            "source": "bloomberg",
            "n_countries": sub["country"].nunique(),
            "n_observations": len(sub),
            "date_min": sub["date"].min().strftime("%Y-%m-%d") if not sub.empty else None,
            "date_max": sub["date"].max().strftime("%Y-%m-%d") if not sub.empty else None,
            "mean": nsub["value"].mean() if not nsub.empty else None,
            "std": nsub["value"].std() if not nsub.empty else None,
            "pct_missing": 1 - len(nsub) / len(sub) if len(sub) > 0 else None,
        })

    return pd.DataFrame(rows)


def record_run(status: Dict, panel: pd.DataFrame, elapsed: float):
    """Append run metadata to history file."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "total_rows": len(panel),
        "n_variables": int(panel["variable"].nunique()),
        "n_countries": int(panel["country"].nunique()),
        "status": status,
    }

    history = []
    if HISTORY_JSON.exists():
        try:
            with open(HISTORY_JSON) as f:
                history = json.load(f)
        except json.JSONDecodeError:
            pass

    history.append(entry)
    with open(HISTORY_JSON, "w") as f:
        json.dump(history, f, indent=2)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="ASADO Bloomberg Data Collector"
    )
    parser.add_argument("--force", action="store_true",
                        help="Bypass 24h download cache, pull fresh data")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without saving files")
    args = parser.parse_args()

    t0 = time.time()

    logger.info("=" * 60)
    logger.info("ASADO Bloomberg Data Collector")
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # ── Step 1: Bloomberg connection setup ────────────────────────────
    logger.info("\nSetting up Bloomberg connection ...")
    try:
        bloomberg_setup(verbose=False)
        logger.info("  Bloomberg connection OK")
    except Exception as e:
        logger.error(f"  Bloomberg connection FAILED: {e}")
        logger.error("  Is Bloomberg Terminal open on Parallels?")
        sys.exit(1)

    # ── Step 2: Load existing panel ───────────────────────────────────
    existing_panel = load_existing_panel()

    # ── Step 3: Collect from Bloomberg ────────────────────────────────
    logger.info("\n" + "-" * 60)
    logger.info("COLLECTING DATA FROM BLOOMBERG")
    logger.info("-" * 60 + "\n")

    fresh_frames: Dict[str, pd.DataFrame] = {}
    status: Dict[str, str] = {}

    with BBG() as bbg:
        # Test connection first
        if not bbg.ping():
            logger.error("Bloomberg ping failed — cannot proceed")
            sys.exit(1)
        logger.info("  Ping OK — Bloomberg is responsive\n")

        collectors = [
            ("Bond Yields",    lambda: collect_bond_yields(bbg, args.force)),
            ("CDS Spreads",    lambda: collect_cds_spreads(bbg, args.force)),
            ("Breakevens",     lambda: collect_breakevens(bbg, args.force)),
            ("Credit Ratings", lambda: collect_credit_ratings(bbg, args.force)),
            ("OIS Rates",      lambda: collect_ois_swap_rates(bbg, args.force)),
            ("WIRP",           lambda: collect_wirp(bbg, args.force)),
            ("ECFC",           lambda: collect_ecfc(bbg, args.force)),
            ("DDIS",           lambda: collect_ddis(bbg, args.force)),
            ("PMI",            lambda: collect_pmi(bbg, args.force)),
            ("M2",             lambda: collect_m2(bbg, args.force)),
        ]

        for name, fn in collectors:
            try:
                df = fn()
                if df is not None and not df.empty:
                    fresh_frames[name] = df
                    status[name] = "SUCCESS"
                else:
                    fresh_frames[name] = pd.DataFrame()
                    status[name] = "NO DATA"
                    logger.warning(f"  {name}: returned no data")
            except Exception as e:
                fresh_frames[name] = pd.DataFrame()
                status[name] = f"FAILED: {e}"
                logger.error(f"  {name}: FAILED — {e}")
            logger.info("")

    # ── Step 4: Compute derived signals ──────────────────────────────
    bond_df = fresh_frames.get("Bond Yields", pd.DataFrame())
    if not bond_df.empty:
        slope_df = compute_yield_curve_slope(bond_df)
        if not slope_df.empty:
            fresh_frames["Yield Curve"] = slope_df
            status["Yield Curve"] = "SUCCESS"

    cds_df = fresh_frames.get("CDS Spreads", pd.DataFrame())
    if not cds_df.empty:
        mipd_df = compute_mipd(cds_df)
        if not mipd_df.empty:
            fresh_frames["MIPD"] = mipd_df
            status["MIPD"] = "SUCCESS"

    ois_df = fresh_frames.get("OIS Rates", pd.DataFrame())
    if not bond_df.empty and not ois_df.empty:
        zspread_df = compute_zspread_ois(bond_df, ois_df)
        if not zspread_df.empty:
            fresh_frames["Z-Spread OIS"] = zspread_df
            status["Z-Spread OIS"] = "SUCCESS"

    # ── Step 5: Merge and assemble panel ─────────────────────────────
    logger.info("-" * 60)
    logger.info("MERGING fresh data with existing panel ...")

    panel = merge_panels(existing_panel, fresh_frames, status)

    if panel.empty:
        logger.error("Panel is empty after merge — aborting.")
        return

    panel = panel.drop_duplicates(subset=["date", "country", "variable"])
    panel = panel.sort_values(["variable", "country", "date"]).reset_index(drop=True)

    catalog = create_variable_catalog(panel)

    # ── Step 6: Save ─────────────────────────────────────────────────
    if args.dry_run:
        logger.info("\n--dry-run: skipping file writes")
    else:
        backup_panel()
        panel.to_parquet(PANEL_PQ, index=False)
        panel.to_csv(PANEL_CSV, index=False)
        catalog.to_csv(CATALOG_CSV, index=False)
        logger.info(f"\nSaved: {PANEL_PQ}")
        logger.info(f"Saved: {PANEL_CSV}")
        logger.info(f"Saved: {CATALOG_CSV}")

    elapsed = time.time() - t0
    if not args.dry_run:
        record_run(status, panel, elapsed)

    # ── Step 7: Summary ──────────────────────────────────────────────
    if existing_panel is not None:
        old_rows = len(existing_panel)
        new_rows = len(panel)
        delta = new_rows - old_rows
        sign = "+" if delta >= 0 else ""
        logger.info(f"\nDelta vs. previous: {old_rows:,} → {new_rows:,} "
                     f"({sign}{delta:,} rows)")

    logger.info("\n" + "=" * 60)
    logger.info("BLOOMBERG COLLECTION SUMMARY")
    logger.info("=" * 60)

    for name, st in status.items():
        marker = "OK" if st == "SUCCESS" else "WARN"
        logger.info(f"  [{marker:4s}] {name:25s} {st}")

    n_ok = sum(1 for s in status.values() if s == "SUCCESS")
    n_vars = panel["variable"].nunique()
    n_ctry = panel["country"].nunique()
    n_rows = len(panel)

    logger.info(f"\nCategories OK : {n_ok}/{len(status)}")
    logger.info(f"Variables     : {n_vars}")
    logger.info(f"Countries     : {n_ctry}/34")
    logger.info(f"Total rows    : {n_rows:,}")

    numeric_panel = panel[pd.to_numeric(panel["value"], errors="coerce").notna()]
    if not numeric_panel.empty:
        logger.info(f"Date range    : {numeric_panel['date'].min().strftime('%Y-%m')} → "
                     f"{numeric_panel['date'].max().strftime('%Y-%m')}")

    logger.info(f"Elapsed       : {elapsed:.1f}s")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
