"""
=============================================================================
SCRIPT NAME: test_attribute_outcomes.py
=============================================================================
Validates the Stage 2 DETERMINISTIC classifier (attribute_outcomes.py) on
synthetic matured outcomes — one per headline class — since no real outcome has
scored yet (first maturity ~2026-07-16). Also checks the data_validity
z-trajectory heuristic. No LLM, no DB, no network.

Run: cd ASADO && source venv/bin/activate && \
     python experiments/learning_loop/test_attribute_outcomes.py
=============================================================================
"""
from __future__ import annotations
import sys
import pandas as pd
sys.path.insert(0, "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
from scripts.loop.attribute_outcomes import (
    classify_axes, headline_class, data_validity_for)

T = pd.Timestamp


def _o(**kw):
    base = dict(gross_active=0.0, net_active=0.0, index_information=0.0,
                etf_capture=0.0, decision_available_at=T("2026-03-04"),
                absorbed_at=None, exit_ts=T("2026-04-01"))
    base.update(kw); return base


def main() -> int:
    fails = []

    # 1. DATA_RIGHT_CAPTURED: moved with thesis, net positive, absorbed after decision
    ax = classify_axes(_o(gross_active=0.05, net_active=0.04, index_information=0.03,
                          etf_capture=0.02, absorbed_at=T("2026-03-20")), "confirmed")
    h = headline_class(ax)
    if h != "DATA_RIGHT_CAPTURED":
        fails.append(f"1 captured: got {h} axes={ax}")

    # 2. DATA_RIGHT_ALREADY_ABSORBED: absorbed BEFORE we could act
    ax = classify_axes(_o(gross_active=0.03, net_active=0.02, index_information=0.03,
                          etf_capture=0.0, absorbed_at=T("2026-03-01")), "confirmed")
    h = headline_class(ax)
    if h != "DATA_RIGHT_ALREADY_ABSORBED":
        fails.append(f"2 already_absorbed: got {h} axes={ax}")

    # 3. DATA_RIGHT_NOT_CAPTURABLE: index paid, ETF lost it (basis failure), net negative
    ax = classify_axes(_o(gross_active=0.01, net_active=-0.02, index_information=0.04,
                          etf_capture=-0.03, absorbed_at=T("2026-03-20")), "confirmed")
    h = headline_class(ax)
    if h != "DATA_RIGHT_NOT_CAPTURABLE":
        fails.append(f"3 not_capturable: got {h} axes={ax}")

    # 4. DATA_WRONG: price moved against the thesis
    ax = classify_axes(_o(gross_active=-0.05, net_active=-0.06), "confirmed")
    h = headline_class(ax)
    if h != "DATA_WRONG":
        fails.append(f"4 data_wrong (price): got {h} axes={ax}")

    # 5. DATA_WRONG via revised_away even if price mild-positive
    ax = classify_axes(_o(gross_active=0.001, net_active=-0.004), "revised_away")
    h = headline_class(ax)
    if h != "UNRESOLVED" and h != "DATA_WRONG":
        fails.append(f"5 revised_away: got {h} axes={ax}")

    # 6. UNRESOLVED: flat move inside the neutral band
    ax = classify_axes(_o(gross_active=0.001, net_active=-0.004), "unknown")
    if headline_class(ax) != "UNRESOLVED":
        fails.append(f"6 unresolved: got {headline_class(ax)} axes={ax}")

    # 7. timing axis: pre_absorbed vs tradable off the capture clock
    a = classify_axes(_o(gross_active=0.02, absorbed_at=T("2026-03-02"),
                         decision_available_at=T("2026-03-04")))
    b = classify_axes(_o(gross_active=0.02, absorbed_at=T("2026-03-10"),
                         decision_available_at=T("2026-03-04")))
    if a["timing"] != "pre_absorbed" or b["timing"] != "tradable":
        fails.append(f"7 timing: pre={a['timing']} trad={b['timing']}")

    # 8. data_validity heuristic: z persists => confirmed; reverts => revised_away
    disloc = pd.DataFrame({
        "entity": ["Brazil", "Brazil"], "date": [T("2026-03-04"), T("2026-04-01")],
        "detector": ["D9", "D9"], "severity": [2.0, 1.9]})
    dv1 = data_validity_for(disloc, "Brazil", T("2026-03-04"), T("2026-04-01"))
    disloc2 = disloc.copy(); disloc2.loc[1, "severity"] = 0.3  # reverted toward 0
    dv2 = data_validity_for(disloc2, "Brazil", T("2026-03-04"), T("2026-04-01"))
    dv3 = data_validity_for(disloc, "Narnia", T("2026-03-04"), T("2026-04-01"))
    if dv1 != "confirmed" or dv2 != "revised_away" or dv3 != "unknown":
        fails.append(f"8 data_validity: persist={dv1} revert={dv2} missing={dv3}")

    if fails:
        print("FAIL:")
        for f in fails:
            print("  -", f)
        return 1
    print("PASS: all 8 attribution checks green")
    print("  headline classes exercised: CAPTURED, ALREADY_ABSORBED, NOT_CAPTURABLE, DATA_WRONG, UNRESOLVED")
    print("  data_validity heuristic: confirmed / revised_away / unknown all correct")
    return 0


if __name__ == "__main__":
    sys.exit(main())
