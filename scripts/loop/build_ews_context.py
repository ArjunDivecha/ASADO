"""
=============================================================================
SCRIPT NAME: build_ews_context.py
=============================================================================

WHAT THIS PROGRAM DOES:
Nightly CONTEXT-TIER step (Arjun approved 2026-07-15): reads the latest run of
the Early Warning System (Arjun's 12-signal US IN/TRANSITION/OUT market-regime
classifier, a sibling repo) and publishes a compact context artifact for the
nightly brief and Fable's Desk. Context tier ONLY - same class as the JST
tail-risk layer and the Triptych prior: no harness claim, no trading rule, no
effect on any signal, score, or verdict. It also carries the A7 habitat note
(the network_spillover family historically earned ~2x its IC in TRANSITION/OUT
months - pre-registered diagnostic, FDR caveat attached) so the desk sees the
interaction between the EWS state and a potential family re-arm.

FAIL-SOFT BY DESIGN: any failure (repo missing, no runs, malformed parquet)
logs loudly and returns exit 2 (PARTIAL) - it can never take down the loop.
STALENESS IS SURFACED, NOT HIDDEN: the EWS runs on Arjun's own cadence; if
its latest monthly reading is > STALE_DAYS old, the artifact carries
stale=true and the brief section says so (house rule: no silent staleness).

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/Early Warning/outputs/run_*/signals_panel.parquet
  (newest run dir wins; columns state_best, composite, composite_pctile, diffusion)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/Early Warning/outputs/run_*/summary.json (run metadata)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/ews_context.json
  (atomic tmp-then-rename; consumed by build_dislocations.py's brief section)

VERSION: 1.0  |  LAST UPDATED: 2026-07-15  |  AUTHOR: Claude (EWS context tier)
DEPENDENCIES: pandas, pyarrow (ASADO venv). No DB access at all.
USAGE:  venv/bin/python scripts/loop/build_ews_context.py        # nightly step
        venv/bin/python scripts/loop/build_ews_context.py --check  # print artifact
=============================================================================
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

EWS_OUTPUTS = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/Early Warning/outputs")
ARTIFACT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/ews_context.json")
STALE_DAYS = 45  # EWS is monthly; > ~1.5 months old = flag stale

A7_NOTE = ("A7 (2026-07-15, pre-registered, single-axis bar, 5-axis FDR caveat): "
           "network_spillover family IC pre-2024 was ~2x higher in TRANSITION/OUT "
           "months (+0.043) than IN months (+0.022), NW-t -2.17. Context for "
           "re-arm sizing only; the 2024-26 decay is state-independent.")


def _latest_run_dir() -> Path | None:
    if not EWS_OUTPUTS.exists():
        return None
    runs = sorted(d for d in EWS_OUTPUTS.glob("run_*") if (d / "signals_panel.parquet").exists())
    return runs[-1] if runs else None


def build_context() -> dict:
    import pandas as pd
    run = _latest_run_dir()
    if run is None:
        raise FileNotFoundError(f"no EWS run dirs with signals_panel.parquet under {EWS_OUTPUTS}")
    panel = pd.read_parquet(run / "signals_panel.parquet",
                            columns=["state_best", "composite", "composite_pctile", "diffusion"])
    last = panel.dropna(subset=["state_best"]).iloc[-1]
    as_of = panel.dropna(subset=["state_best"]).index[-1]
    age_days = (datetime.now(timezone.utc).date() - pd.Timestamp(as_of).date()).days
    meta = {}
    sj = run / "summary.json"
    if sj.exists():
        meta = json.loads(sj.read_text()).get("best", {})
    return {
        "generated_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_run": run.name,
        "as_of_month_end": str(pd.Timestamp(as_of).date()),
        "age_days": int(age_days),
        "stale": bool(age_days > STALE_DAYS),
        "state": str(last["state_best"]),
        "composite": round(float(last["composite"]), 4),
        "composite_pctile": round(float(last["composite_pctile"]), 4),
        "diffusion": round(float(last["diffusion"]), 4),
        "classifier": meta.get("variant"),
        "a7_habitat_note": A7_NOTE,
        "tier": "context-only (JST/Triptych class): no signal, no rule, no verdict",
    }


def main() -> int:
    if "--check" in sys.argv:
        print(ARTIFACT.read_text() if ARTIFACT.exists() else "no artifact yet")
        return 0
    try:
        ctx = build_context()
        ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        tmp = ARTIFACT.with_name(ARTIFACT.name + ".tmp")
        tmp.write_text(json.dumps(ctx, indent=2))
        tmp.replace(ARTIFACT)
        print(f"ews_context: {ctx['state']} as of {ctx['as_of_month_end']} "
              f"(composite {ctx['composite']}, pctile {ctx['composite_pctile']:.0%}, "
              f"diffusion {ctx['diffusion']:.0%}, stale={ctx['stale']})")
        return 0
    except Exception as e:  # fail-soft: never red the loop
        print(f"ews_context PARTIAL: {type(e).__name__}: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
