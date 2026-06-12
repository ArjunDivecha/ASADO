#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: discover_predmkt_candidates.py
=============================================================================

WHAT THIS PROGRAM DOES (plain English):
The ASADO prediction-market registry (config/predmkt_curated.yaml) is a
hand-curated list of Polymarket and Kalshi markets that matter for the
34-country macro universe. Curating it by hand means finding live market IDs
one at a time, which is slow. This program automates the FINDING part:

  1. It asks Kalshi for every open market in a fixed list of macro series
     (CPI, Fed decisions, rate cuts, unemployment, GDP, recession).
  2. It pages through Polymarket's most-traded active markets and keeps the
     ones whose titles match macro/geopolitics keyword rules (oil, Taiwan,
     Ukraine, tariffs, elections in our 34 countries, recession, etc.),
     while throwing away sports/crypto/celebrity noise.
  3. For every keeper it drafts a registry entry: category, subcategory,
     resolution clarity, and a TEMPLATE spillover block (which countries are
     affected, in which direction, through which channel).

The output is a DRAFT for human/agent review — entries are appended to the
real registry only after curation. Elasticities in the templates are
judgment starting points, not estimates.

INPUT FILES (full paths):
- (none on disk — reads two live APIs)
  https://api.elections.kalshi.com/trade-api/v2/markets   (keyless)
  https://gamma-api.polymarket.com/markets                (keyless)

OUTPUT FILES (full paths):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/predmkt_discovery.json
    Raw candidate dump (all fields fetched, before drafting).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/predmkt_candidates_draft.yaml
    Draft registry entries in the exact predmkt_curated.yaml schema.

VERSION: 1.0
LAST UPDATED: 2026-06-11
AUTHOR: ASADO agent session

DEPENDENCIES: requests, pyyaml (both in ASADO venv)

USAGE:
  python scripts/loop/discover_predmkt_candidates.py
  python scripts/loop/discover_predmkt_candidates.py --poly-pages 20

NOTES:
- Keyless public endpoints; ~25 HTTP calls total, < 1 minute.
- Existing registry IDs are excluded automatically so the draft only
  contains NEW candidates.
- Ladder series (CPI strikes) keep every open strike for the nearest two
  expiries; far expiries are skipped to limit noise.
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path

import requests
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REGISTRY_PATH = BASE_DIR / "config" / "predmkt_curated.yaml"
OUT_DIR = BASE_DIR / "Data" / "work" / "loop"
OUT_JSON = OUT_DIR / "predmkt_discovery.json"
OUT_YAML = OUT_DIR / "predmkt_candidates_draft.yaml"

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
POLY_BASE = "https://gamma-api.polymarket.com"

# ── Kalshi macro series to sweep ─────────────────────────────────────────────
# series_ticker -> (asado_category, subcategory_prefix, resolution_source)
KALSHI_SERIES = {
    "KXCPI":      ("cpi", "cpi_mom", "BLS CPI release"),
    "KXCPICOREYOY": ("cpi", "cpi_core_yoy", "BLS CPI release"),
    "KXCPIYOY":   ("cpi", "cpi_yoy", "BLS CPI release"),
    "KXFEDDECISION": ("fed_policy", "fed_decision", "FOMC statement"),
    "KXFED":      ("fed_policy", "fed_target", "FOMC statement"),
    "KXRATECUT":  ("fed_policy", "fed_cut_count", "FOMC rate decisions"),
    "KXU3":       ("unemployment", "unemployment_u3", "BLS Employment Situation"),
    "KXPAYROLLS": ("unemployment", "payrolls", "BLS Employment Situation"),
    "KXGDP":      ("gdp_recession", "gdp_print", "BEA GDP release"),
    "KXRECSSNBER": ("gdp_recession", "recession_nber", "NBER declaration"),
}

# ── Polymarket keyword routing ───────────────────────────────────────────────
# First matching rule wins. (regex on question+slug, lowercased)
POLY_RULES = [
    ("oil_shock", "high", r"\b(wti|brent|crude|oil)\b.*\b(hit|reach|high|above|\$\d)", "Front-month settlement (CME/ICE)"),
    ("oil_shock", "high", r"\bopec\b", "OPEC official communique"),
    ("regional_conflict_me", "medium", r"\b(hormuz|iran|israel.*(strike|war|attack)|houthis?|red sea)\b", "Recognized conflict/maritime reporting"),
    ("regional_conflict_pacific", "medium", r"\b(taiwan|south china sea|china.*(invade|blockade|military))\b", "Recognized military engagement criteria"),
    ("regional_conflict_eastern_europe", "medium", r"\b(ukraine|russia.*(ceasefire|peace|war|nato)|zelensky|putin.*(meet|deal))\b", "Recognized ceasefire/conflict reporting"),
    ("tariff", "high", r"\btariff", "Official tariff implementation announcements"),
    ("fed_policy", "high", r"\b(fed|fomc|powell|rate (cut|hike)|interest rates?)\b", "FOMC statement"),
    ("gdp_recession", "medium", r"\brecession\b", "NBER recession declaration"),
    ("cpi", "high", r"\b(inflation|cpi)\b", "BLS CPI release"),
    ("country_election", "high",
     r"\b(brazil|mexico|india|indonesia|korea|japan|germany|france|italy|spain|"
     r"poland|turkey|philippines|thailand|malaysia|vietnam|south africa|chile|"
     r"netherlands|sweden|denmark|switzerland|australia|canada|u\.?k\.?|hungary)\b"
     r".*\b(election|president|prime minister|pm\b|chancellor)|"
     r"\b(election|president|prime minister|chancellor)\b.*"
     r"\b(brazil|mexico|india|indonesia|korea|japan|germany|france|italy|spain|"
     r"poland|turkey|philippines|thailand|malaysia|vietnam|south africa|chile|"
     r"netherlands|sweden|denmark|switzerland|australia|canada)\b",
     "Official electoral authority result"),
    ("china_policy", "medium", r"\bchina\b.*\b(gdp|stimulus|yuan|devalu|property|evergrande)\b", "Official PRC statistics / policy announcements"),
    ("sanctions", "medium", r"\b(sanction|swift ban|oil price cap)\b", "Official sanctions announcements"),
]

# Hard blacklist — never macro-relevant.
POLY_BLACKLIST = re.compile(
    r"\b(nba|nfl|mlb|nhl|ufc|premier league|champions league|world cup|fifa|"
    r"grammy|oscar|emmy|bitcoin|btc|ethereum|solana|crypto|airdrop|"
    r"gta|minecraft|taylor swift|kanye|mrbeast|jesus|antichrist|alien|"
    r"time'?s person|spotify|box office|super bowl|olympic)\b", re.I)

# ── Spillover templates per category ────────────────────────────────────────
# Sign convention follows the existing registry: positive elasticity = YES
# outcome HURTS that country's equity market; negative = helps.
SPILLOVER_TEMPLATES = {
    "oil_shock": [
        ("Saudi Arabia", -0.70, "oil_export", "high"),
        ("India", 0.50, "oil_import_dependency", "high"),
        ("Japan", 0.45, "oil_import_dependency", "high"),
        ("Korea", 0.35, "oil_import_dependency", "medium"),
        ("Thailand", 0.30, "oil_import_dependency", "medium"),
    ],
    "regional_conflict_me": [
        ("Saudi Arabia", 0.55, "regional_proximity", "high"),
        ("India", 0.30, "oil_import_dependency", "medium"),
        ("Japan", 0.25, "oil_import_dependency", "medium"),
        ("Turkey", 0.20, "regional_proxy", "low"),
    ],
    "regional_conflict_pacific": [
        ("Taiwan", 0.80, "regional_proximity", "high"),
        ("ChinaA", 0.55, "regional_proximity", "high"),
        ("ChinaH", 0.55, "regional_proximity", "high"),
        ("Korea", 0.45, "tech_supply_chain", "high"),
        ("Japan", 0.40, "regional_proximity", "medium"),
    ],
    "regional_conflict_eastern_europe": [
        ("Poland", 0.50, "regional_proximity", "high"),
        ("Germany", 0.30, "trade_partner", "medium"),
        ("Turkey", 0.20, "regional_proxy", "medium"),
        ("Sweden", 0.15, "regional_proximity", "low"),
    ],
    "tariff": [
        ("ChinaA", 0.40, "trade_partner", "medium"),
        ("Mexico", 0.30, "trade_partner", "medium"),
        ("Canada", 0.25, "trade_partner", "medium"),
        ("U.S.", 0.15, "usd_beta", "medium"),
    ],
    "fed_policy": [
        ("U.S.", -0.30, "usd_beta", "high"),
        ("NASDAQ", -0.40, "usd_beta", "high"),
        ("Brazil", -0.25, "em_beta", "medium"),
        ("Mexico", -0.20, "em_beta", "medium"),
        ("India", -0.15, "em_beta", "medium"),
    ],
    "cpi": [
        ("U.S.", -0.40, "usd_beta", "high"),
        ("NASDAQ", -0.50, "usd_beta", "medium"),
    ],
    "unemployment": [
        ("U.S.", 0.30, "usd_beta", "high"),
        ("US SmallCap", 0.35, "usd_beta", "medium"),
    ],
    "gdp_recession": [
        ("U.S.", 0.65, "usd_beta", "high"),
        ("Germany", 0.30, "trade_partner", "medium"),
        ("Korea", 0.25, "tech_supply_chain", "medium"),
        ("Japan", 0.20, "trade_partner", "medium"),
    ],
    "china_policy": [
        ("ChinaA", 0.50, "regional_proxy", "high"),
        ("ChinaH", 0.50, "regional_proxy", "high"),
        ("Australia", 0.25, "commodity_export", "medium"),
        ("Brazil", 0.20, "commodity_export", "medium"),
    ],
    "sanctions": [
        ("ChinaA", 0.25, "trade_partner", "medium"),
        ("Germany", 0.20, "trade_partner", "medium"),
        ("Turkey", 0.15, "regional_proxy", "low"),
    ],
    "country_election": [],  # filled per-market from the matched country
}

# Election keyword -> T2 country (for per-market spillover)
ELECTION_COUNTRY = {
    "brazil": "Brazil", "mexico": "Mexico", "india": "India",
    "indonesia": "Indonesia", "korea": "Korea", "japan": "Japan",
    "germany": "Germany", "france": "France", "italy": "Italy",
    "spain": "Spain", "poland": "Poland", "turkey": "Turkey",
    "philippines": "Philippines", "thailand": "Thailand",
    "malaysia": "Malaysia", "vietnam": "Vietnam",
    "south africa": "South Africa", "chile": "Chile",
    "netherlands": "Netherlands", "sweden": "Sweden",
    "denmark": "Denmark", "switzerland": "Switzerland",
    "australia": "Australia", "canada": "Canada", "uk": "U.K.",
    "u.k.": "U.K.",
}


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "asado-predmkt-discovery/1.0"
    return s


def existing_ids() -> set[str]:
    if not REGISTRY_PATH.exists():
        return set()
    entries = yaml.safe_load(REGISTRY_PATH.read_text()) or []
    return {str(e.get("market_id", "")).strip() for e in entries}


def sweep_kalshi(s: requests.Session) -> list[dict]:
    out = []
    for series, (cat, subprefix, res_src) in KALSHI_SERIES.items():
        try:
            r = s.get(f"{KALSHI_BASE}/markets",
                      params={"series_ticker": series, "status": "open", "limit": 200},
                      timeout=30)
            r.raise_for_status()
            mkts = r.json().get("markets", [])
        except Exception as e:
            print(f"  KALSHI {series}: FAILED {e!r}")
            continue
        if not mkts:
            print(f"  KALSHI {series}: no open markets")
            continue
        # Ladders: keep only the nearest two expiries (close_time sorted).
        closes = sorted({m.get("close_time", "") for m in mkts})[:2]
        kept = [m for m in mkts if m.get("close_time", "") in closes]
        print(f"  KALSHI {series}: {len(mkts)} open -> keeping {len(kept)} (nearest expiries)")
        for m in kept:
            out.append({
                "platform": "kalshi",
                "market_id": m["ticker"],
                "title": m.get("title", ""),
                "close_time": m.get("close_time"),
                "volume": m.get("volume", 0),
                "category": cat,
                "subcategory": f"{subprefix}_{m['ticker'].split('-')[-1].lower().replace('.', 'p')}",
                "resolution_source": res_src,
                "clarity": "high",
            })
        time.sleep(0.4)
    return out


def sweep_polymarket(s: requests.Session, pages: int) -> list[dict]:
    out, seen = [], set()
    for page in range(pages):
        try:
            r = s.get(f"{POLY_BASE}/markets",
                      params={"active": "true", "closed": "false", "limit": 100,
                              "offset": page * 100, "order": "volumeNum",
                              "ascending": "false"},
                      timeout=30)
            r.raise_for_status()
            mkts = r.json()
        except Exception as e:
            print(f"  POLY page {page}: FAILED {e!r}")
            break
        if not mkts:
            break
        for m in mkts:
            cid = m.get("conditionId", "")
            slug = m.get("slug", "")
            text = f"{m.get('question', '')} {slug}".lower()
            if not cid or cid in seen or POLY_BLACKLIST.search(text):
                continue
            for cat, clarity, pattern, res_src in POLY_RULES:
                if re.search(pattern, text):
                    seen.add(cid)
                    out.append({
                        "platform": "polymarket",
                        "market_id": cid,
                        "slug": slug,
                        "title": m.get("question", ""),
                        "end_date": m.get("endDate"),
                        "volume": float(m.get("volumeNum") or 0),
                        "category": cat,
                        "subcategory": re.sub(r"[^a-z0-9]+", "_", slug)[:60].strip("_"),
                        "resolution_source": res_src,
                        "clarity": clarity,
                    })
                    break
        time.sleep(0.3)
    print(f"  POLY: {len(out)} keyword-matched candidates from {pages} pages")
    return out


def to_registry_entry(c: dict) -> dict:
    cat = c["category"]
    spill = SPILLOVER_TEMPLATES.get(cat, [])
    if cat == "country_election":
        text = f"{c.get('title', '')} {c.get('slug', '')}".lower()
        hits = [t2 for kw, t2 in ELECTION_COUNTRY.items() if kw in text]
        spill = [(hits[0], 0.45, "regional_proxy", "high")] if hits else []
    entry = {
        "platform": c["platform"],
        "market_id": c["market_id"],
        "asado_category": cat,
        "asado_subcategory": c["subcategory"],
        "contract_type": "binary",
        "resolution_clarity": c["clarity"],
        "resolution_source": c["resolution_source"],
        "spillover_countries": [
            {"country": t2, "elasticity": e, "channel": ch, "confidence": cf}
            for t2, e, ch, cf in spill
        ],
    }
    if c.get("slug"):
        entry["slug"] = c["slug"]
    return entry


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--poly-pages", type=int, default=15,
                    help="pages of 100 Polymarket markets to scan (default 15)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    s = _session()
    known = existing_ids()
    print(f"Existing registry IDs: {len(known)}")

    print("Sweeping Kalshi macro series ...")
    kalshi = sweep_kalshi(s)
    print("Sweeping Polymarket top-volume actives ...")
    poly = sweep_polymarket(s, args.poly_pages)

    candidates = [c for c in kalshi + poly if c["market_id"] not in known]
    OUT_JSON.write_text(json.dumps(
        {"generated": datetime.now().isoformat(), "candidates": candidates},
        indent=2, default=str))

    drafts = [to_registry_entry(c) for c in candidates]
    header = (
        "# DRAFT predmkt registry candidates — generated "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')} by discover_predmkt_candidates.py\n"
        "# REVIEW BEFORE MERGING into config/predmkt_curated.yaml:\n"
        "#   - prune mis-categorized markets\n"
        "#   - adjust template elasticities where the specific market differs\n"
        f"# {len(drafts)} candidates ({len(kalshi)} kalshi, {len(poly)} polymarket, "
        f"{len(kalshi) + len(poly) - len(candidates)} already in registry)\n\n"
    )
    OUT_YAML.write_text(header + yaml.dump(drafts, sort_keys=False, allow_unicode=True))
    print(f"\nWrote {len(candidates)} candidates:")
    print(f"  {OUT_JSON}")
    print(f"  {OUT_YAML}")
    by_cat: dict[str, int] = {}
    for c in candidates:
        by_cat[c["category"]] = by_cat.get(c["category"], 0) + 1
    for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        print(f"    {k:<36} {v}")


if __name__ == "__main__":
    main()
