#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: tests/test_family_ic_monitor.py
=============================================================================

INPUT FILES:
- None. Every fixture is built in-test from synthetic data OR from tiny
  temp files created under pytest's tmp_path. This suite NEVER opens the real
  Data/asado.duckdb or Data/loop/asado_loop.duckdb, and never reads the real
  status artifact (contract rule: synthetic-only unit tests).
- The INV1 planted-IC / planted-echo fixture builders are REUSED VERBATIM from
  tests/test_harness_v4.py (copied below with attribution) so the monitor's
  honest-clock alignment is tested on the identical known-answer inputs the
  harness itself uses.

OUTPUT FILES:
- None beyond pytest tmp_path scratch (temp DuckDB files + temp status JSON),
  all under the per-test tmp_path.

VERSION: 1.0
LAST UPDATED: 2026-07-14
AUTHOR: Arjun Divecha (built by agent session, contract FAMILY-IC-MONITOR-001)

DESCRIPTION:
Unit + fixture suite for scripts/loop/build_family_ic_monitor.py. Proves on
synthetic data with deterministic seeds:
  INV1  the monitor's member-IC alignment uses the harness-v4 honest clock:
        a planted-echo signal scores |IC| < 0.005 (and would leak at legacy
        lag 0), a planted-IC signal is recovered within +/-20%.
  INV2  fail-soft: nightly_step never raises on a poisoned input environment;
        the failure is logged loudly and it returns exit 2.
  INV3  durable-write idempotence: re-running the upsert on the same night
        leaves the row count unchanged and updates values; the module never
        writes the main warehouse.
  INV4  known-answer comparison logic: passes when the backfilled per-year
        means/correlation match the references, fails and names offending years
        otherwise.
  INV5  R-A gate state machine: exhaustive truth table incl. alternating signs,
        exactly-zero months, calendar gaps, and re-park after re-arm.
  INV6  write-surface confinement: a static scan of the module's write targets
        and a dynamic synthetic run leave only the durable loop table + the
        status artifact changed.

DEPENDENCIES: pytest, numpy, pandas, duckdb (project venv).

USAGE:
  venv/bin/python -m pytest tests/test_family_ic_monitor.py -q
=============================================================================
"""

from __future__ import annotations

import io
import json
import re
import tokenize
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest


def _code_only(src: str) -> str:
    """Return the module source with all string literals AND comments removed,
    so a static scan sees CODE (method calls, identifiers) and never the prose
    of docstrings/comments (which legitimately name forbidden surfaces)."""
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in (tokenize.STRING, tokenize.COMMENT):
            continue
        out.append(tok.string)
    return " ".join(out)

import sys
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.loop import build_family_ic_monitor as mon  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Fixture builders REUSED VERBATIM from tests/test_harness_v4.py (_echo_fixture,
# _planted_ic_fixture). Copied rather than imported to avoid import side effects
# of that module's harness sub-imports; the logic is byte-identical so INV1 is
# measured on the harness's own known-answer inputs.
# ─────────────────────────────────────────────────────────────────────────────
def _echo_fixture(n_countries=100, n_dates=4000, rho=0.6, idio=0.3, scale=0.01, seed=11):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2000-01-03", periods=n_dates + 5)
    a = rng.normal(0, 1, size=(len(dates), n_countries))
    R = np.zeros((len(dates), n_countries))
    for t in range(1, len(dates)):
        lead_prev = a[t - 1, np.arange(n_countries) - 1]
        R[t, :] = (rho * lead_prev + np.sqrt(1 - rho**2) * a[t, :]
                   + idio * rng.normal(0, 1, n_countries))
    R *= scale
    S = R[:, np.arange(n_countries) - 1]
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
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2000-01-03", periods=n_dates + 5)
    countries = [f"C{i:03d}" for i in range(n_countries)]
    R = rng.normal(0, 0.01, size=(len(dates), n_countries))
    rho0 = 2 * np.sin(np.pi / 6 * target)
    ret_rows, sig_rows = [], []
    for k, d in enumerate(dates):
        for j, c in enumerate(countries):
            ret_rows.append((d, c, R[k, j]))
    for k in range(len(dates) - 2):
        future = R[k + 2, :]
        zf = (future - future.mean()) / (future.std() + 1e-12)
        noise = rng.normal(0, 1, n_countries)
        sig = rho0 * zf + np.sqrt(max(1 - rho0**2, 0.0)) * noise
        for j, c in enumerate(countries):
            sig_rows.append((dates[k], c, sig[j]))
    returns = pd.DataFrame(ret_rows, columns=["date", "country", "return_1m"])
    signal = pd.DataFrame(sig_rows, columns=["date", "country", "value"])
    return signal, returns, target


# ─────────────────────────────────────────────────────────────────────────────
# INV1 — monitor alignment uses the harness-v4 honest clock
# ─────────────────────────────────────────────────────────────────────────────
def test_inv1_planted_ic_recovered_within_tolerance():
    signal, returns, target = _planted_ic_fixture()
    ic = mon.member_daily_ic(signal, returns, horizon_days=1,
                             direction="higher_is_better", source="t2", variable="X")
    recovered = float(ic.mean())
    assert len(ic) > 2000
    assert 0.80 * target <= recovered <= 1.20 * target, \
        f"recovered {recovered:.4f} outside +/-20% of planted {target}"


def test_inv1_echo_excluded_at_honest_clock_but_present_at_legacy_lag0():
    from scripts.harness.evaluate_signal import align_daily, rank_ic_series
    signal, returns = _echo_fixture()
    # monitor uses the honest clock (effective lag >= 1) -> echo near zero
    ic_mon = mon.member_daily_ic(signal, returns, horizon_days=1,
                                 direction="higher_is_better", source="graph", variable="ECHO")
    mean_mon = float(ic_mon.mean())
    assert abs(mean_mon) < 0.005, f"monitor echo IC not near-zero: {mean_mon:.5f}"
    # the SAME fixture at legacy lag 0 leaks materially -> proves the embargo the
    # monitor imports (not a reimplementation) is what moves the window off the
    # signal's own close.
    ic_legacy = rank_ic_series(align_daily(signal, returns, 1, 0))
    assert float(ic_legacy.mean()) > 0.015
    assert float(ic_legacy.mean()) > 3 * abs(mean_mon)


def test_inv1_effective_lag_is_at_least_one_for_all_member_sources():
    # Every source the roster uses resolves to an effective daily lag >= 1.
    for src in ("graph", None, "combiner", "t2", "gdelt"):
        assert mon.effective_daily_lag_days("ANY", src or "", {}) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic helpers for INV2 / INV3 / INV6 (no real DB)
# ─────────────────────────────────────────────────────────────────────────────
def _syn_daily_family():
    return {"frequency": "daily", "horizon_days": 1, "rosters": {
        "book_2026_07_14": {"role": "gate", "members": [
            {"variable": "SYN_A", "table": "syn_tbl", "source": None,
             "direction": "higher_is_better", "universe": None},
            {"variable": "SYN_B", "table": "syn_tbl", "source": None,
             "direction": "higher_is_better", "universe": None},
        ]}}}


def _syn_loaders(seed=1):
    """Loaders returning a small deterministic daily panel + per-member signal."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=80)
    countries = [f"C{i:02d}" for i in range(12)]
    R = rng.normal(0, 0.01, size=(len(dates), len(countries)))
    ret_rows, sig_rows = [], []
    for k, d in enumerate(dates):
        for j, c in enumerate(countries):
            ret_rows.append((d, c, R[k, j]))
            sig_rows.append((d, c, float(rng.normal())))
    returns = pd.DataFrame(ret_rows, columns=["date", "country", "return_1m"])
    sig = pd.DataFrame(sig_rows, columns=["date", "country", "value"])

    def returns_daily(con):
        return returns.copy()

    def returns_monthly(con):
        return pd.DataFrame(columns=["date", "country", "return_1m"])

    def member_signal(con, member):
        return sig.copy()

    return {"returns_daily": returns_daily, "returns_monthly": returns_monthly,
            "member_signal": member_signal}


# ─────────────────────────────────────────────────────────────────────────────
# INV2 — fail-soft: nightly_step never raises on a poisoned environment
# ─────────────────────────────────────────────────────────────────────────────
def test_inv2_nightly_step_is_fail_soft_on_poisoned_loader(tmp_path, caplog):
    con = duckdb.connect(str(tmp_path / "loop.duckdb"))
    try:
        def boom(con, member):
            raise RuntimeError("poisoned input: table missing")
        loaders = {**_syn_loaders(), "member_signal": boom}
        with caplog.at_level("ERROR"):
            rc = mon.nightly_step(con=con, loaders=loaders, families={"syn": _syn_daily_family()},
                                  status_path=tmp_path / "status.json",
                                  now=pd.Timestamp("2020-05-01"))
        assert rc == 2, "poisoned nightly step must return exit 2, not raise"
        assert any("FAILED" in r.message or "FAILED" in r.getMessage() for r in caplog.records), \
            "failure must be logged loudly"
    finally:
        con.close()


def test_inv2_nightly_step_graceful_on_empty_panel(tmp_path):
    con = duckdb.connect(str(tmp_path / "loop.duckdb"))
    try:
        empty = pd.DataFrame(columns=["date", "country", "value"])
        loaders = {**_syn_loaders(), "member_signal": lambda con, m: empty.copy()}
        rc = mon.nightly_step(con=con, loaders=loaders, families={"syn": _syn_daily_family()},
                              status_path=tmp_path / "status.json",
                              now=pd.Timestamp("2020-05-01"))
        assert rc == 0, "empty panel must not crash the step"
        assert (tmp_path / "status.json").exists()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────────────────────────
# INV3 — durable-write idempotence + no main-DB write
# ─────────────────────────────────────────────────────────────────────────────
def test_inv3_upsert_is_idempotent(tmp_path):
    con = duckdb.connect(str(tmp_path / "loop.duckdb"))
    try:
        months = pd.date_range("2020-01-01", periods=4, freq="MS")
        s1 = pd.Series([0.01, 0.02, -0.01, 0.03], index=months)
        nm = pd.Series([5, 5, 5, 5], index=months, dtype="Int64")
        mon.upsert_family_ic(con, "fam", "book_2026_07_14", "gate", s1, nm, "daily", "5d", "ts1")
        n1 = con.execute(f"SELECT count(*) FROM {mon.MONITOR_TABLE}").fetchone()[0]
        # second run, same night, UPDATED values -> row count unchanged, values updated
        s2 = s1 + 0.005
        mon.upsert_family_ic(con, "fam", "book_2026_07_14", "gate", s2, nm, "daily", "5d", "ts2")
        n2 = con.execute(f"SELECT count(*) FROM {mon.MONITOR_TABLE}").fetchone()[0]
        assert n1 == n2 == 4, f"upsert duplicated rows: {n1} -> {n2}"
        got = mon.read_family_ic(con, "fam", "book_2026_07_14")
        assert abs(float(got.iloc[0]) - 0.015) < 1e-9, "value not updated on re-upsert"
        # a DIFFERENT roster for the same family+month is a distinct row (PK includes roster)
        mon.upsert_family_ic(con, "fam", "ref16_frozen", "inv4_reference", s1, nm, "daily", "5d", "ts1")
        assert con.execute(f"SELECT count(*) FROM {mon.MONITOR_TABLE}").fetchone()[0] == 8
    finally:
        con.close()


def test_inv3_double_nightly_run_is_idempotent(tmp_path):
    con = duckdb.connect(str(tmp_path / "loop.duckdb"))
    try:
        kwargs = dict(con=con, loaders=_syn_loaders(), families={"syn": _syn_daily_family()},
                      status_path=tmp_path / "status.json", now=pd.Timestamp("2020-05-01"))
        assert mon.nightly_step(**kwargs) == 0
        n1 = con.execute(f"SELECT count(*) FROM {mon.MONITOR_TABLE}").fetchone()[0]
        assert mon.nightly_step(**kwargs) == 0
        n2 = con.execute(f"SELECT count(*) FROM {mon.MONITOR_TABLE}").fetchone()[0]
        assert n1 == n2 and n1 > 0, f"double nightly run changed row count: {n1} -> {n2}"
    finally:
        con.close()


def test_inv3_verify_idempotent_entrypoint_passes(tmp_path):
    # The G4 verifier (run-twice, assert equal row counts + status refresh) must
    # pass on a synthetic temp DB (drives the exact nightly step twice).
    con = duckdb.connect(str(tmp_path / "loop.duckdb"))
    try:
        rc = mon.verify_idempotent(con=con, loaders=_syn_loaders(),
                                   families={"syn": _syn_daily_family()},
                                   status_path=tmp_path / "status.json",
                                   now=pd.Timestamp("2020-05-01"), settle_s=0.05)
        assert rc == 0
    finally:
        con.close()


def test_inv3_module_never_writes_the_main_db():
    # Code-inspection: no write SQL (INSERT/UPDATE/DELETE/CREATE TABLE) targets a
    # main-warehouse (`asado.`-qualified) table, and the main DB is never opened
    # directly (all connections go through loop_connection / guarded_connect).
    src = Path(mon.__file__).read_text()
    for m in re.finditer(r'(INSERT\s+INTO|CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS|UPDATE|DELETE\s+FROM)\s+([A-Za-z0-9_\.{}]+)',
                         src, flags=re.IGNORECASE):
        assert "asado." not in m.group(2), f"write targets main warehouse: {m.group(0)}"
    code = _code_only(src)
    assert "duckdb.connect" not in code, "module must not open a DB directly (use loop_connection)"
    assert "read_only=False" in src  # the loop DB (only) is opened read-write


# ─────────────────────────────────────────────────────────────────────────────
# INV4 — known-answer comparison logic (synthetic references, no live DB)
# ─────────────────────────────────────────────────────────────────────────────
def _write_refs(tmp_path, per_year, pre_mean, monthly_series):
    a6 = tmp_path / "a6.json"
    a6.write_text(json.dumps({"lag1_per_year": {str(y): float(v) for y, v in per_year.items()},
                              "lag1_pre_mean": float(pre_mean)}))
    a2 = tmp_path / "a2.parquet"
    pd.DataFrame({"month": monthly_series.index, "family_ic": monthly_series.values}).to_parquet(a2)
    return a6, a2


def _flip_monthly(seed=0):
    """Month-indexed 2010-01..2026-06 series that is positive-ish pre-2024 and
    negative post-2024 (so the four INV4 clauses are all exercisable), with real
    month-to-month variation so a Pearson correlation is well defined."""
    months = pd.date_range("2010-01-01", "2026-06-01", freq="MS")
    rng = np.random.default_rng(seed)
    base = np.where(months.year < 2024, 0.02, -0.02)
    vals = base + 0.015 * np.sin(np.arange(len(months)) / 3.0) + rng.normal(0, 0.004, len(months))
    return pd.Series(vals, index=months)


def _refs_matching(tmp_path, series):
    per_year = series.groupby(series.index.year).mean().to_dict()
    pre = series[(series.index >= "2012-01-01") & (series.index < "2024-01-01")].mean()
    return _write_refs(tmp_path, per_year, pre, series)


def test_inv4_comparison_passes_on_matching_series(tmp_path):
    s = _flip_monthly()
    a6, a2 = _refs_matching(tmp_path, s)
    rep = mon.inv4_comparison(s.copy(), a6_path=a6, a2_path=a2)
    assert rep["ok"] is True, rep
    assert rep["n_offending_years"] == 0 and rep["corr_ok"] and rep["pre_ok"] and rep["post_ok"]
    assert rep["corr_vs_a2_monthly"] >= 0.95


def test_inv4_comparison_flags_offending_year(tmp_path):
    s = _flip_monthly()
    a6, a2 = _refs_matching(tmp_path, s)
    backfill = s.copy()
    backfill[backfill.index.year == 2015] += 0.02   # > per_year_tol 0.012
    rep = mon.inv4_comparison(backfill, a6_path=a6, a2_path=a2)
    assert rep["ok"] is False and 2015 in rep["offending_years"]
    assert rep["corr_vs_a2_monthly"] >= 0.95  # corr still fine; only per-year fails


def test_inv4_comparison_fails_on_low_correlation(tmp_path):
    s = _flip_monthly(seed=1)
    per_year = s.groupby(s.index.year).mean().to_dict()
    pre = s[(s.index >= "2012-01-01") & (s.index < "2024-01-01")].mean()
    noise = pd.Series(np.random.default_rng(3).normal(0, 0.05, len(s)), index=s.index)
    a6, a2 = _write_refs(tmp_path, per_year, pre, noise)   # a2 uncorrelated with backfill
    rep = mon.inv4_comparison(s.copy(), a6_path=a6, a2_path=a2)
    assert rep["n_offending_years"] == 0 and rep["pre_ok"] and rep["post_ok"]
    assert rep["corr_ok"] is False and rep["ok"] is False


def test_inv4_comparison_fails_on_pre_mean_mismatch(tmp_path):
    s = _flip_monthly()
    per_year = s.groupby(s.index.year).mean().to_dict()
    true_pre = s[(s.index >= "2012-01-01") & (s.index < "2024-01-01")].mean()
    # a6 pre-mean far off (> 0.001) while per-year still matches
    a6, a2 = _write_refs(tmp_path, per_year, true_pre + 0.01, s)
    rep = mon.inv4_comparison(s.copy(), a6_path=a6, a2_path=a2)
    assert rep["pre_ok"] is False and rep["ok"] is False
    assert rep["n_offending_years"] == 0 and rep["corr_ok"]


def test_inv4_comparison_fails_when_flip_absent(tmp_path):
    # An all-positive backfill (no post-2024 decay) fails clause (iv) even if the
    # references are made to match its per-year/pre.
    months = pd.date_range("2010-01-01", "2026-06-01", freq="MS")
    rng = np.random.default_rng(2)
    s = pd.Series(0.02 + 0.01 * np.sin(np.arange(len(months)) / 3.0) + rng.normal(0, 0.003, len(months)),
                  index=months)
    a6, a2 = _refs_matching(tmp_path, s)
    rep = mon.inv4_comparison(s.copy(), a6_path=a6, a2_path=a2)
    assert rep["post_2024_mean"] > 0 and rep["post_ok"] is False and rep["ok"] is False


# ─────────────────────────────────────────────────────────────────────────────
# INV5 — R-A gate state machine: exhaustive truth table
# ─────────────────────────────────────────────────────────────────────────────
def _points(seq, start="2020-01-01"):
    """Build (month, ic) points. seq entries: a float ic, or None to SKIP the
    month entirely (a calendar gap)."""
    months = pd.date_range(start, periods=len(seq), freq="MS")
    return [(m, v) for m, v in zip(months, seq) if v is not None]


@pytest.mark.parametrize("seq,exp_state,exp_consec", [
    ([], "parked", 0),                                   # empty
    ([0.01], "parked", 1),                               # one positive
    ([0.01, 0.02], "re-armed", 2),                       # two consecutive -> re-arm
    ([0.01, 0.02, 0.03], "re-armed", 3),                 # stays re-armed
    ([0.01, -0.01], "parked", 0),                        # positive then negative
    ([0.01, -0.01, 0.02], "parked", 1),                  # reset then one positive
    ([0.01, -0.01, 0.02, 0.02], "re-armed", 2),          # re-arm after a reset
    ([0.01, -0.01, 0.02, -0.02, 0.03, -0.03], "parked", 0),  # alternating never re-arms
    ([0.01, 0.0], "parked", 0),                          # exactly zero is non-positive
    ([0.01, 0.0, 0.02, 0.02], "re-armed", 2),            # zero resets, then re-arm
    ([0.01, 0.02, 0.0], "parked", 0),                    # re-park after re-arm via zero
    ([0.01, 0.02, -0.01], "parked", 0),                  # re-park after re-arm via negative
    ([0.01, 0.02, -0.01, 0.03, 0.04], "re-armed", 2),    # re-park then re-arm again
    ([1e-9], "parked", 1),                               # tiny positive counts
    ([float("nan")], "parked", 0),                       # NaN is non-positive
])
def test_inv5_gate_truth_table(seq, exp_state, exp_consec):
    res = mon.evaluate_gate(_points(seq))
    assert res["state"] == exp_state, f"{seq} -> {res}"
    assert res["consecutive_positive"] == exp_consec, f"{seq} -> {res}"


def test_inv5_calendar_gap_breaks_consecutive_chain():
    # Jan(+), [Feb missing], Mar(+): the gap resets the counter -> no re-arm.
    pts = [(pd.Timestamp("2020-01-01"), 0.01), (pd.Timestamp("2020-03-01"), 0.02)]
    res = mon.evaluate_gate(pts)
    assert res["state"] == "parked" and res["consecutive_positive"] == 1


def test_inv5_gap_reparks_a_rearmed_family():
    # Jan(+),Feb(+) -> re-armed; [Mar missing]; Apr(+): gap resets -> re-parked.
    pts = [(pd.Timestamp("2020-01-01"), 0.01), (pd.Timestamp("2020-02-01"), 0.02),
           (pd.Timestamp("2020-04-01"), 0.03)]
    res = mon.evaluate_gate(pts)
    assert res["state"] == "parked" and res["consecutive_positive"] == 1


def test_inv5_transitions_recorded_with_evidence_months():
    # +,+ (re-arm at m2), - (re-park at m3), +,+ (re-arm at m5)
    res = mon.evaluate_gate(_points([0.01, 0.02, -0.01, 0.03, 0.04]))
    trans = res["transitions"]
    assert [(t["from"], t["to"]) for t in trans] == \
        [("parked", "re-armed"), ("re-armed", "parked"), ("parked", "re-armed")]
    assert trans[0]["month"] == "2020-02-01" and trans[2]["month"] == "2020-05-01"


# ─────────────────────────────────────────────────────────────────────────────
# INV6 — write-surface confinement (static scan + dynamic synthetic run)
# ─────────────────────────────────────────────────────────────────────────────
def test_inv6_static_scan_of_write_targets():
    src = Path(mon.__file__).read_text()
    code = _code_only(src)  # strings + comments stripped -> CODE only, not prose
    # No forbidden write operations in code (method calls survive stripping;
    # forbidden path prose lives only in docstrings and is correctly removed).
    for forbidden in ("to_parquet", "to_csv", "ledgers", "family_registry"):
        assert forbidden not in code, f"module has a forbidden write operation: {forbidden}"
    # The only table written is the monitor table (loop DB, unqualified) -- SQL
    # lives in string literals, so scan the raw source for the DDL.
    created = re.findall(r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([A-Za-z0-9_{}]+)', src, re.IGNORECASE)
    assert created, "expected a CREATE TABLE for the monitor table"
    assert all("{MONITOR_TABLE}" in c or mon.MONITOR_TABLE in c for c in created)
    # The only durable file written is the status artifact, via an atomic rename.
    assert ".replace(status_path)" in src


def test_inv6_dynamic_run_touches_only_allowed_surfaces(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    loop_db = sandbox / "loop.duckdb"
    status = sandbox / "family_ic_status.json"
    con = duckdb.connect(str(loop_db))
    try:
        rc = mon.nightly_step(con=con, loaders=_syn_loaders(), families={"syn": _syn_daily_family()},
                              status_path=status, now=pd.Timestamp("2020-05-01"))
        assert rc == 0
    finally:
        con.close()
    # Only the loop DB (+ its wal) and the status JSON may exist in the sandbox.
    produced = {p.name for p in sandbox.iterdir()}
    allowed = {"loop.duckdb", "loop.duckdb.wal", "family_ic_status.json"}
    assert produced <= allowed, f"unexpected write surfaces created: {produced - allowed}"
    assert status.exists()
    # the durable table exists and has rows
    con = duckdb.connect(str(loop_db))
    try:
        assert con.execute(f"SELECT count(*) FROM {mon.MONITOR_TABLE}").fetchone()[0] > 0
    finally:
        con.close()


# ─────────────────────────────────────────────────────────────────────────────
# Roster sanity (deterministic v1 roster is intact)
# ─────────────────────────────────────────────────────────────────────────────
def test_roster_v1_two_roster_structure():
    fams = mon.monitored_families()
    assert set(fams) == {"network_spillover", "eco_surprise", "ml_combiner"}
    ns = fams["network_spillover"]
    assert ns["horizon_days"] == 5
    # gate roster = the 5 Book WATCH-tier members; ref16 = a6's 16 for INV4 only
    assert mon.gate_roster_name(ns) == "book_2026_07_14"
    assert len(ns["rosters"]["book_2026_07_14"]["members"]) == 5
    assert ns["rosters"]["book_2026_07_14"]["role"] == "gate"
    assert len(ns["rosters"]["ref16_frozen"]["members"]) == 16
    assert ns["rosters"]["ref16_frozen"]["role"] == "inv4_reference"
    # the Book 5 are a subset of ref16
    book = {m["variable"] for m in ns["rosters"]["book_2026_07_14"]["members"]}
    ref16 = {m["variable"] for m in ns["rosters"]["ref16_frozen"]["members"]}
    assert book < ref16
    # singleton families: gate roster only
    assert mon.gate_roster_name(fams["ml_combiner"]) == "book_2026_07_14"
    assert [m["variable"] for m in fams["ml_combiner"]["rosters"]["book_2026_07_14"]["members"]] \
        == ["COMBINER_RIDGE_DAILY_V1"]
    assert [m["variable"] for m in fams["eco_surprise"]["rosters"]["book_2026_07_14"]["members"]] \
        == ["ECO_INFL_SURPRISE_Z"]
    assert mon.KNOWN_ANSWER_ROSTER == "ref16_frozen"
