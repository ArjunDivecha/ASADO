#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REGIME_EW_ROOT = Path(__file__).resolve().parent
ASADO_ROOT = REGIME_EW_ROOT.parent
REGIME_ROOT = ASADO_ROOT / "regime"
sys.path.insert(0, str(ASADO_ROOT))

from regime_ew.src.ew_model import (  # noqa: E402
    HMM_PARAMS_DIR,
    RESULTS_DIR,
    build_country_feature_panels,
    country_slug,
    ensure_dirs,
    gate1_persistence,
    gate2_volatility,
    gate3_lead,
    gate4_robustness,
    plot_outputs,
    run_full_sample_country,
    run_walk_forward_country,
    select_feature_set,
    write_results_md,
)

from regime.src.data_loader import (  # noqa: E402
    build_forward_returns,
    list_t2_factor_variables,
    load_country_returns,
    load_factor_panel,
)
from regime.src.utils import T2_COUNTRIES  # noqa: E402


def _json_default(obj):
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        val = float(obj)
        return None if not np.isfinite(val) else val
    if isinstance(obj, float):
        return None if not np.isfinite(obj) else obj
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    return str(obj)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, default=_json_default))


def _write_country_params(country: str, payload: dict) -> None:
    _write_json(HMM_PARAMS_DIR / f"{country_slug(country)}.json", payload)


def _status_after_gate(gate_name: str) -> str:
    return f"FAIL - stopped at {gate_name}"


def run(full_sample_only: bool = False, continue_after_fail: bool = False) -> dict:
    ensure_dirs()

    available = list_t2_factor_variables()
    features = select_feature_set(available)
    factor_panel = load_factor_panel()
    factor_panel = factor_panel[factor_panel["factor"].isin(features)].copy()
    returns = load_country_returns(("1MRet", "3MRet"))
    returns["date"] = pd.to_datetime(returns["date"]).dt.to_period("M").dt.to_timestamp()
    returns_1m_by_country = {
        country: build_forward_returns(returns[returns["country"] == country], "1MRet")
        for country in T2_COUNTRIES
    }
    panels = build_country_feature_panels(factor_panel, features, T2_COUNTRIES)

    manifest: dict = {
        "status": "running",
        "overall_status": "running",
        "features": features,
        "countries": T2_COUNTRIES,
        "conventions": {
            "return_alignment": "signal[t] pairs with build_forward_returns 1MRet[t]/3MRet[t]",
            "standardization": "per-country expanding z-score, min 24 months",
            "walk_forward": "annual refit; train on dates before prediction year",
            "adverse_state_mapping": "training-window forward 1MRet state mean, rank 0 is worst/adverse",
        },
        "gates": {},
    }

    full_signals = []
    params_by_country = {}
    for country in T2_COUNTRIES:
        sig, params = run_full_sample_country(
            country,
            panels[country],
            returns_1m_by_country[country],
            features,
        )
        if params:
            params_by_country[country] = {"country": country, "features": features, "full_sample": params}
        else:
            params_by_country[country] = {
                "country": country,
                "features": features,
                "full_sample": {"status": "insufficient_data", "n_obs": int(len(panels[country]))},
            }
        if not sig.empty:
            full_signals.append(sig)

    full_sample_summary = None
    if full_signals:
        full_df = pd.concat(full_signals, ignore_index=True).sort_values(["country", "date"])
        full_df.to_parquet(RESULTS_DIR / "ew_signals_full_sample.parquet", index=False)
        full_gate3_rows, full_sample_summary = gate3_lead(full_df, returns, T2_COUNTRIES)
        full_gate3_rows.to_parquet(RESULTS_DIR / "gate3_lead_full_sample_diagnostic.parquet", index=False)
        manifest["full_sample_diagnostic"] = full_sample_summary
    else:
        manifest["full_sample_diagnostic"] = {"status": "no_full_sample_signals"}

    if full_sample_only:
        for country, payload in params_by_country.items():
            _write_country_params(country, payload)
        manifest["status"] = "complete"
        manifest["overall_status"] = "FULL_SAMPLE_ONLY"
        _write_json(RESULTS_DIR / "manifest.json", manifest)
        write_results_md(manifest, features, full_sample_summary)
        return manifest

    wf_signals = []
    for country in T2_COUNTRIES:
        sig, fit_records = run_walk_forward_country(
            country,
            panels[country],
            returns_1m_by_country[country],
            features,
        )
        params_by_country.setdefault(country, {"country": country, "features": features})
        params_by_country[country]["walk_forward"] = {
            "fit_records": fit_records,
            "n_signal_rows": int(len(sig)),
        }
        if not sig.empty:
            wf_signals.append(sig)

    for country, payload in params_by_country.items():
        _write_country_params(country, payload)

    if not wf_signals:
        manifest["status"] = "complete"
        manifest["overall_status"] = "FAIL - no walk-forward signals"
        _write_json(RESULTS_DIR / "manifest.json", manifest)
        write_results_md(manifest, features, full_sample_summary)
        return manifest

    signals = pd.concat(wf_signals, ignore_index=True).sort_values(["country", "date"])
    signals.to_parquet(RESULTS_DIR / "ew_signals.parquet", index=False)

    gate1_rows, gate1_summary = gate1_persistence(signals, T2_COUNTRIES)
    gate1_rows.to_parquet(RESULTS_DIR / "gate1_persistence.parquet", index=False)
    manifest["gates"]["gate1_persistence"] = gate1_summary
    if not gate1_summary["pass"] and not continue_after_fail:
        manifest["status"] = "complete"
        manifest["overall_status"] = _status_after_gate("Gate 1 persistence")
        _write_json(RESULTS_DIR / "manifest.json", manifest)
        write_results_md(manifest, features, full_sample_summary)
        plot_outputs(signals, None)
        return manifest

    gate2_rows, gate2_summary = gate2_volatility(signals, returns, T2_COUNTRIES)
    gate2_rows.to_parquet(RESULTS_DIR / "gate2_volatility.parquet", index=False)
    manifest["gates"]["gate2_volatility"] = gate2_summary

    gate3_rows, gate3_summary = gate3_lead(signals, returns, T2_COUNTRIES)
    gate3_rows.to_parquet(RESULTS_DIR / "gate3_lead.parquet", index=False)
    manifest["gates"]["gate3_lead"] = gate3_summary
    plot_outputs(signals, gate3_rows)
    if not gate3_summary["pass"] and not continue_after_fail:
        manifest["status"] = "complete"
        manifest["overall_status"] = _status_after_gate("Gate 3 own-country lead")
        _write_json(RESULTS_DIR / "manifest.json", manifest)
        write_results_md(manifest, features, full_sample_summary)
        return manifest

    gate4_rows, gate4_summary = gate4_robustness(signals, returns, T2_COUNTRIES, gate3_summary)
    gate4_rows.to_parquet(RESULTS_DIR / "gate4_robustness.parquet", index=False)
    manifest["gates"]["gate4_robustness"] = gate4_summary
    if not gate4_summary["pass"]:
        manifest["overall_status"] = _status_after_gate("Gate 4 robustness")
    elif gate1_summary["pass"] and gate3_summary["pass"]:
        manifest["overall_status"] = "PASS"
    else:
        manifest["overall_status"] = "FAIL"

    manifest["status"] = "complete"
    _write_json(RESULTS_DIR / "manifest.json", manifest)
    write_results_md(manifest, features, full_sample_summary)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the per-country regime early-warning PRD test.")
    parser.add_argument("--full-sample-only", action="store_true", help="Run only the leaked diagnostic full-sample HMM pass.")
    parser.add_argument(
        "--continue-after-fail",
        action="store_true",
        help="Compute later diagnostics even after a hard gate fails. Default follows the PRD stop rule.",
    )
    args = parser.parse_args()
    manifest = run(full_sample_only=args.full_sample_only, continue_after_fail=args.continue_after_fail)
    print(json.dumps({"overall_status": manifest["overall_status"], "features": manifest["features"]}, indent=2))


if __name__ == "__main__":
    main()
