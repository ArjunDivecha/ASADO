"""Tests for the daily docket orchestration (PR-5+): robustness + nightly cost gate. Offline."""
from __future__ import annotations

import scripts.discovery_triage.daily_docket as dd


def _good_result():
    return {
        "drafts": [{
            "object_type": "detector_family_draft", "family_name": "Brazil",
            "epistemic_status": ["unvalidated", "tool_outcome_blind", "prospective_only_unknown_cutoff"],
            "card": {"summary": "FX skew relief while flows stay negative.",
                     "falsification": {"near_term": ["CDS widens within 21d"]},
                     "mythos_self_falsification": {"strongest_objection": "flow artifact",
                                                   "first_probe_to_run": "leave-one-crisis-out"}},
        }],
        "dropped": [], "route": "prospective_only_unknown_cutoff", "usage": None,
    }


def test_build_docket_robust_to_failing_search(tmp_path, monkeypatch):
    def fake_run(s, as_of, **kw):
        if s == "boom_search":
            raise RuntimeError("surface missing")
        return _good_result()

    monkeypatch.setattr(dd, "run_lab_session", fake_run)
    out, results = dd.build_docket("2026-06-24",
                                   ["cross_surface_contradiction", "boom_search"],
                                   dockets_dir=tmp_path)
    assert out.exists()
    text = out.read_text()
    assert "Brazil" in text                                   # the good search rendered
    assert "Skipped searches" in text and "boom_search" in text  # the bad one was skipped, not fatal
    assert any(r.get("error") for r in results)


def test_nightly_gate_no_ops_without_optin(monkeypatch, capsys):
    monkeypatch.delenv("ASADO_RUN_DISCOVERY_LAB", raising=False)
    rc = dd.main(["--nightly"])
    assert rc == 0                                             # no spend, clean exit
    assert "disabled" in capsys.readouterr().out
