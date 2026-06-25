"""Tests for forward_track (PR-2B): single-country readouts, idempotency, surface whitelist."""
from __future__ import annotations

import pandas as pd
import pytest

from scripts.discovery_triage.forward_track import (
    RETURN_SURFACES,
    resolve_return_surface,
    run_forward_track,
)
from scripts.discovery_triage.route_claim import route_claim


def _claim():
    return {
        "claim_id": "C_20270625_001",
        "links": {"hypothesis_id": "H_20270625_001"},
        "target_country": "Brazil",
        "target": {"return_surface": "country_returns_daily",
                   "measurement_shape": "single_country_event", "direction": "long_high_signal"},
    }


def _returns():
    # 25 business days from 2027-02-02 for 3 countries (start_date today < these).
    dates = pd.bdate_range("2027-02-02", periods=25)
    rows = []
    for country, r in [("Brazil", 0.002), ("Chile", 0.0), ("Korea", -0.001)]:
        for d in dates:
            rows.append({"date": str(d.date()), "country": country, "ret": r})
    return pd.DataFrame(rows)


def test_single_country_readout_matures_21d_only(tmp_path, monkeypatch):
    # route a killed claim -> graveyard roster, with start_date forced before the data
    import scripts.discovery_triage.route_claim as rc

    class _FakeDate:
        @staticmethod
        def today():
            import datetime
            return datetime.date(2027, 2, 1)

    monkeypatch.setattr(rc, "date", _FakeDate)
    graveyard = tmp_path / "graveyard.jsonl"
    prospective = tmp_path / "prospective.jsonl"
    route_claim(_claim(), "killed_fatal_leakage",
                prospective_path=prospective, graveyard_path=graveyard)

    df = _returns()
    returns_for = lambda s: df if s == "country_returns_daily" else (_ for _ in ()).throw(AssertionError())  # noqa: E731
    appended = run_forward_track(graveyard, "graveyard", returns_for)

    # Only 21d matures (25 obs); 63d and 252d are immature.
    assert len(appended) == 1
    r = appended[0]
    assert r["horizon_days"] == 21 and r["arm"] == "graveyard"
    assert r["measurement_shape"] == "single_country_event"
    assert r["relative_return"] > 0  # Brazil outperforms the cross-section
    assert r["n_countries_in_xs"] == 3

    # idempotent: a second run appends nothing
    assert run_forward_track(graveyard, "graveyard", returns_for) == []


def test_surface_whitelist_blocks_optimizer_surface():
    assert "country_returns_daily" in RETURN_SURFACES
    with pytest.raises(PermissionError):
        resolve_return_surface(None, "factor_returns_daily")
    with pytest.raises(PermissionError):
        resolve_return_surface(None, "combiner_scores_daily")
