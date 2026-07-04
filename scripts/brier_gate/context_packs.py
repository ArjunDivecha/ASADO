"""
=============================================================================
SCRIPT NAME: context_packs.py (Brier Gate step 2 — library module)
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  (read-only: market_implied_daily, sovereign_daily, eco_surprise_signals)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
  (read-only: gdelt_raw_daily)

OUTPUT FILES:
- None directly (library). The forecast runner caches rendered packs to
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/brier_gate/packs.jsonl

VERSION: 1.0
LAST UPDATED: 2026-07-03
AUTHOR: Claude Code (for Arjun Divecha)

DESCRIPTION:
Builds the point-in-time ASADO context pack for one prediction-market
question at forecast time t (Brier Gate arm A1/A2, docs/PRD_BRIER_GATE.md).

PIT DISCIPLINE (the crux of the experiment): every query filters
date <= (t - 24h).date() — a full-day embargo, so a daily close value is
only visible the following day. No web access, no series later than that.

Sections (built only when relevant; each capped):
  1. Global risk dashboard (always): VIX, VIX3M, MOVE, HY OAS, DXY
  2. Commodities (oil/gold/gas/copper keywords or oil tag): front + 2nd
     contract levels and recent changes
  3. US rates & macro (fed/inflation/rates keywords or tags): 2Y & 10Y
     Treasury yield path, latest US eco-surprise reading
  4. Country lens (any of GDELT's 249 country names detected in the
     question/title, max 3): news tone z, news risk, attention shock;
     plus 5Y CDS and 10Y yield if a T2 country

DEPENDENCIES:
- duckdb, pandas (project venv)

USAGE:
  from context_packs import ContextPackBuilder
  cpb = ContextPackBuilder()
  text, sha = cpb.build(question, event_title, tag, forecast_ts)

NOTES:
- Connections are opened read-only once and reused; call .close() when done.
- Country detection is word-boundary regex over GDELT country names, with
  a small alias map (US/U.S./America -> United States, UK -> United Kingdom).
=============================================================================
"""

from __future__ import annotations

import hashlib
import re
from datetime import timedelta
from pathlib import Path

import duckdb
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOOP_DB = BASE_DIR / "Data" / "loop" / "asado_loop.duckdb"
MAIN_DB = BASE_DIR / "Data" / "asado.duckdb"

RISK_VARS = ["RISK_VIX", "RISK_VIX3M", "RISK_MOVE", "RISK_HY_OAS", "RISK_DXY"]
CMD_KEYWORDS = {
    "CMD_CL1": r"\b(oil|wti|crude|opec|barrel)\b",
    "CMD_CO1": r"\b(oil|brent|crude|opec|barrel)\b",
    "CMD_GC1": r"\b(gold)\b",
    "CMD_NG1": r"\b(natural gas|natgas|lng)\b",
    "CMD_HG1": r"\b(copper)\b",
}
RATES_RE = re.compile(
    r"\b(fed|fomc|interest rate|rate cut|rate hike|inflation|cpi|treasury|yield|recession|gdp|unemployment|jobs report|payrolls)\b",
    re.IGNORECASE,
)
ALIASES = {
    "US": "United States", "U.S.": "United States", "USA": "United States",
    "America": "United States", "UK": "United Kingdom", "U.K.": "United Kingdom",
    "Korea": "South Korea",
}
T2_SOV = {  # GDELT name -> sovereign_daily country name where they differ
    "United States": "U.S.", "United Kingdom": "U.K.", "South Korea": "Korea",
}


def _fmt_series(df: pd.DataFrame, label: str, ndays: int = 12) -> str:
    if df.empty:
        return ""
    tail = df.tail(ndays)
    vals = ", ".join(f"{d:%m-%d}={v:.2f}" for d, v in zip(tail["date"], tail["value"]))
    latest = tail["value"].iloc[-1]
    chg5 = latest - tail["value"].iloc[-6] if len(tail) > 5 else None
    chg = f" (5d chg {chg5:+.2f})" if chg5 is not None else ""
    return f"{label}: {vals}{chg}\n"


class ContextPackBuilder:
    def __init__(self) -> None:
        self.loop = duckdb.connect(str(LOOP_DB), read_only=True)
        self.main = duckdb.connect(str(MAIN_DB), read_only=True)
        names = self.main.execute(
            "SELECT DISTINCT country_name FROM gdelt_raw_daily"
        ).fetchall()
        self.gdelt_countries = sorted({r[0] for r in names if r[0]}, key=len, reverse=True)
        self._country_re = re.compile(
            r"\b(" + "|".join(re.escape(c) for c in self.gdelt_countries + list(ALIASES)) + r")\b"
        )

    def close(self) -> None:
        self.loop.close()
        self.main.close()

    def _loop_series(self, table: str, variable: str, country: str, cutoff, n: int = 25) -> pd.DataFrame:
        return self.loop.execute(
            f"""SELECT date, value FROM {table}
                WHERE variable = ? AND country = ? AND date <= ?
                ORDER BY date DESC LIMIT {n}""",
            [variable, country, cutoff],
        ).df().sort_values("date")

    def build(self, question: str, event_title: str, tag: str, forecast_ts) -> tuple[str, str]:
        t = pd.Timestamp(forecast_ts)
        cutoff = (t - timedelta(hours=24)).date()
        text = f"[ASADO warehouse data, all series as of {cutoff} or earlier]\n\n"
        blob = f"{question} {event_title}".strip()

        # 1. Global risk dashboard
        sec = ""
        for var in RISK_VARS:
            sec += _fmt_series(self._loop_series("market_implied_daily", var, "GLOBAL", cutoff), var.replace("RISK_", ""))
        if sec:
            text += "== Global risk dashboard ==\n" + sec + "\n"

        # 2. Commodities
        sec = ""
        for var, pat in CMD_KEYWORDS.items():
            if tag == "oil" and var in ("CMD_CL1", "CMD_CO1") or re.search(pat, blob, re.IGNORECASE):
                label = {"CMD_CL1": "WTI front", "CMD_CO1": "Brent front", "CMD_GC1": "Gold front",
                         "CMD_NG1": "NatGas front", "CMD_HG1": "Copper front"}[var]
                sec += _fmt_series(self._loop_series("market_implied_daily", var, "GLOBAL", cutoff), label)
        if sec:
            text += "== Commodity prices ==\n" + sec + "\n"

        # 3. US rates & macro
        if tag in ("fed-rates", "inflation", "economy") or RATES_RE.search(blob):
            sec = ""
            for var, label in [("SOV_2Y_YIELD_PCT", "US 2Y yield %"), ("SOV_10Y_YIELD_PCT", "US 10Y yield %")]:
                sec += _fmt_series(self._loop_series("sovereign_daily", var, "U.S.", cutoff), label)
            es = self.loop.execute(
                """SELECT date, variable, value FROM eco_surprise_signals
                   WHERE country = 'U.S.' AND date <= ? ORDER BY date DESC LIMIT 6""",
                [cutoff],
            ).df()
            if not es.empty:
                sec += "US eco surprises (latest): " + ", ".join(
                    f"{r.variable}={r.value:.2f} ({r.date:%m-%d})" for r in es.itertuples()
                ) + "\n"
            if sec:
                text += "== US rates & macro ==\n" + sec + "\n"

        # 4. Country lens
        found: list[str] = []
        for match in self._country_re.findall(blob):
            name = ALIASES.get(match, match)
            if name not in found and name in self.gdelt_countries:
                found.append(name)
        for name in found[:3]:
            g = self.main.execute(
                """SELECT date, country_news_sentiment AS tone_z, country_news_risk AS risk,
                          attention_shock
                   FROM gdelt_raw_daily WHERE country_name = ? AND date <= ?
                   ORDER BY date DESC LIMIT 10""",
                [name, str(cutoff)],
            ).df().sort_values("date")
            sec = ""
            if not g.empty:
                sec += "News tone z: " + ", ".join(
                    f"{d:%m-%d}={v:.2f}" for d, v in zip(g["date"], g["tone_z"])) + "\n"
                sec += "News risk: " + ", ".join(
                    f"{d:%m-%d}={v:.2f}" for d, v in zip(g["date"], g["risk"])) + "\n"
            sov_name = T2_SOV.get(name, name)
            cds = self._loop_series("sovereign_daily", "SOV_CDS_5Y_BP", sov_name, cutoff, n=10)
            sec += _fmt_series(cds, "5Y CDS bp", ndays=8)
            if sec:
                text += f"== {name} ==\n" + sec + "\n"

        text = text[:7000]
        sha = hashlib.sha256(text.encode()).hexdigest()[:16]
        return text, sha
