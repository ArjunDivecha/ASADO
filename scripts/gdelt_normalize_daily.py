#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/gdelt_normalize_daily.py
=============================================================================

DESCRIPTION:
    DAILY analog of gdelt_normalize.py. Reads the upstream GDELT repo's
    country_signal_daily.parquet directly and produces tidy _CS/_TS normalized
    daily GDELT factors, plus the daily 1DRet country-return series.

INPUT FILES:
    - GDELT country_signal_daily.parquet
    - Data/work/t2_daily/normalized_t2_master.parquet  (for the 1DRet series)

OUTPUT FILES:
    - Data/work/gdelt_daily/gdelt_factors_daily.parquet  (tidy: date,country,variable,value)

NO EXCEL OR CSV:
    The daily GDELT path reads parquet and writes parquet.

VERSION: 1.0
LAST UPDATED: 2026-06-09
AUTHOR: Arjun Divecha (ported by Claude Code)

DEPENDENCIES: pandas, pyarrow

USAGE:
    python scripts/gdelt_normalize_daily.py
    python scripts/gdelt_normalize_daily.py --panel-parquet PATH --t2-parquet PATH --out-parquet PATH
=============================================================================
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

try:
    from scripts import gdelt_normalize as gn
    from scripts.loop.loopdb import t2_countries
except ModuleNotFoundError:  # direct execution as python scripts/gdelt_normalize_daily.py
    import gdelt_normalize as gn
    from loop.loopdb import t2_countries

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
GDELT_WORK_DIR = BASE_DIR / "Data" / "work" / "gdelt_daily"
DEFAULT_PANEL_PARQUET = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT/data/panels/country_signal_daily.parquet")
DEFAULT_T2_PARQUET = BASE_DIR / "Data" / "work" / "t2_daily" / "normalized_t2_master.parquet"
DEFAULT_OUT_PARQUET = GDELT_WORK_DIR / "gdelt_factors_daily.parquet"
COUNTRY_MAPPING = BASE_DIR / "config" / "country_mapping.json"

PANEL_INDICATORS = [
    ("country_news_sentiment", "country_news_sentiment"),
    ("country_news_risk", "country_news_risk"),
    ("country_news_sentiment_raw", "country_news_sentiment_raw"),
    ("country_news_risk_raw", "country_news_risk_raw"),
    ("country_news_attention", "country_news_attention"),
    ("local_attention_share", "local_attention_share"),
    ("sentiment_x_attention", "country_news_sentiment_x_attention"),
    ("local_tone", "local_tone"),
    ("foreign_tone", "foreign_tone"),
    ("attention_shock", "attention_shock"),
    ("tone_dispersion", "tone_dispersion"),
    ("tone_wavg_wordcount", "tone_wavg_wordcount"),
    ("tone_mean", "tone_mean"),
    ("tone_p50", "tone_p50"),
    ("positive_mean", "positive_mean"),
    ("negative_mean", "negative_mean"),
    ("polarity_mean", "polarity_mean"),
    ("n_articles", "n_articles"),
]


def _load_1dret_long(t2_parquet: Path) -> pd.DataFrame:
    if not t2_parquet.exists():
        raise FileNotFoundError(f"T2 normalized parquet not found: {t2_parquet}")
    panel = pd.read_parquet(t2_parquet, columns=["date", "country", "variable", "value"])
    panel = panel.rename(columns={c: c.lower() for c in panel.columns if c.lower() == "date"})
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce")
    ret = panel[panel["variable"] == "1DRet"][["date", "country", "variable", "value"]].copy()
    ret["country"] = ret["country"].astype(str)
    return ret


def _iso3_to_t2_countries(mapping_path: Path = COUNTRY_MAPPING) -> dict[str, list[str]]:
    payload = json.loads(mapping_path.read_text())
    live = set(t2_countries())
    out: dict[str, list[str]] = {}
    for country, meta in payload["countries"].items():
        if country not in live:
            continue
        iso3 = str(meta.get("iso3") or "").strip()
        if iso3:
            out.setdefault(iso3, []).append(country)
    return out


def _panel_parts(
    panel_path: Path,
    mapping_path: Path = COUNTRY_MAPPING,
) -> tuple[list[pd.DataFrame], pd.Timestamp, pd.Timestamp, list[str]]:
    if not panel_path.exists():
        raise FileNotFoundError(f"GDELT panel parquet not found: {panel_path}")
    panel = pd.read_parquet(panel_path)
    required = {"date", "country_iso3"}
    missing_required = sorted(required - set(panel.columns))
    if missing_required:
        raise ValueError(f"GDELT panel missing required columns: {missing_required}")
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
    panel["country_iso3"] = panel["country_iso3"].astype(str).str.strip()
    panel = panel.dropna(subset=["date"])
    iso_to_t2 = _iso3_to_t2_countries(mapping_path)
    panel = panel[panel["country_iso3"].isin(iso_to_t2)].copy()
    if panel.empty:
        raise ValueError(f"GDELT panel has no ASADO T2 countries: {panel_path}")

    parts: list[pd.DataFrame] = []
    loaded: list[str] = []
    for sheet_name, column in PANEL_INDICATORS:
        if column not in panel.columns:
            continue
        rows = panel[["date", "country_iso3", column]].copy()
        rows[column] = pd.to_numeric(rows[column], errors="coerce")
        rows = rows.dropna(subset=[column])
        if rows.empty:
            continue
        exploded = []
        for iso3, countries in iso_to_t2.items():
            sub = rows.loc[rows["country_iso3"] == iso3, ["date", column]]
            if sub.empty:
                continue
            for country in countries:
                c = sub.rename(columns={column: country}).set_index("date")
                exploded.append(c)
        if not exploded:
            continue
        wide = pd.concat(exploded, axis=1).sort_index()
        wide = wide.loc[:, ~wide.columns.duplicated()]
        wide.index.name = "date"
        if gn._should_flip(sheet_name):
            wide = wide * -1.0
        parts.extend(gn._sheet_to_long_variants(sheet_name, wide))
        loaded.append(sheet_name)

    if not parts:
        raise ValueError(f"GDELT panel produced no normalized variables: {panel_path}")
    return parts, pd.Timestamp(panel["date"].min()).normalize(), pd.Timestamp(panel["date"].max()).normalize(), loaded


def main() -> int:
    ap = argparse.ArgumentParser(description="Daily GDELT parquet -> tidy factor parquet.")
    ap.add_argument("--panel-parquet", default=str(DEFAULT_PANEL_PARQUET),
                    help="GDELT repo country_signal_daily.parquet. Daily GDELT is parquet-only.")
    ap.add_argument("--t2-parquet", default=str(DEFAULT_T2_PARQUET))
    ap.add_argument("--out-parquet", default=str(DEFAULT_OUT_PARQUET))
    args = ap.parse_args()

    out_path = Path(args.out_parquet); out_path.parent.mkdir(parents=True, exist_ok=True)

    panel_arg = Path(args.panel_parquet)
    all_parts, win_s, win_e, loaded = _panel_parts(panel_arg)
    logger.info("Loaded GDELT panel parquet: %s (%d indicators)", panel_arg, len(loaded))

    ret = _load_1dret_long(Path(args.t2_parquet))
    combined = pd.concat([pd.concat(all_parts, ignore_index=True), ret], ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
    combined = combined.dropna(subset=["date"])
    combined = combined[(combined["date"] >= win_s) & (combined["date"] <= win_e)]
    combined = combined.sort_values(["date", "variable", "country"]).reset_index(drop=True)
    if combined.empty:
        logger.error("GDELT normalization produced zero rows for window %s..%s", win_s.date(), win_e.date())
        return 1
    combined.to_parquet(out_path, index=False)
    logger.info("Wrote %s (%d rows, %d vars, window %s..%s)",
                out_path, len(combined), combined["variable"].nunique(), win_s.date(), win_e.date())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
