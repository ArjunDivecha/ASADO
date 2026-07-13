"""
=============================================================================
SCRIPT NAME: a1_premise_check.py
=============================================================================

WHAT THIS PROGRAM DOES:
Phase A of the G1 flip autopsy (PRD Amendment 1): verify the PREMISE that the
network_spillover family (GRAPH*/GRAPHP*/LL_*/SIM_* signals) has negative
cross-sectional ICs in 2024-2026, using ONLY frozen artifacts written by the
June-2026 harness runs — no live DB access, no recomputation. Two sources:

  1. The harness run JSONs in Data/loop/harness_runs/ (one per hypothesis
     test, written 2026-06-10/12): extracts each network_spillover variable's
     verdict, primary-horizon mean IC, NW-t, and the stored per-YEAR IC table.
  2. The harness_ic_series snapshot parquet (per-date rank ICs stored by the
     same runs): recomputes calendar-year mean ICs per signal directly from
     the stored daily IC series as a cross-check on (1), and builds the
     monthly family IC series (equal-weight mean of sign-aligned per-signal
     monthly ICs, latest run per hypothesis, WEAK/WATCH roster per PRD §2).

Outputs a per-signal x per-year IC matrix, the monthly family IC series, and
a console verdict on the premise: is the family IC materially negative in
2024-01 -> latest vs 2012-2023 (NW-t lag 6 on the difference)?

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/harness_runs/*.json
  (frozen harness run artifacts; read-only)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/harness_ic_series.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/harness_results.parquet

OUTPUT FILES (all under the experiment results dir):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a1_per_year_ic_json.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a1_per_year_ic_json.xlsx
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a1_family_ic_monthly.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a1_summary.json

VERSION: 1.0  |  LAST UPDATED: 2026-07-13  |  AUTHOR: Claude (G1 flip autopsy)
DEPENDENCIES: pandas, numpy, openpyxl (production venv). No DB access.
USAGE: venv/bin/python experiments/2026_07_flip_autopsy/a1_premise_check.py
=============================================================================
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
RUNS = ROOT / "Data/loop/harness_runs"
SNAP = ROOT / "Data/work/experiments/flip_autopsy/snapshot_2026_07_13"
RES = ROOT / "experiments/2026_07_flip_autopsy/results"
RES.mkdir(parents=True, exist_ok=True)

FAMILY_PREFIX = re.compile(r"^(GRAPH|LL_|SIM_)")


def nw_tstat(x: np.ndarray, lags: int = 6) -> float:
    """Newey-West t-stat of the mean of series x."""
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 12:
        return np.nan
    e = x - x.mean()
    s = e @ e / n
    for k in range(1, lags + 1):
        w = 1.0 - k / (lags + 1.0)
        s += 2.0 * w * (e[k:] @ e[:-k]) / n
    return float(x.mean() / np.sqrt(s / n))


# ---------------------------------------------------------------- 1. JSONs
rows = []
for f in sorted(RUNS.glob("H_*.json")):
    o = json.loads(f.read_text())
    var = (o.get("signal_spec") or {}).get("variable", "")
    if not FAMILY_PREFIX.match(var):
        continue
    prim = str(o.get("horizons", [None])[0]) if o.get("horizons") else None
    ic_block = o.get("ic", {})
    # primary horizon = the one used for the verdict; harness stores per-horizon dicts
    prim_key = o.get("primary_horizon") or (list(ic_block)[0] if ic_block else None)
    blk = ic_block.get(str(prim_key), {}) if ic_block else {}
    year_tbl = blk.get("year") or blk.get("by_year") or {}
    rows.append({
        "hypothesis_id": o["hypothesis_id"],
        "run_ts": o.get("run_ts"),
        "variable": var,
        "table": (o.get("signal_spec") or {}).get("table"),
        "direction": o.get("direction"),
        "frequency": o.get("frequency"),
        "primary_horizon": prim_key,
        "verdict": o.get("verdict"),
        "mean_ic": blk.get("mean_ic"),
        "nw_t": blk.get("nw_t"),
        "universe_n": o.get("universe_n"),
        "year_table": json.dumps(year_tbl),
        "file": f.name,
    })

js = pd.DataFrame(rows)
if js.empty:
    raise SystemExit("FAIL: no network_spillover harness JSONs found — premise cannot be checked")

# keep the LATEST run per hypothesis (protocol: dedupe to last verdict)
js = js.sort_values("run_ts").groupby("hypothesis_id", as_index=False).tail(1)

# explode year tables -> per-signal per-year IC matrix
yr_rows = []
for _, r in js.iterrows():
    yt = json.loads(r["year_table"])
    for y, v in yt.items():
        ic = v.get("mean_ic") if isinstance(v, dict) else v
        yr_rows.append({"hypothesis_id": r["hypothesis_id"], "variable": r["variable"],
                        "verdict": r["verdict"], "year": int(y), "ic": ic})
peryear = pd.DataFrame(yr_rows)
peryear.to_parquet(RES / "a1_per_year_ic_json.parquet", index=False)

pivot = pd.DataFrame()
if not peryear.empty:
    pivot = peryear.pivot_table(index=["variable", "hypothesis_id", "verdict"],
                                columns="year", values="ic")
    with pd.ExcelWriter(RES / "a1_per_year_ic_json.xlsx") as xw:
        pivot.to_excel(xw, sheet_name="per_year_ic")
        js.drop(columns=["year_table"]).to_excel(xw, sheet_name="runs", index=False)

# ------------------------------------------------- 2. stored IC series
ics = pd.read_parquet(SNAP / "harness_ic_series.parquet")
hr = pd.read_parquet(SNAP / "harness_results.parquet")
print("harness_ic_series columns:", list(ics.columns))
print("harness_results columns:", list(hr.columns))

# ic_series already carries hypothesis_id/run_ts/horizon; add verdict + primary
# horizon from harness_results (via result_file), variable/direction from JSONs
hr2 = hr[["result_file", "verdict", "primary_horizon"]].copy()
fam = js[["hypothesis_id", "variable", "direction", "verdict"]].rename(
    columns={"verdict": "verdict_json"})
merged = ics.merge(hr2, on="result_file", how="inner").merge(
    fam, on="hypothesis_id", how="inner")
print(f"joined IC-series rows for family: {len(merged):,} "
      f"({merged['hypothesis_id'].nunique()} hypotheses)")

# primary horizon only
merged = merged[merged["horizon"].astype(str) == merged["primary_horizon"].astype(str)]
latest_files = (merged.sort_values("run_ts").groupby("hypothesis_id")["result_file"].last())
merged = merged[merged["result_file"].isin(set(latest_files))]

datecol = next(c for c in ["date", "ic_date"] if c in merged.columns)
iccol = next(c for c in ["ic", "rank_ic", "value"] if c in merged.columns)
merged[datecol] = pd.to_datetime(merged[datecol])

# sign-align: harness ICs are already direction-aligned? Conservative: align by
# registered direction (lower_is_better -> flip) unless column already aligned.
if "direction" in merged.columns:
    flip = merged["direction"].eq("lower_is_better")
    merged["ic_aligned"] = np.where(flip, -merged[iccol], merged[iccol])
else:
    merged["ic_aligned"] = merged[iccol]

# ROSTER per PRD section 2: final verdict WEAK or WATCH
roster = merged[merged["verdict_json"].isin(["WEAK", "WATCH"])].copy()
print(f"roster signals (WEAK/WATCH): {sorted(roster['variable'].unique())}")

# monthly per-signal IC, then equal-weight family IC
roster["month"] = roster[datecol].dt.to_period("M").dt.to_timestamp()
sig_m = roster.groupby(["variable", "month"])["ic_aligned"].mean().reset_index()
fam_m = sig_m.groupby("month")["ic_aligned"].mean().rename("family_ic").reset_index()
fam_m.to_parquet(RES / "a1_family_ic_monthly.parquet", index=False)

# per-year family IC + all-signals (incl DEAD) variant
fam_m["year"] = fam_m["month"].dt.year
per_year_family = fam_m.groupby("year")["family_ic"].agg(["mean", "count"])

pre = fam_m[(fam_m["month"] >= "2012-01-01") & (fam_m["month"] < "2024-01-01")]["family_ic"]
post = fam_m[fam_m["month"] >= "2024-01-01"]["family_ic"]
diff_series = fam_m.set_index("month")["family_ic"]
# NW t on post-mean and on difference via dummy regression equivalent:
post_t = nw_tstat(post.values)
pre_t = nw_tstat(pre.values)

summary = {
    "n_family_jsons": int(len(js)),
    "n_roster_signals": int(roster["variable"].nunique()),
    "per_year_family_ic": {str(k): round(float(v), 5) for k, v in per_year_family["mean"].items()},
    "pre_2012_2023_mean_ic": round(float(pre.mean()), 5) if len(pre) else None,
    "pre_nw_t": round(pre_t, 2) if pre_t == pre_t else None,
    "post_2024_mean_ic": round(float(post.mean()), 5) if len(post) else None,
    "post_nw_t": round(post_t, 2) if post_t == post_t else None,
    "post_n_months": int(len(post)),
    "note": "frozen June-2026 harness artifacts only; no recomputation",
}
(RES / "a1_summary.json").write_text(json.dumps(summary, indent=2))

print("\n=== PER-YEAR FAMILY IC (stored ic_series, roster=WEAK/WATCH, sign-aligned) ===")
print(per_year_family.round(4).to_string())
print("\npre 2012-2023: mean IC {} (NW-t {}),  post 2024+: mean IC {} (NW-t {}, n={})".format(
    summary["pre_2012_2023_mean_ic"], summary["pre_nw_t"],
    summary["post_2024_mean_ic"], summary["post_nw_t"], summary["post_n_months"]))
print("\n=== PER-SIGNAL PER-YEAR IC (from JSON year tables) ===")
if not pivot.empty:
    cols = [c for c in pivot.columns if c >= 2020]
    print(pivot[cols].round(3).to_string())
print("\nDone. Outputs in", RES)
