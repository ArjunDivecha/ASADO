#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: tests/test_harness_v4.py
=============================================================================

INPUT FILES:
- None. Every fixture is built in-test from synthetic data. This suite NEVER
  opens Data/asado.duckdb or Data/loop/asado_loop.duckdb (contract rule).
- Reads the `main` git ref of scripts/harness/evaluate_signal.py via `git show`
  for the INV6 v3-vs-v4 equivalence check (source only, no execution against
  real data).

OUTPUT FILES:
- None (pure asserts; INV6 writes the v3 source to a private tempfile that it
  deletes).

VERSION: 1.0
LAST UPDATED: 2026-07-14
AUTHOR: Arjun Divecha (built by agent session, HARNESS-V4-HONEST-LEDGER-001)

DESCRIPTION:
The v4 harness known-answer + invariant suite (contract HARNESS-V4-HONEST-LEDGER-001).
Proves, on synthetic data with deterministic seeds:
  INV1  every daily evaluation carries a >= 1-trading-day execution embargo,
        including ZERO_LAG_SOURCES, and align_daily's window opens strictly
        after the signal date.
  INV2  a planted cross-sectional rank-IC is recovered within +/-20%.
  INV3  a pure timezone-echo signal scores |mean IC| < 0.005 under the v4
        (lag>=1) window BUT > 0.015 under the legacy lag-0 window (the
        discrimination, not just the null).
  INV4  the re-verdict ledger-integrity report catches new registrations /
        mismatched verdict counts / changed family N (reverdict_v4).
  INV5  the forward-return blacklist still refuses NMRet/NDRet-family predictors.
  INV6  monthly verdict behaviour is byte-identical between `main` (v3) and HEAD
        (v4) except for the additive execution_convention labeling field.
  INV7  the execution_convention block is present and valid, and the G4 checker
        rejects a JSON missing a field (negative fixture) and reports
        'G3 not yet run' when the sweep output is absent.

DEPENDENCIES:
- pytest, numpy, pandas (project venv).

USAGE:
  venv/bin/python -m pytest tests/test_harness_v4.py -q
  venv/bin/python -m pytest tests/ -k harness_v4 -q
=============================================================================
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.harness import evaluate_signal as ev  # noqa: E402
from scripts.harness import check_convention_labels as cc  # noqa: E402
from scripts.harness import reverdict_v4 as rv  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic fixtures (deterministic)
# ─────────────────────────────────────────────────────────────────────────────

def _daily_panel(rng, n_countries, n_dates, builder):
    """builder(a, R) fills R (dates x countries); returns (returns_df, signal_df)
    plus the raw R matrix + country list for the caller to build a signal."""
    dates = pd.bdate_range("2000-01-03", periods=n_dates)
    countries = [f"C{i:03d}" for i in range(n_countries)]
    return dates, countries


def _echo_fixture(n_countries=100, n_dates=4000, rho=0.6, idio=0.3, scale=0.01, seed=11):
    """Pure timezone-echo: a common cyclic lead-lag where country i's return
    echoes neighbour (i-1)'s previous-day shock, and the signal for i is
    neighbour (i-1)'s SAME-DAY return. Calibrated so the echo is visible only
    when the window opens at the signal's own close (lag 0), never one day out."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2000-01-03", periods=n_dates + 5)
    a = rng.normal(0, 1, size=(len(dates), n_countries))
    R = np.zeros((len(dates), n_countries))
    for t in range(1, len(dates)):
        lead_prev = a[t - 1, np.arange(n_countries) - 1]      # a_{i-1}(t-1)
        R[t, :] = (rho * lead_prev + np.sqrt(1 - rho**2) * a[t, :]
                   + idio * rng.normal(0, 1, n_countries))
    R *= scale                                                # realistic return magnitude
    S = R[:, np.arange(n_countries) - 1]                      # signal_i(t) = r_{i-1}(t)
    countries = [f"C{i:03d}" for i in range(n_countries)]
    ret_rows, sig_rows = [], []
    for k, d in enumerate(dates):
        for j, c in enumerate(countries):
            ret_rows.append((d, c, R[k, j]))
            sig_rows.append((d, c, S[k, j]))
    returns = pd.DataFrame(ret_rows, columns=["date", "country", "return_1m"])
    signal = pd.DataFrame(sig_rows, columns=["date", "country", "value"])
    return signal, returns


def _planted_ic_fixture(n_countries=50, n_dates=3000, target=0.05, seed=7):
    """A daily panel whose signal genuinely predicts the harness's lag-1/h-1
    forward window (return ROW k+2) at a known cross-sectional Spearman IC."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2000-01-03", periods=n_dates + 5)
    countries = [f"C{i:03d}" for i in range(n_countries)]
    R = rng.normal(0, 0.01, size=(len(dates), n_countries))
    # Spearman ~ (6/pi) arcsin(rho0/2); invert to place the target rank-IC.
    rho0 = 2 * np.sin(np.pi / 6 * target)
    ret_rows, sig_rows = [], []
    for k, d in enumerate(dates):
        for j, c in enumerate(countries):
            ret_rows.append((d, c, R[k, j]))
    for k in range(len(dates) - 2):
        future = R[k + 2, :]                                  # lag1,h1 window return
        zf = (future - future.mean()) / (future.std() + 1e-12)
        noise = rng.normal(0, 1, n_countries)
        sig = rho0 * zf + np.sqrt(max(1 - rho0**2, 0.0)) * noise
        for j, c in enumerate(countries):
            sig_rows.append((dates[k], c, sig[j]))
    returns = pd.DataFrame(ret_rows, columns=["date", "country", "return_1m"])
    signal = pd.DataFrame(sig_rows, columns=["date", "country", "value"])
    return signal, returns, target


def _monthly_fixture(n_countries=34, n_months=140, seed=3):
    """First-of-month synthetic panel with a mild cross-sectional predictive
    signal so the monthly portfolio/IC/DSR branches all produce real numbers."""
    rng = np.random.default_rng(seed)
    months = pd.date_range("2008-01-01", periods=n_months, freq="MS")
    countries = [f"C{i:02d}" for i in range(n_countries)]
    fut = rng.normal(0, 0.05, size=(n_months, n_countries))   # month m return
    ret_rows, sig_rows = [], []
    for k, d in enumerate(months):
        for j, c in enumerate(countries):
            ret_rows.append((d, c, fut[k, j]))
    for k in range(n_months - 1):
        nxt = fut[k + 1, :]
        z = (nxt - nxt.mean()) / (nxt.std() + 1e-12)
        sig = 0.35 * z + np.sqrt(1 - 0.35**2) * rng.normal(0, 1, n_countries)
        for j, c in enumerate(countries):
            sig_rows.append((months[k], c, sig[j]))
    returns = pd.DataFrame(ret_rows, columns=["date", "country", "return_1m"])
    signal = pd.DataFrame(sig_rows, columns=["date", "country", "value"])
    return signal, returns


# ─────────────────────────────────────────────────────────────────────────────
# INV1 — daily execution embargo floor (>= 1 for all daily sources)
# ─────────────────────────────────────────────────────────────────────────────

def test_inv1_daily_execution_embargo_floor_for_zero_lag_sources():
    # Every ZERO_LAG_SOURCE resolves to an EFFECTIVE daily lag >= 1 under v4,
    # even though its PUBLICATION lag stays 0 (unchanged, still honest).
    for src in sorted(ev.ZERO_LAG_SOURCES):
        assert ev.daily_publication_lag_days("ANY", src, {}) == 0            # publication unchanged
        assert ev.effective_daily_lag_days("ANY", src, {}) >= 1              # execution embargo (INV1)
    # An explicit publication_lag_days=0 override is still floored to >= 1.
    assert ev.effective_daily_lag_days("ANY", "t2", {"publication_lag_days": 0}) >= 1
    # A larger publication/override lag is preserved (max wins).
    assert ev.effective_daily_lag_days("ANY", "epu", {"publication_lag_days": 4}) == 4


def test_inv1_align_daily_window_opens_strictly_after_signal_date():
    # With the v4 effective lag for a zero-lag source, align_daily's window start
    # index strictly exceeds the signal date's position (start = p + lag > p).
    dates = pd.date_range("2020-01-01", periods=12, freq="B")
    rets = np.zeros(12)
    rets[6] = 0.10                                     # move lands one day after signal date
    returns = pd.DataFrame({"date": dates, "country": "Brazil", "return_1m": rets})
    signal = pd.DataFrame({"date": [dates[5]], "country": ["Brazil"], "value": [1.0]})  # t = idx 5
    lag = ev.effective_daily_lag_days("MOM", "t2", {})
    assert lag >= 1
    aligned = ev.align_daily(signal, returns, horizon_days=1, lag_days=lag)
    # lag >= 1 embargoes the t+1 (index 6) move -> fwd is the flat t+2 window.
    assert abs(float(aligned["fwd_return"].iloc[0])) < 1e-9
    # And the same fixture WITHOUT the embargo (lag 0) would have captured it,
    # proving the floor is what moved the window off the signal's own close.
    leaky = ev.align_daily(signal, returns, horizon_days=1, lag_days=0)
    assert abs(float(leaky["fwd_return"].iloc[0]) - 0.10) < 1e-9


# ─────────────────────────────────────────────────────────────────────────────
# INV2 — known-answer: planted cross-sectional IC recovered within +/-20%
# ─────────────────────────────────────────────────────────────────────────────

def test_inv2_planted_ic_recovered_within_tolerance():
    signal, returns, target = _planted_ic_fixture()
    aligned = ev.align_daily(signal, returns, horizon_days=1,
                             lag_days=ev.effective_daily_lag_days("X", "t2", {}))
    ic = ev.rank_ic_series(aligned)
    recovered = float(ic.mean())
    assert len(ic) > 2000
    assert 0.80 * target <= recovered <= 1.20 * target, \
        f"recovered {recovered:.4f} outside +/-20% of planted {target}"


# ─────────────────────────────────────────────────────────────────────────────
# INV3 — echo exclusion (near-zero at v4, materially positive at legacy lag 0)
# ─────────────────────────────────────────────────────────────────────────────

def test_inv3_echo_excluded_at_v4_but_present_at_legacy_lag0():
    signal, returns = _echo_fixture()
    v4_lag = ev.effective_daily_lag_days("ECHO", "t2", {})     # == 1
    assert v4_lag >= 1
    ic_v4 = ev.rank_ic_series(ev.align_daily(signal, returns, horizon_days=1, lag_days=v4_lag))
    ic_legacy = ev.rank_ic_series(ev.align_daily(signal, returns, horizon_days=1, lag_days=0))
    mean_v4 = float(ic_v4.mean())
    mean_legacy = float(ic_legacy.mean())
    assert abs(mean_v4) < 0.005, f"v4 echo IC not near-zero: {mean_v4:.5f}"
    assert mean_legacy > 0.015, f"legacy lag-0 echo IC not materially positive: {mean_legacy:.5f}"
    # The discrimination itself: the leak is far larger under the old window.
    assert mean_legacy > 3 * abs(mean_v4)


# ─────────────────────────────────────────────────────────────────────────────
# INV4 — re-verdict ledger integrity (synthetic event lists, no DB)
# ─────────────────────────────────────────────────────────────────────────────

def _synthetic_ledger():
    """A tiny hand-built hypothesis ledger: 3 registrations in 2 families, each
    with one verdict."""
    return [
        {"event": "hyp_register", "hypothesis_id": "H1", "family_key": "famA"},
        {"event": "hyp_register", "hypothesis_id": "H2", "family_key": "famA"},
        {"event": "hyp_register", "hypothesis_id": "H3", "family_key": "famB"},
        {"event": "hyp_verdict", "hypothesis_id": "H1", "verdict": "WATCH"},
        {"event": "hyp_verdict", "hypothesis_id": "H2", "verdict": "DEAD"},
        {"event": "hyp_verdict", "hypothesis_id": "H3", "verdict": "WEAK"},
    ]


def test_inv4_ledger_integrity_report_passes_on_clean_reverdict():
    before = _synthetic_ledger()
    # a clean re-verdict: one NEW verdict event per re-run id, no new registration
    after = before + [
        {"event": "hyp_verdict", "hypothesis_id": "H1", "verdict": "DEAD"},
        {"event": "hyp_verdict", "hypothesis_id": "H2", "verdict": "DEAD"},
        {"event": "hyp_verdict", "hypothesis_id": "H3", "verdict": "WEAK"},
    ]
    rep = rv.ledger_integrity_report(before, after, ["H1", "H2", "H3"])
    assert rep["ok"], rep["checks"]
    assert rep["new_register_events"] == 0
    assert rep["new_verdict_events"] == 3


def test_inv4_ledger_integrity_report_flags_new_registration():
    before = _synthetic_ledger()
    after = before + [
        {"event": "hyp_register", "hypothesis_id": "H4", "family_key": "famA"},  # illegal
        {"event": "hyp_verdict", "hypothesis_id": "H1", "verdict": "DEAD"},
    ]
    rep = rv.ledger_integrity_report(before, after, ["H1"])
    assert not rep["ok"]
    assert rep["checks"]["no_new_registrations"] is False
    assert rep["checks"]["per_family_registration_counts_unchanged"] is False


def test_inv4_ledger_integrity_report_flags_verdict_count_mismatch():
    before = _synthetic_ledger()
    after = before + [{"event": "hyp_verdict", "hypothesis_id": "H1", "verdict": "DEAD"}]
    # claim two re-run ids but only one verdict landed
    rep = rv.ledger_integrity_report(before, after, ["H1", "H2"])
    assert not rep["ok"]
    assert rep["checks"]["new_verdicts_match_reverdicted"] is False


# ─────────────────────────────────────────────────────────────────────────────
# INV5 — forward-return blacklist still refuses NMRet/NDRet predictors
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("variable", sorted(ev.FORWARD_RETURN_VARIABLES))
def test_inv5_blacklist_refuses_forward_return_variable(variable):
    # The guard is the first line of load_signal, BEFORE any DB access, so we
    # can pass con=None: a blacklisted variable must raise, never proceed.
    with pytest.raises(ValueError, match="FORWARD|lookahead|optimizer target"):
        ev.load_signal(None, {"table": "feature_panel", "variable": variable},
                       ["U.S."], "2008-01-01", "daily")


def test_inv5_blacklist_allows_non_forward_variable_past_the_guard():
    # A non-blacklisted variable must NOT trip the forward-return guard (it will
    # fail later for other reasons with con=None; the point is the guard lets it by).
    with pytest.raises(Exception) as ei:
        ev.load_signal(None, {"table": "feature_panel", "variable": "12-1MTR_CS"},
                       ["U.S."], "2008-01-01", "daily")
    assert "FORWARD" not in str(ei.value) and "lookahead" not in str(ei.value)


# ─────────────────────────────────────────────────────────────────────────────
# INV6 — monthly v3-vs-v4 equivalence (byte-identical minus labeling fields)
# ─────────────────────────────────────────────────────────────────────────────

def _main_is_already_v4() -> bool:
    """Post-merge lifecycle guard: once exp/harness-v4 is merged, main IS v4 and
    the v3 comparison baseline no longer exists. The INV6 equivalence was proven
    and recorded pre-merge (contract HARNESS-V4-HONEST-LEDGER-001, 279-green run
    of 2026-07-14); these tests skip rather than fail tautologically."""
    src = subprocess.check_output(
        ["git", "-C", str(BASE_DIR), "show", "main:scripts/harness/evaluate_signal.py"],
        text=True)
    return "effective_daily_lag_days" in src


def _load_v3_module():
    """Load `main`'s (v3) evaluate_signal.py as an isolated module for comparison."""
    src = subprocess.check_output(
        ["git", "-C", str(BASE_DIR), "show", "main:scripts/harness/evaluate_signal.py"],
        text=True)
    if "effective_daily_lag_days" in src:
        pytest.skip("main already merged to v4 - v3 baseline gone; equivalence "
                    "proven pre-merge (see contract ledger)")
    assert "execution_convention" not in src, "main already contains v4 changes"
    tmp = tempfile.NamedTemporaryFile("w", suffix="_ev_v3.py", delete=False)
    tmp.write(src)
    tmp.close()
    spec = importlib.util.spec_from_file_location("ev_v3_main", tmp.name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ev_v3_main"] = mod
    spec.loader.exec_module(mod)
    mod.__source_tmpfile = tmp.name  # for cleanup
    return mod


def _monthly_pipeline(mod, signal, returns, direction="higher_is_better",
                      horizons=(1, 3, 6), lag=1, n_trials=5):
    """Reproduce evaluate_signal's monthly compute using `mod`'s functions only
    (no I/O). Returns the verdict-relevant outputs, minus labeling fields."""
    ic_block = {}
    for h in horizons:
        aligned = mod.align_monthly(signal, returns, lag, h)
        ic = mod.rank_ic_series(aligned)
        yearly = mod.yearly_ic_table(ic)
        pct = float(np.mean([v > 0 for v in yearly.values()])) if yearly else None
        ic_block[f"{h}m"] = {
            "mean_ic": round(float(ic.mean()), 4) if len(ic) else None,
            "nw_t": round(mod.nw_tstat(ic, max_lag=h), 3) if len(ic) else None,
            "n_dates": int(len(ic)),
            "pct_positive_years": round(pct, 3) if pct is not None else None,
            "yearly_ic": yearly,
        }
    aligned_1m = mod.align_monthly(signal, returns, lag, 1)
    port = mod.backtest_monthly(aligned_1m, direction, n_top=7, min_cross_section=14)
    dsr = {}
    if "_ls_gross_series" in port:
        ls = port.pop("_ls_gross_series")
        port.pop("_subperiods_src", None)
        dsr = mod.deflated_sharpe_block(ls, n_trials, periods_per_year=12)
    else:
        port.pop("_ls_gross_series", None)
        port.pop("_subperiods_src", None)
    prim = ic_block["1m"]
    metrics = {
        "coverage_fail": False, "history_fail": False,
        "primary_nw_t": prim["nw_t"], "pct_positive_years": prim["pct_positive_years"],
        "ls_sharpe_gross": port.get("gross", {}).get("ls_sharpe"),
        "top_excess_gross": port.get("gross", {}).get("excess_ann_return"),
        "deflated_sharpe": dsr.get("deflated_sharpe"),
        "portfolios_skipped": "error" in port or not port,
        "portfolio_error": port.get("error"),
    }
    verdict, notes = mod.decide_verdict(metrics, "monthly")
    return {"ic_block": ic_block, "portfolio": port, "dsr": dsr,
            "verdict": verdict, "gate_notes": notes}


def test_inv6_monthly_v3_v4_numeric_equivalence():
    v3 = _load_v3_module()
    try:
        signal, returns = _monthly_fixture()
        out_v3 = _monthly_pipeline(v3, signal, returns)
        out_v4 = _monthly_pipeline(ev, signal, returns)
        # Byte-identical (the pipeline emits no labeling field; those live only in
        # the full result dict, which is the documented INV6 exception).
        assert json.dumps(out_v3, sort_keys=True, default=str) == \
            json.dumps(out_v4, sort_keys=True, default=str)
        # sanity: the fixture actually exercised a real portfolio + verdict
        assert "error" not in out_v4["portfolio"]
        assert out_v4["verdict"] in {"WATCH", "WEAK", "DEAD"}
    finally:
        Path(getattr(v3, "__source_tmpfile", "/nonexistent")).unlink(missing_ok=True)


def test_inv6_monthly_helper_source_is_untouched():
    if _main_is_already_v4():
        pytest.skip("main already merged to v4 - v3 baseline gone; equivalence "
                    "proven pre-merge (see contract ledger)")
    """Every monthly-path helper is byte-identical between v3 (main) and v4 (HEAD)."""
    v3 = _load_v3_module()
    try:
        monthly_helpers = [
            "month_index", "align_monthly", "rank_ic_series", "nw_tstat",
            "yearly_ic_table", "backtest_monthly", "_breakeven_bps", "_ann_ret",
            "_sharpe", "subperiod_table", "expected_max_sharpe",
            "deflated_sharpe_block", "decide_verdict", "infer_publication_lag",
        ]
        for fn in monthly_helpers:
            assert inspect.getsource(getattr(v3, fn)) == inspect.getsource(getattr(ev, fn)), \
                f"monthly helper {fn} changed between v3 and v4"
    finally:
        Path(getattr(v3, "__source_tmpfile", "/nonexistent")).unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# INV7 / G4 — execution_convention block present + valid; checker rejects gaps
# ─────────────────────────────────────────────────────────────────────────────

def test_inv7_execution_convention_daily_and_monthly_valid():
    daily = ev._execution_convention("daily", ev.effective_daily_lag_days("X", "t2", {}), 0)
    monthly = ev._execution_convention("monthly", 0, 1)
    assert cc.validate_convention({"execution_convention": daily}) == []
    assert cc.validate_convention({"execution_convention": monthly}) == []
    assert daily["harness_version"] == ev.HARNESS_VERSION >= 4
    assert daily["lag_days_effective"] >= 1                      # INV1 stamped in the label
    assert monthly["lag_days_effective"] is None


def test_inv7_g4_checker_rejects_result_missing_a_convention_field():
    good = {"execution_convention": ev._execution_convention("daily", 1, 0)}
    # Drop one required field -> the schema checker must complain (negative fixture).
    for field in cc.REQUIRED_FIELDS:
        broken = {"execution_convention": {k: v for k, v in good["execution_convention"].items()
                                           if k != field}}
        problems = cc.validate_convention(broken)
        assert problems, f"checker failed to flag missing field {field}"
    # A daily run with a sub-1 lag (INV1 violation) is also rejected.
    bad_lag = {"execution_convention": {**good["execution_convention"], "lag_days_effective": 0}}
    assert cc.validate_convention(bad_lag)
    # Missing the whole block is rejected.
    assert cc.validate_convention({}) == ["missing execution_convention block"]


def test_g4_checker_reports_g3_not_run_when_output_absent(tmp_path):
    # Point the checker at an empty dir -> it must say the sweep has not run (exit 2).
    rc = cc.main([str(tmp_path)])
    assert rc == 2
    # And a totally absent path also yields exit 2.
    assert cc.main([str(tmp_path / "does_not_exist")]) == 2


def test_g4_checker_passes_on_valid_manifest(tmp_path):
    # Build a minimal sweep output dir with one valid daily result JSON.
    res = {"hypothesis_id": "H_x", "frequency": "daily",
           "execution_convention": ev._execution_convention("daily", 1, 0)}
    rj = tmp_path / "H_x_20260714_000000.json"
    rj.write_text(json.dumps(res))
    (tmp_path / "manifest.json").write_text(json.dumps({"result_files": [str(rj)]}))
    assert cc.main([str(tmp_path)]) == 0
    # A missing-field result in the manifest -> exit 1 (offender listed).
    bad = {"execution_convention": {"frequency": "daily", "harness_version": 4}}
    rj.write_text(json.dumps(bad))
    assert cc.main([str(tmp_path)]) == 1
