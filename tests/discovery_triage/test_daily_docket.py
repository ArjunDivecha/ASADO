"""Tests for the daily docket orchestration (merge Phase 4): dedupe/rank/cap,
raw-vs-shown accounting, no-padding, robustness, and the nightly cost gate. Offline."""
from __future__ import annotations

import scripts.discovery_triage.daily_docket as dd


def _draft(family: str, members: int = 2, summary_len: int = 250):
    return {
        "object_type": "detector_family_draft", "family_name": family,
        "epistemic_status": ["unvalidated", "tool_outcome_blind", "prospective_only_unknown_cutoff"],
        "summary": "FX skew relief while flows stay negative; " + ("x" * summary_len),
        "members": [f"relationship {i}" for i in range(members)],
        "falsification": {"fatal_if": ["sovereign CDS widens"], "must_check": ["jackknife", "crisis"]},
        "mythos_self_falsification": {"strongest_counterargument": "flow artifact",
                                      "what_would_change_my_mind": ["decompose the basis"]},
    }


def test_curate_dedupes_ranks_and_caps():
    results = [{"drafts": [_draft("Brazil", 2), _draft("Brazil", 1), _draft("Chile", 3)],
                "dropped": [{"reason": "x"}]}]
    shown, meta = dd.curate(results)
    assert meta["raw"] == 3 and meta["collapsed"] == 1 and meta["shown"] == 2
    fams = [d["family_name"] for _, _, d in shown]
    assert fams.count("Brazil") == 1 and "Chile" in fams
    brazil = [d for _, _, d in shown if d["family_name"] == "Brazil"][0]
    assert len(brazil["members"]) == 2          # the richer Brazil wins the dedupe


def test_render_distinguishes_raw_from_shown():
    results = [{"drafts": [_draft("Brazil"), _draft("Brazil"), _draft("Chile")],
                "dropped": [{"reason": "forbidden"}]}]
    txt = dd._render("2026-06-24", results)
    assert "2 shown" in txt and "3 raw candidates" in txt and "1 collapsed" in txt
    assert "1 dropped by strict validation" in txt
    # canonical falsification fields are rendered
    assert "Why ranked" in txt and "Fatal if" in txt and "Must check" in txt
    assert "What would change my mind" in txt


def test_no_padding_below_floor():
    txt = dd._render("2026-06-24", [{"drafts": [_draft("Brazil")], "dropped": []}])
    assert "NOT padded" in txt


def test_build_docket_robust_to_failing_search(tmp_path, monkeypatch):
    def fake_run(s, as_of, **kw):
        if s == "boom_search":
            raise RuntimeError("surface missing")
        return {"drafts": [_draft("Brazil")], "dropped": [],
                "route": "prospective_only_unknown_cutoff", "usage": None}

    monkeypatch.setattr(dd, "run_lab_session", fake_run)
    out, results = dd.build_docket("2026-06-24",
                                   ["cross_surface_contradiction", "boom_search"],
                                   dockets_dir=tmp_path)
    assert out.exists()
    txt = out.read_text()
    assert "Brazil" in txt and "Skipped searches" in txt and "boom_search" in txt


def test_nightly_gate_no_ops_without_optin(monkeypatch, capsys):
    monkeypatch.delenv("ASADO_RUN_DISCOVERY_LAB", raising=False)
    rc = dd.main(["--nightly"])
    assert rc == 0
    assert "disabled" in capsys.readouterr().out
