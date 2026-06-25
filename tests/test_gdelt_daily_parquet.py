from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from scripts import gdelt_normalize_daily as norm
from scripts import refresh_gdelt_daily as refresh


def test_panel_parts_expands_duplicate_t2_countries(tmp_path):
    mapping = tmp_path / "country_mapping.json"
    mapping.write_text(json.dumps({
        "countries": {
            "Australia": {"iso3": "AUS"},
            "NASDAQ": {"iso3": "USA"},
            "U.S.": {"iso3": "USA"},
            "ChinaA": {"iso3": "CHN"},
            "ChinaH": {"iso3": "CHN"},
        }
    }))
    panel = tmp_path / "country_signal_daily.parquet"
    pd.DataFrame([
        {"date": "2026-06-22", "country_iso3": "AUS", "country_news_sentiment": 1.0},
        {"date": "2026-06-22", "country_iso3": "USA", "country_news_sentiment": 2.0},
        {"date": "2026-06-22", "country_iso3": "CHN", "country_news_sentiment": 3.0},
        {"date": "2026-06-23", "country_iso3": "AUS", "country_news_sentiment": 4.0},
        {"date": "2026-06-23", "country_iso3": "USA", "country_news_sentiment": 5.0},
        {"date": "2026-06-23", "country_iso3": "CHN", "country_news_sentiment": 6.0},
    ]).to_parquet(panel, index=False)

    parts, start, end, loaded = norm._panel_parts(panel, mapping)
    tidy = pd.concat(parts, ignore_index=True)

    assert start == pd.Timestamp("2026-06-22")
    assert end == pd.Timestamp("2026-06-23")
    assert loaded == ["country_news_sentiment"]
    assert set(tidy["country"]) == {"Australia", "NASDAQ", "U.S.", "ChinaA", "ChinaH"}
    assert set(tidy["variable"]) == {"country_news_sentiment_CS", "country_news_sentiment_TS"}


def test_latest_master_gkg_date_parses_15_minute_masterfile(tmp_path):
    master = tmp_path / "masterfilelist.txt"
    master.write_text(
        "1 a http://data.gdeltproject.org/gdeltv2/20260622120000.export.CSV.zip\n"
        "2 b http://data.gdeltproject.org/gdeltv2/20260623121500.gkg.csv.zip\n"
        "3 c http://data.gdeltproject.org/gdeltv2/20260624140000.gkg.csv.zip\n"
    )

    assert refresh.latest_master_gkg_date(master) == date(2026, 6, 24)


def test_panel_max_date_reports_none_for_missing_panel(tmp_path):
    assert refresh.panel_max_date(tmp_path) is None


def test_daily_gdelt_scripts_do_not_use_csv_or_excel_storage():
    repo = Path(__file__).resolve().parents[1]
    scripts = [
        repo / "scripts" / "refresh_gdelt_daily.py",
        repo / "scripts" / "gdelt_normalize_daily.py",
        repo / "scripts" / "gdelt_optimizer_daily.py",
    ]
    forbidden = ("read_csv(", "to_csv(", "read_excel(", "to_excel(", "ExcelWriter(", "openpyxl")
    for script in scripts:
        text = script.read_text()
        hits = [token for token in forbidden if token in text]
        assert not hits, f"{script.name} contains forbidden storage calls: {hits}"
