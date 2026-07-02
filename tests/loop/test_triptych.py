#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: test_triptych.py
=============================================================================

INPUT FILES:
- None (synthetic arrays; no database or network access).

OUTPUT FILES:
- None (pytest assertions only).

VERSION: 1.0
LAST UPDATED: 2026-07-02
AUTHOR: Arjun Divecha (built by agent session, Triptych Prediction Prior Layer)

DESCRIPTION:
Unit + canary tests for the Triptych analytics kernel
(scripts/loop/triptych_kernel.py) and the scan's queue gates. The load-bearing
tests are the PIT no-lookahead canaries: bucket assignments at time t must be
COMPLETELY INSENSITIVE to any observation after t, and full-sample bucketing
must NOT have that property (proving the two modes actually differ).

DEPENDENCIES:
- pytest, numpy (project venv)

USAGE:
 venv/bin/python -m pytest tests/loop/test_triptych.py -q
=============================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.loop.triptych_kernel import (  # noqa: E402
    PIT_MIN_OBS,
    assign_bucket,
    assign_buckets_full,
    assign_buckets_pit,
    bucket_t_stat,
    cross_country_z,
    expanding_z,
    is_forbidden_signal,
    linear_fit,
    quantile,
    spearman_ic,
    thresholds_from_sorted,
)

rng = np.random.default_rng(42)


# --------------------------------------------------------------------------- #
# PIT no-lookahead canaries — the tests that matter
# --------------------------------------------------------------------------- #
class TestPITNoLookahead:
    def test_future_shock_cannot_move_past_buckets(self):
        """Append a massive future outlier: every already-assigned PIT bucket
        must stay identical. This is the definition of no lookahead."""
        base = rng.normal(0, 1, 120)
        shocked = np.concatenate([base, [50.0, -50.0, 40.0]])
        b_base, _ = assign_buckets_pit(base)
        b_shocked, _ = assign_buckets_pit(shocked)
        np.testing.assert_array_equal(b_base, b_shocked[: len(base)])

    def test_full_sample_is_sensitive_to_future(self):
        """Control: FULL-sample buckets MUST move when the future changes —
        otherwise the two modes are not actually different."""
        base = rng.normal(0, 1, 120)
        shocked = np.concatenate([base, np.full(30, 10.0)])
        b_base, _ = assign_buckets_full(base)
        b_shocked, _ = assign_buckets_full(shocked)
        assert not np.array_equal(b_base, b_shocked[: len(base)])

    def test_warmup_has_no_buckets(self):
        sig = rng.normal(0, 1, PIT_MIN_OBS + 10)
        buckets, _ = assign_buckets_pit(sig)
        assert (buckets[: PIT_MIN_OBS - 1] == 0).all()
        assert (buckets[PIT_MIN_OBS - 1:] > 0).all()

    def test_pit_threshold_uses_own_observation(self):
        """core.js inserts the record's own signal BEFORE assigning its bucket
        (binaryInsert then assign). Mirror check: the Nth record is bucketed
        against thresholds that include itself."""
        sig = np.arange(1.0, PIT_MIN_OBS + 1.0)  # strictly increasing
        buckets, _ = assign_buckets_pit(sig)
        # A strictly increasing series: each new max lands in the TOP bucket.
        assert buckets[PIT_MIN_OBS - 1] == 10

    def test_expanding_z_is_pit(self):
        """The expanding z at time t must not change when the future changes."""
        base = rng.normal(0, 1, 100)
        z1 = expanding_z(base)
        z2 = expanding_z(np.concatenate([base, [99.0]]))
        np.testing.assert_allclose(z1, z2[:100])


# --------------------------------------------------------------------------- #
# core.js parity units
# --------------------------------------------------------------------------- #
class TestKernelParity:
    def test_expanding_z_welford_population(self):
        """Population variance (m2/count), first obs -> 0, matches core.js."""
        vals = np.array([1.0, 2.0, 3.0])
        z = expanding_z(vals)
        assert z[0] == 0.0
        # after 2 obs: mean=1.5, pop var=0.25, std=0.5 -> (2-1.5)/0.5 = 1.0
        assert z[1] == pytest.approx(1.0)
        # after 3: mean=2, pop var=2/3 -> (3-2)/sqrt(2/3)
        assert z[2] == pytest.approx(1.0 / np.sqrt(2.0 / 3.0))

    def test_quantile_linear_interp(self):
        assert quantile([1, 2, 3, 4], 0.5) == pytest.approx(2.5)
        assert quantile([10], 0.9) == 10

    def test_thresholds_and_assignment(self):
        srt = sorted(range(1, 101))
        thr = thresholds_from_sorted(srt, 10)
        assert len(thr) == 9
        assert assign_bucket(0.5, thr) == 1
        assert assign_bucket(1000.0, thr) == 10
        assert assign_bucket(float("nan"), thr) is None
        assert assign_bucket(5.0, []) is None

    def test_cross_country_z_excludes_self(self):
        """Peer mean/std must exclude the country itself (core.js filter)."""
        piv = np.array([[1.0, 2.0, 3.0]])
        z = cross_country_z(piv)
        # For value 1: peers (2,3), mean 2.5, pop std 0.5 -> (1-2.5)/0.5 = -3
        assert z[0, 0] == pytest.approx(-3.0)
        assert z[0, 2] == pytest.approx((3 - 1.5) / 0.5)

    def test_cross_country_z_single_country_is_nan(self):
        z = cross_country_z(np.array([[5.0, np.nan, np.nan]]))
        assert np.isnan(z[0, 0])

    def test_bucket_t_stat_overlap_adjustment(self):
        vals = np.array([0.01, 0.02, 0.03, 0.02, 0.01, 0.02] * 4)
        t1 = bucket_t_stat(vals, 1)
        t12 = bucket_t_stat(vals, 12)
        assert t1 is not None and t12 is not None
        assert abs(t12) < abs(t1)          # n_eff shrinks with horizon
        assert bucket_t_stat(vals[:2], 1) is None

    def test_spearman_ic_perfect_monotone(self):
        sig = np.arange(20.0)
        ic, t = spearman_ic(sig, sig * 2 + 1, 1)
        assert ic == pytest.approx(1.0)
        assert spearman_ic(sig[:5], sig[:5], 1) == (None, None)

    def test_linear_fit(self):
        slope, icept, r2 = linear_fit([1, 2, 3, 4], [2, 4, 6, 8])
        assert slope == pytest.approx(2.0)
        assert icept == pytest.approx(0.0)
        assert r2 == pytest.approx(1.0)
        assert linear_fit([1], [2]) == (None, None, None)

    def test_forbidden_forward_returns(self):
        """The house LOOKAHEAD TRAP: NMRet variables are refused as signals."""
        for bad in ("1MRet", "3MRet", "6MRet", "9MRet", "12MRet", "21DRet"):
            assert is_forbidden_signal(bad), bad
        for ok in ("12-1MTR", "1MTR", "12MTR", "REER", "Tot Return Index"):
            assert not is_forbidden_signal(ok), ok


# --------------------------------------------------------------------------- #
# Scan-level checks (config + queue gates + confidence rules)
# --------------------------------------------------------------------------- #
class TestScanRules:
    def test_config_parses_and_declares_grid(self):
        import yaml
        cfg = yaml.safe_load((BASE_DIR / "config" / "triptych_scan.yaml").read_text())
        assert cfg["return_variable"] == "Tot Return Index"
        assert set(cfg["normalizations"]) == {"raw", "history_z", "cross_var_pct"}
        assert set(cfg["return_modes"]) == {"absolute", "relative"}
        assert all(h in {1, 3, 6, 12, 24, 36} for h in cfg["horizons"])
        # every declared warehouse factor names a real main-DB table
        allowed = {"external_factors", "extended_factors", "imf_factors",
                   "macrostructure_factors", "bloomberg_factors"}
        for spec in cfg["warehouse_factors"]:
            assert spec["table"] in allowed, spec

    def test_full_sample_confidence_is_zero(self):
        """Full-sample rows may NEVER carry prior confidence (descriptive only)."""
        import pandas as pd
        from scripts.loop.build_triptych_scan import finalize, load_config
        cfg = load_config()
        row = {
            "threshold_mode": "full", "n_records": 100, "current_signal": 1.0,
            "current_decile": 10, "bucket1_avg": -0.05, "bucket10_avg": 0.05,
            "spread_top_minus_bottom": 0.10, "slope_per_bucket": 0.01,
            "r_squared": 0.9, "ic_spearman": 0.3, "ic_t_stat": 4.0,
            "cur_bucket_n": 20, "cur_bucket_avg_fwd": 0.05,
            "cur_bucket_hit_rate": 0.9, "cur_bucket_t_stat": 3.0,
            "implied_direction": "long", "aligned": 1, "sample_score": 1.0,
            "ic_score": 1.0, "hit_score": 0.8,
            "factor": "X", "factor_table": "t2_raw", "country": "Brazil",
            "normalization": "raw", "return_mode": "absolute", "horizon_months": 12,
        }
        pit_row = dict(row, threshold_mode="pit")
        out = finalize(pd.DataFrame([row, pit_row]), "2026-07", cfg)
        full = out[out.threshold_mode == "full"].iloc[0]
        pit = out[out.threshold_mode == "pit"].iloc[0]
        assert full.confidence_score == 0.0
        assert "descriptive" in full.confidence_notes
        assert pit.confidence_score > 0.0

    def test_queue_rejects_full_sample_and_weak_rows(self):
        import pandas as pd
        from scripts.loop.build_triptych_scan import build_queue, load_config
        cfg = load_config()
        strong = {
            "threshold_mode": "pit", "n_records": 200, "cur_bucket_n": 20,
            "ic_t_stat": 3.5, "r_squared": 0.8, "implied_direction": "long",
            "current_decile": 1, "confidence_score": 0.9,
            "country": "Brazil", "factor": "X",
        }
        cases = pd.DataFrame([
            strong,
            dict(strong, threshold_mode="full"),               # descriptive
            dict(strong, ic_t_stat=1.0),                       # weak IC
            dict(strong, current_decile=5),                    # mid-distribution
            dict(strong, n_records=30),                        # thin history
            dict(strong, implied_direction="insufficient"),    # no direction
        ])
        q = build_queue(cases, cfg)
        assert len(q) == 1
        assert q.iloc[0].threshold_mode == "pit"
        assert q.iloc[0].current_decile == 1

    def test_queue_dedupes_per_pair(self):
        import pandas as pd
        from scripts.loop.build_triptych_scan import build_queue, load_config
        cfg = load_config()
        base = {
            "threshold_mode": "pit", "n_records": 200, "cur_bucket_n": 20,
            "ic_t_stat": 3.5, "r_squared": 0.8, "implied_direction": "long",
            "current_decile": 1, "confidence_score": 0.9,
            "country": "Brazil", "factor": "X",
        }
        dup = pd.DataFrame([base, dict(base, confidence_score=0.5),
                            dict(base, country="Chile")])
        q = build_queue(dup, cfg)
        assert len(q) == 2                                     # one per (country,factor)
        assert set(q.country) == {"Brazil", "Chile"}


# --------------------------------------------------------------------------- #
# Chat routing (deterministic — no API key needed)
# --------------------------------------------------------------------------- #
class TestChatRouting:
    def _data(self):
        return {
            "meta": {"generated_ts": "2026-07-02T02:00:00"},
            "gap_engine": {"status": "missing", "as_of": None, "top": []},
            "governance": {"overall": "green", "dimensions": []},
            "triptych": {"status": "fresh", "as_of": "2026-07",
                         "queue": [{"country": "Taiwan", "factor": "Copper"}],
                         "by_country": {}},
        }

    def test_triptych_intent_routes_to_view(self):
        from cos_mockups.cos_chat_service import deterministic_answer
        for phrase in ("triptych", "Triptych priors", "the review queue",
                       "what does history say"):
            resp = deterministic_answer(phrase, self._data())
            assert resp is not None, phrase
            views = [a.view for a in resp.ui_actions if a.type == "focus_view"]
            assert views == ["triptych"], phrase
            assert "PRIOR" in resp.answer_html

    def test_analytical_question_falls_through(self):
        """A sentence merely mentioning triptych must NOT be swallowed by the
        nav intent (anchored fullmatch) — it belongs to the Opus path."""
        from cos_mockups.cos_chat_service import deterministic_answer
        resp = deterministic_answer(
            "why does the triptych prior disagree with the combiner on Taiwan?",
            self._data())
        assert resp is None or "PRIOR for triage" not in (resp.answer_html or "")
