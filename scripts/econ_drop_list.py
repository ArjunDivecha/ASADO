"""
=============================================================================
SCRIPT NAME: scripts/econ_drop_list.py
=============================================================================

INPUT FILES:  (none) — pure-Python canonical configuration module.
OUTPUT FILES: (none) — imported by build_econ_panel.py.

VERSION: 1.0
LAST UPDATED: 2026-06-04
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
Single source of truth for the Econ factor REDUNDANCY drop-list. A
correlation audit of the econ _CS signals (2026-06-04) found ~58 factor pairs
with |r| >= 0.85 — the same economic concept pulled from multiple providers
(IMF / World Bank / ILO / UNDP / ND-GAIN / macrostructure), accounting-identity
mirrors, and composite-vs-component duplicates. This drops the redundant
member of each cluster, keeping the fresher / more-authoritative / more-direct
series. Unlike the GDELT keep-list (an allowlist over a firehose), this is a
DROP-LIST: everything not listed here is retained.

Selection principle: keep the fresher / primary source; drop identity mirrors,
composite-vs-component duplicates, and collinear sub-indicators.

Each dropped base sheet also removes its derived variants downstream
(_CS / _TS / _D12 / _D12_CS / _D12_TS), since those are computed from the base.

USAGE:
  from econ_drop_list import should_drop
  SHEETS = [(s, v) for (s, v) in SHEETS if not should_drop(s)]

NOTES:
- Matching is on the Excel SHEET NAME (which becomes the downstream factor
  base). Names are matched after stripping a trailing _D12.
- Kept-but-correlated factors that are economically distinct were deliberately
  retained (e.g. IMF_CPI_Inflation_YoY, WB_Population_Growth, WB_Trade_Openness,
  WB_Female_LFP, NDGAIN_Score, WB_Govt_Effectiveness, WB_Political_Stability).
=============================================================================
"""
from __future__ import annotations

# 23 redundant base sheets to drop (see module docstring for the audit).
DROP_SHEETS: frozenset[str] = frozenset({
    # A. Same concept, different source — keep the fresher IMF/ILO series
    "WB_Inflation_CPI",            # ~ IMF_WEO_Inflation (r=0.99)
    "WB_GDP_Growth_Real",          # ~ IMF_WEO_GDP_Growth (0.99)
    "WB_Current_Account_GDP",      # ~ IMF_WEO_CA_GDP (0.96)
    "WB_Population",               # ~ IMF_WEO_Population (1.00)
    "WB_Unemployment",             # ~ ILO_Unemployment_Rate (0.96)
    "IMF_WEO_Unemployment",        # ~ ILO_Unemployment_Rate (0.95)
    # B. Accounting identities / composite-vs-component
    "FAO_Import_Dependency",       # = inverse of FAO_Self_Sufficiency (1.00)
    "IMF_BOP_Financial_Account_Bal",  # ~ -IMF_BOP_Current_Account by identity (0.98)
    "IMF_Trade_Openness_USD",      # = (X+M)/GDP, collinear w/ IMF Exports+Imports
    "NDGAIN_Readiness",            # component of NDGAIN_Score (0.97)
    "NDGAIN_Vulnerability",        # component of NDGAIN_Score (0.86)
    "UNDP_IHDI",                   # ~ UNDP_HDI (0.94)
    "MS_CentralBank_Claims_on_G_0cda",   # ~ MS_CentralBank_BalanceSheet_GDP (0.98)
    "MS_CentralBank_SovDebt_Share",      # ~ MS_CentralBank_BalanceSheet_GDP (0.98)
    "MS_Swap_Line_Access",         # ~ MS_Policy_Backstop (0.98)
    "WB_Import_Cover_Months",      # ~ MS_Reserve_Adequacy (0.86)
    "MS_Public_Debt_Domestic_Cu_3b00",   # ~ MS_Public_Debt_Domestic_Cr (0.91)
    # C. Collinear WGI governance family — keep Govt_Effectiveness + Political_Stability
    "WB_Control_Corruption",
    "WB_Rule_of_Law",
    "WB_Regulatory_Quality",
    "WB_Voice_Accountability",
    # D. Borderline (user-approved)
    "IMF_TBill_Rate",              # ~ IMF_Money_Market_Rate (0.90)
    "WB_Female_Labor_Share",       # ~ WB_Female_LFP (0.86)
})


def should_drop(sheet_name: str) -> bool:
    """True if this Econ sheet (or its _D12 variant) is a redundant drop."""
    base = sheet_name[:-4] if sheet_name.endswith("_D12") else sheet_name
    return base in DROP_SHEETS
