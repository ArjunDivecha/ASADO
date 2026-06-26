"""Tests for the triage battery (PR-2A): target-reentry (FATAL), power band, warnings."""
from __future__ import annotations

import pandas as pd

from scripts.discovery_triage.run_triage_probes import (
    country_region_jackknife,
    leave_one_crisis_out,
    power_budget_band,
    run_triage,
    target_reentry,
)


def _claim(variables, signal_table=None, shape="cross_sectional_rank_ic"):
    c = {"claim_id": "C_x", "variables": variables,
         "target": {"return_surface": "country_returns_daily", "measurement_shape": shape,
                    "direction": "long_high_signal"}}
    if signal_table:
        c["signal_spec"] = {"table": signal_table}
    return c


def test_target_reentry_fatal_on_forward_variable():
    p = target_reentry(_claim(["1MRet"]))
    assert p["status"] == "fail" and p["fatal"]


def test_target_reentry_fatal_on_forbidden_table():
    p = target_reentry(_claim(["FX_RR25_1M_Z252"], signal_table="combiner_scores_daily"))
    assert p["status"] == "fail"


def test_target_reentry_pass_on_clean_signal():
    p = target_reentry(_claim(["FX_RR25_1M_Z252"], signal_table="market_implied_signals"))
    assert p["status"] == "pass"


def test_run_triage_kills_on_fatal():
    res = run_triage(_claim(["1MRet"]))
    assert res["status"] == "killed_fatal_leakage"
    assert res["fatal_failures"]


def test_run_triage_passes_clean():
    res = run_triage(_claim(["FX_RR25_1M_Z252"]))
    assert res["status"] == "triage_passed_not_validated"


def test_target_reentry_fatal_on_forbidden_surface_in_sql():
    # H2: a forbidden surface inside a signal_spec.sql JOIN must be caught (substring,
    # not exact-match) — exact equality previously let this through.
    c = {"claim_id": "C_x", "variables": ["FX_RR25_1M_Z252"],
         "signal_spec": {"table": "market_implied_signals",
                         "sql": "SELECT z FROM market_implied_signals JOIN combiner_scores_daily USING(country)"},
         "target": {"return_surface": "country_returns_daily",
                    "measurement_shape": "cross_sectional_rank_ic", "direction": "long_high_signal"}}
    p = target_reentry(c)
    assert p["status"] == "fail" and p["fatal"]


def test_run_triage_fails_closed_on_empty_claim():
    # L2: a claim with no inspectable signal source must NOT pass vacuously.
    res = run_triage({"claim_id": "C_empty"})
    assert res["status"] == "killed_fatal_leakage"
    assert res["fatal_failures"]


def test_power_budget_band_is_band_not_verdict():
    df = pd.DataFrame(0.0, index=range(120), columns=[f"c{i}" for i in range(20)])
    band = power_budget_band(df, horizon_rows=21)
    assert band["detectable_ic_band"][0] <= band["detectable_ic_band"][1]
    assert "verdict" not in band
    assert band["conclusion"] == "advisory_band_not_a_verdict"


def test_crisis_and_jackknife_warnings():
    assert leave_one_crisis_out({"drop_covid": 0.01}, full_ic=0.05)["status"] == "warning"
    assert leave_one_crisis_out(None, None)["status"] == "not_run"
    assert country_region_jackknife({"Brazil": 0.9, "Chile": 0.1})["status"] == "warning"
    assert country_region_jackknife({"Brazil": 0.3, "Chile": 0.3, "Korea": 0.4})["status"] == "pass"
