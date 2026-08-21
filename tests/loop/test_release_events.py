#!/usr/bin/env python3
"""
Unit tests for the release-date-stamped economic surprise layer and event-study integration.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import pytest
import pandas as pd

from scripts.loop.loopdb import loop_connection, T2_UNIVERSE
from scripts.loop.event_study import preset_events


def test_release_events_tables_exist_and_non_empty():
    con = loop_connection()
    try:
        tables = [t[0] for t in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()]
        assert "release_events_daily" in tables
        assert "release_events_signals" in tables

        n_events = con.execute("SELECT COUNT(*) FROM release_events_daily").fetchone()[0]
        n_signals = con.execute("SELECT COUNT(*) FROM release_events_signals").fetchone()[0]
        assert n_events >= 40000
        assert n_signals >= 50000
    finally:
        con.close()


def test_release_events_invariants():
    con = loop_connection()
    try:
        # 1. Signal date must be >= release date (PIT invariant)
        bad_pit = con.execute("SELECT COUNT(*) FROM release_events_daily WHERE signal_date < release_date").fetchone()[0]
        assert bad_pit == 0

        # 2. All countries must be valid T2 countries
        countries = [r[0] for r in con.execute("SELECT DISTINCT country FROM release_events_daily").fetchall()]
        for c in countries:
            assert c in T2_UNIVERSE

        # 3. Concepts must cover the 10 core macro concepts
        concepts = set(r[0] for r in con.execute("SELECT DISTINCT concept FROM release_events_daily").fetchall())
        expected_concepts = {"cpi", "core_cpi", "ppi", "gdp", "unemp", "employment", "pmi", "ip", "retail_sales", "consumer_confidence"}
        assert expected_concepts.issubset(concepts)

        # 4. Winsorized z-scores must be in [-3.0, 3.0]
        out_of_bounds = con.execute("SELECT COUNT(*) FROM release_events_daily WHERE surprise_z < -3.001 OR surprise_z > 3.001").fetchone()[0]
        assert out_of_bounds == 0
    finally:
        con.close()


def test_event_study_release_presets():
    con = loop_connection()
    try:
        args = argparse.Namespace(threshold=1.5, agency=None, detector=None, category=None)

        # Test GDP hot preset
        df_gdp, anchor = preset_events(con, "release_gdp_hot", args)
        assert anchor == "next_day"
        assert not df_gdp.empty
        assert "date" in df_gdp.columns
        assert "country" in df_gdp.columns
        assert "sign" in df_gdp.columns

        # Test Sentiment hot preset
        df_sent, anchor_sent = preset_events(con, "release_sentiment_hot", args)
        assert anchor_sent == "next_day"
        assert not df_sent.empty

        # Test CPI hot preset (presumed sign = -1.0 for equity headwind)
        df_cpi, anchor_cpi = preset_events(con, "release_cpi_hot", args)
        assert anchor_cpi == "next_day"
        assert not df_cpi.empty
        assert (df_cpi["sign"] == -1.0).all()
    finally:
        con.close()
