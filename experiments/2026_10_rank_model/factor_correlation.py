#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/factor_correlation.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/snapshot_2026_10_07/feature_panel_observed.parquet
    Frozen copy of the `feature_panel_observed` view (34 T2 countries, forecasts
    excluded), tidy long: (date, country, value, variable, source). Made by
    scripts/snapshot_for_experiment.py so this script never touches the live DB.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/cache/query_assistant/variable_catalog.json
    Per-variable metadata (source, frequency, base variable) from the schema
    registry; used to label variables and to keep only monthly ones.

OUTPUT FILES (all inside a timestamped run directory
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/corr_<YYYYMMDD_HHMMSS>/ ):
- factor_correlation_matrix.parquet   wide matrix, rows/cols = variable (clustered order)
- factor_overlap_n.parquet            pairwise count of (date, country) observations
- factor_correlation_matrix.xlsx      sheets: Correlation, Overlap_N, Variables,
                                      Top_Pairs, Clusters, CS_vs_TS
- factor_correlation_heatmap.pdf      clustered heatmap (light mode, matplotlib)
- summary.json                        counts, parameters, run metadata
- run.log                             the log of this run

VERSION: 1.1
LAST UPDATED: 2026-10-07
AUTHOR: Claude (Fable 5.1) for Arjun Divecha

DESCRIPTION:
Builds the pairwise Pearson correlation matrix of the z-scores of every monthly
factor in the ASADO warehouse — both the `_CS` (within-month, across-country)
and the `_TS` (within-country, across-time) variants, in one matrix — so Arjun
can hand-pick a de-duplicated factor set for the country-ranking model.

Why one pooled Pearson matrix: `_CS` has zero mean each month by construction,
so its pooled correlation over (date, country) rows is essentially the average
within-month cross-sectional correlation — "do these two factors order the 34
countries the same way?". `_TS` scores keep a common time component (every
country's rate z-score fell together in 2020), so a `_TS`/`_TS` pooled
correlation also reflects shared global swings. That is what a model scoring
each country-month independently sees as feature redundancy, so it is the
right measure for de-duplication; a within-month-demeaned version would be the
measure for pure cross-sectional ordering (not built here).

v1.1 (2026-10-07): added the `_TS` variants (v1.0 was `_CS` only) and the
`CS_vs_TS` sheet, which gives each base factor's correlation between its two
variants so near-identical pairs can be collapsed.

Steps:
  1. Load the snapshot, keep variables ending in `_CS` or `_TS` whose catalog
     frequency is not quarterly/annual (monthly, daily and event-driven stay),
     and drop anything whose base variable is a forward return (blacklisted).
  2. Pivot to a (date, country) x variable wide panel.
  3. Pairwise-complete Pearson correlation with a minimum overlap; pairs below
     the overlap floor are left undefined and rendered as an em dash.
  4. Order variables by hierarchical clustering on 1 - |rho| (average linkage)
     so near-duplicates sit next to each other, and cut the tree at two
     |rho| thresholds to list duplicate groups.
  5. Write parquet (canonical), xlsx (for eyeballing), PDF heatmap, summary.

Sign convention note: the T2 `_CS` and `_TS` scores are sign-flipped upstream
for the "lower-is-better" factors (PE, PBK, Debt to GDP, RSI14, ...), so for
those higher = more attractive. Other sources' scores are not flipped. The
sign therefore matters for reading a correlation but not for spotting a
duplicate; the Top_Pairs and Clusters sheets use |rho|.

DEPENDENCIES: pandas, numpy, scipy, matplotlib, xlsxwriter, pyarrow (experiment .venv)

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python factor_correlation.py
  .venv/bin/python factor_correlation.py --min-overlap 300

NOTES:
- Reads parquet only; never opens asado.duckdb.
- Rows duplicated on (date, country, variable) are averaged and logged.
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
# Code and results live in the exp/NN worktree; data (snapshot, catalog) stays in the main checkout.
EXP_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model")
SNAPSHOT = (
    BASE_DIR / "Data" / "work" / "experiments" / "2026_10_rank_model"
    / "snapshot_2026_10_07" / "feature_panel_observed.parquet"
)
CATALOG = BASE_DIR / "Data" / "cache" / "query_assistant" / "variable_catalog.json"
RESULTS_ROOT = EXP_DIR / "results"

# Forward-return variables are optimizer targets, never signals
# (scripts/harness/evaluate_signal.py is canonical; copied here so this
# experiment is self-contained).
FORWARD_RETURN_BASES = {
    "1MRet", "3MRet", "6MRet", "9MRet", "12MRet",
    "1DRet", "5DRet", "20DRet", "60DRet", "120DRet",
}
EXCLUDED_FREQUENCIES = {"quarterly", "annual"}

# T2 factors whose _CS score is multiplied by -1 upstream (scripts/t2_normalize.py)
T2_SIGN_FLIPPED = {
    "Best Cash Flow", "Best PBK", "Best PE ", "Best Price Sales",
    "EV to EBITDA", "Shiller PE", "Trailing PE", "Positive PE ",
    "Currency Change", "Debt to GDP", "REER", "RSI14", "10Yr Bond 12",
    "Advance Decline", "1MTR", "3MTR", "Debt To EV",
    "Bloom Country Risk", "Bond Yield Change",
}

log = logging.getLogger("factor_correlation")


def setup_logging(run_dir: Path) -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    log.setLevel(logging.INFO)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    fh = logging.FileHandler(run_dir / "run.log")
    fh.setFormatter(fmt)
    log.addHandler(sh)
    log.addHandler(fh)


def load_variables(snapshot: Path, catalog: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (long panel of included _CS/_TS rows, variable table for ALL _CS/_TS vars)."""
    df = pd.read_parquet(snapshot)
    df["date"] = pd.to_datetime(df["date"])
    log.info("snapshot rows=%d countries=%d variables=%d",
             len(df), df["country"].nunique(), df["variable"].nunique())

    cs = df[df["variable"].str.endswith(("_CS", "_TS"))].copy()
    meta = json.load(open(catalog))["variable_metadata"]
    missing_meta = sorted(v for v in cs["variable"].unique() if v not in meta)
    if missing_meta:
        log.warning("%d variables not in the catalog (frequency unknown, kept): %s",
                    len(missing_meta), missing_meta[:10])

    rows = []
    for v, g in cs.groupby("variable"):
        m = meta.get(v, {})
        base = m.get("base_variable", v[:-3])
        freq = m.get("frequency", "unknown")
        src = m.get("source", g["source"].iloc[0])
        if base in FORWARD_RETURN_BASES:
            status = "excluded: forward return"
        elif freq in EXCLUDED_FREQUENCIES:
            status = f"excluded: {freq}"
        else:
            status = "included"
        rows.append({
            "variable": v,
            "base_variable": base,
            "normalization": v[-2:],
            "source": src,
            "frequency": freq,
            "status": status,
            "n_obs": int(len(g)),
            "n_countries": int(g["country"].nunique()),
            "first_date": g["date"].min().date().isoformat(),
            "last_date": g["date"].max().date().isoformat(),
            "sign_flipped_upstream": bool(src == "t2" and base in T2_SIGN_FLIPPED),
        })
    var_table = pd.DataFrame(rows).sort_values(["status", "source", "variable"]).reset_index(drop=True)

    included = set(var_table.loc[var_table["status"] == "included", "variable"])
    kept = cs[cs["variable"].isin(included)].copy()
    log.info("_CS/_TS variables: total=%d included=%d excluded=%d",
             len(var_table), len(included), len(var_table) - len(included))
    for status, n in var_table["status"].value_counts().items():
        log.info("  %-28s %d", status, n)
    inc = var_table[var_table["status"] == "included"]
    log.info("included by normalization: %s", inc["normalization"].value_counts().to_dict())
    return kept, var_table


def build_wide(kept: pd.DataFrame) -> pd.DataFrame:
    dup = kept.duplicated(["date", "country", "variable"]).sum()
    if dup:
        log.warning("%d duplicate (date,country,variable) rows — averaging", dup)
    wide = kept.pivot_table(index=["date", "country"], columns="variable",
                            values="value", aggfunc="mean")
    wide = wide.replace([np.inf, -np.inf], np.nan)
    log.info("wide panel: %d (date,country) rows x %d variables; dates %s -> %s",
             wide.shape[0], wide.shape[1],
             wide.index.get_level_values(0).min().date(),
             wide.index.get_level_values(0).max().date())
    return wide


def pairwise_corr(wide: pd.DataFrame, min_overlap: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    vals = wide.corr(method="pearson", min_periods=min_overlap).to_numpy(copy=True)
    np.fill_diagonal(vals, 1.0)  # a constant column would otherwise self-correlate as NaN
    corr = pd.DataFrame(vals, index=wide.columns, columns=wide.columns)
    notna = wide.notna().astype(np.int32)
    n = pd.DataFrame(notna.T.values @ notna.values, index=wide.columns, columns=wide.columns)
    undefined = int(corr.isna().values.sum())
    log.info("correlation: %d x %d; undefined pairs (overlap < %d): %d of %d",
             *corr.shape, min_overlap, undefined // 2, corr.shape[0] * (corr.shape[0] - 1) // 2)
    return corr, n


def cluster_order(corr: pd.DataFrame, thresholds: list[float]) -> tuple[list[str], dict[float, pd.Series]]:
    from scipy.cluster.hierarchy import fcluster, leaves_list, linkage
    from scipy.spatial.distance import squareform

    a = corr.abs().values.copy()
    a[np.isnan(a)] = 0.0  # no overlap -> treat as unrelated
    np.fill_diagonal(a, 1.0)
    dist = 1.0 - a
    dist = (dist + dist.T) / 2.0
    np.fill_diagonal(dist, 0.0)
    z = linkage(squareform(dist, checks=False), method="average")
    order = [corr.index[i] for i in leaves_list(z)]
    clusters = {}
    for t in thresholds:
        labels = fcluster(z, t=1.0 - t, criterion="distance")
        clusters[t] = pd.Series(labels, index=corr.index, name=f"cluster_abs_rho_ge_{t:.2f}")
        sizes = pd.Series(labels).value_counts()
        log.info("clusters at |rho|>=%.2f: %d groups, %d with >1 member, largest %d",
                 t, len(sizes), int((sizes > 1).sum()), int(sizes.max()))
    return order, clusters


def top_pairs(corr: pd.DataFrame, n: pd.DataFrame, var_table: pd.DataFrame, floor: float) -> pd.DataFrame:
    vt = var_table.set_index("variable")
    src, base, norm = vt["source"], vt["base_variable"], vt["normalization"]
    vals = corr.values
    iu = np.triu_indices_from(vals, k=1)
    rec = pd.DataFrame({
        "variable_a": corr.index[iu[0]],
        "variable_b": corr.columns[iu[1]],
        "rho": vals[iu],
        "overlap_n": n.values[iu],
    }).dropna(subset=["rho"])
    rec["abs_rho"] = rec["rho"].abs()
    rec["source_a"] = rec["variable_a"].map(src)
    rec["source_b"] = rec["variable_b"].map(src)
    rec["norm_a"] = rec["variable_a"].map(norm)
    rec["norm_b"] = rec["variable_b"].map(norm)
    rec["same_base_factor"] = rec["variable_a"].map(base).values == rec["variable_b"].map(base).values
    rec = rec[rec["abs_rho"] >= floor].sort_values("abs_rho", ascending=False).reset_index(drop=True)
    log.info("pairs with |rho| >= %.2f: %d (of which CS-vs-TS of the same factor: %d)",
             floor, len(rec), int(rec["same_base_factor"].sum()))
    return rec[["variable_a", "source_a", "norm_a", "variable_b", "source_b", "norm_b",
                "same_base_factor", "rho", "abs_rho", "overlap_n"]]


def cs_vs_ts(corr: pd.DataFrame, n: pd.DataFrame, var_table: pd.DataFrame) -> pd.DataFrame:
    """One row per base factor that has both a _CS and a _TS variant in the matrix."""
    inc = var_table[var_table["status"] == "included"]
    rows = []
    for b, g in inc.groupby("base_variable"):
        cs = g.loc[g["normalization"] == "CS", "variable"]
        ts = g.loc[g["normalization"] == "TS", "variable"]
        if len(cs) != 1 or len(ts) != 1:
            continue
        c, t = cs.iloc[0], ts.iloc[0]
        rows.append({"base_variable": b, "source": g["source"].iloc[0],
                     "cs_variable": c, "ts_variable": t,
                     "rho_cs_ts": float(corr.loc[c, t]), "overlap_n": int(n.loc[c, t])})
    out = pd.DataFrame(rows)
    out["abs_rho"] = out["rho_cs_ts"].abs()
    out = out.sort_values("abs_rho", ascending=False).reset_index(drop=True)
    log.info("base factors with both CS and TS: %d; |rho| >= 0.8 between them: %d",
             len(out), int((out["abs_rho"] >= 0.8).sum()))
    return out


def write_xlsx(path: Path, corr: pd.DataFrame, n: pd.DataFrame, var_table: pd.DataFrame,
               pairs: pd.DataFrame, clusters: dict[float, pd.Series], min_overlap: int,
               csts: pd.DataFrame) -> None:
    with pd.ExcelWriter(path, engine="xlsxwriter") as xw:
        wb = xw.book
        num = wb.add_format({"num_format": "0.00", "font_size": 8})
        hdr_rot = wb.add_format({"rotation": 90, "bold": True, "font_size": 7,
                                 "align": "center", "valign": "bottom"})
        hdr = wb.add_format({"bold": True, "font_size": 8})
        dash = wb.add_format({"align": "center", "font_size": 8, "font_color": "#888888"})

        # --- Correlation (clustered order) -----------------------------------
        ws = wb.add_worksheet("Correlation")
        xw.sheets["Correlation"] = ws
        ws.write(0, 0, "variable", hdr)
        for j, v in enumerate(corr.columns):
            ws.write(0, j + 1, v, hdr_rot)
        for i, v in enumerate(corr.index):
            ws.write(i + 1, 0, v, hdr)
            row = corr.iloc[i].values
            for j, x in enumerate(row):
                if np.isnan(x):
                    ws.write(i + 1, j + 1, "—", dash)
                else:
                    ws.write_number(i + 1, j + 1, float(x), num)
        k = len(corr)
        ws.conditional_format(1, 1, k, k, {
            "type": "3_color_scale",
            "min_type": "num", "min_value": -1, "min_color": "#2166AC",
            "mid_type": "num", "mid_value": 0, "mid_color": "#FFFFFF",
            "max_type": "num", "max_value": 1, "max_color": "#B2182B",
        })
        ws.set_column(0, 0, 32)
        ws.set_column(1, k, 4.2)
        ws.set_row(0, 150)
        ws.freeze_panes(1, 1)
        ws.write(k + 2, 0, f"Pearson correlation of _CS and _TS z-scores over pooled (date, country) rows; "
                           f"pairwise-complete; — = fewer than {min_overlap} overlapping observations. "
                           f"Rows/columns ordered by hierarchical clustering on 1-|rho|.")

        # --- Overlap N ---------------------------------------------------------
        n_ord = n.loc[corr.index, corr.columns]
        n_ord.to_excel(xw, sheet_name="Overlap_N")
        ws2 = xw.sheets["Overlap_N"]
        ws2.set_column(0, 0, 32)
        ws2.set_column(1, k, 6)
        ws2.freeze_panes(1, 1)

        # --- Variables ---------------------------------------------------------
        vt = var_table.copy()
        for t, s in clusters.items():
            vt[s.name] = vt["variable"].map(s)
        order_pos = {v: i for i, v in enumerate(corr.index)}
        vt["clustered_position"] = vt["variable"].map(order_pos)
        vt = vt.sort_values(["status", "clustered_position", "source", "variable"],
                            na_position="last").reset_index(drop=True)
        vt.to_excel(xw, sheet_name="Variables", index=False, na_rep="—")
        ws3 = xw.sheets["Variables"]
        ws3.set_column(0, 1, 34)
        ws3.set_column(2, 20, 16)
        ws3.freeze_panes(1, 1)
        ws3.autofilter(0, 0, len(vt), len(vt.columns) - 1)

        # --- Top pairs ---------------------------------------------------------
        pairs.to_excel(xw, sheet_name="Top_Pairs", index=False)
        ws4 = xw.sheets["Top_Pairs"]
        ws4.set_column(0, 0, 34)
        ws4.set_column(1, 2, 12)
        ws4.set_column(3, 3, 34)
        ws4.set_column(4, 9, 12)
        ws4.freeze_panes(1, 0)
        ws4.autofilter(0, 0, len(pairs), len(pairs.columns) - 1)

        # --- CS vs TS of the same base factor ------------------------------
        # na_rep: a pair under the overlap floor is undefined, rendered as an em dash
        csts.to_excel(xw, sheet_name="CS_vs_TS", index=False, na_rep="—")
        ws6 = xw.sheets["CS_vs_TS"]
        ws6.set_column(0, 0, 34)
        ws6.set_column(1, 1, 14)
        ws6.set_column(2, 3, 34)
        ws6.set_column(4, 6, 12)
        ws6.freeze_panes(1, 0)
        ws6.autofilter(0, 0, len(csts), len(csts.columns) - 1)

        # --- Clusters (one row per group, members listed) ----------------------
        rows = []
        src = var_table.set_index("variable")["source"]
        for t, s in clusters.items():
            for cid, members in s.groupby(s).groups.items():
                members = list(members)
                if len(members) < 2:
                    continue
                sub = corr.loc[members, members].abs().values
                iu = np.triu_indices_from(sub, k=1)
                rows.append({
                    "threshold_abs_rho": t,
                    "cluster_id": int(cid),
                    "n_members": len(members),
                    "min_abs_rho_within": float(np.nanmin(sub[iu])),
                    "mean_abs_rho_within": float(np.nanmean(sub[iu])),
                    "sources": ", ".join(sorted(set(src[m] for m in members))),
                    "members": " | ".join(members),
                })
        cl = pd.DataFrame(rows).sort_values(["threshold_abs_rho", "n_members"],
                                            ascending=[False, False]).reset_index(drop=True)
        cl.to_excel(xw, sheet_name="Clusters", index=False)
        ws5 = xw.sheets["Clusters"]
        ws5.set_column(0, 4, 14)
        ws5.set_column(5, 5, 30)
        ws5.set_column(6, 6, 160)
        ws5.freeze_panes(1, 0)


def write_heatmap(path: Path, corr: pd.DataFrame, var_table: pd.DataFrame, min_overlap: int) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize

    k = len(corr)
    src = var_table.set_index("variable")["source"]
    sources = sorted(set(src[v] for v in corr.index))
    # fixed categorical order for tick-label colours (identity, not rank)
    palette = ["#1F77B4", "#D62728", "#2CA02C", "#9467BD", "#FF7F0E", "#8C564B",
               "#E377C2", "#17BECF", "#BCBD22", "#7F7F7F"]
    src_color = {s: palette[i % len(palette)] for i, s in enumerate(sources)}

    cell = 0.13 if k <= 200 else 0.11
    label_pt = 4.5 if k <= 200 else 3.6
    side = max(12.0, k * cell + 3.5)
    fig, ax = plt.subplots(figsize=(side, side), facecolor="white")
    a = corr.values
    im = ax.imshow(a, cmap="RdBu_r", norm=Normalize(vmin=-1, vmax=1),
                   interpolation="nearest", aspect="equal")
    # undefined cells as light grey hatch
    und = np.isnan(a)
    if und.any():
        ax.imshow(np.where(und, 1.0, np.nan), cmap="Greys", vmin=0, vmax=4,
                  interpolation="nearest", aspect="equal")
    ax.set_xticks(range(k))
    ax.set_yticks(range(k))
    ax.set_xticklabels(corr.columns, rotation=90, fontsize=label_pt)
    ax.set_yticklabels(corr.index, fontsize=label_pt)
    for lab in ax.get_xticklabels():
        lab.set_color(src_color[src[lab.get_text()]])
    for lab in ax.get_yticklabels():
        lab.set_color(src_color[src[lab.get_text()]])
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    cb.set_label("Pearson ρ of cross-sectional z-scores", fontsize=9)
    cb.ax.tick_params(labelsize=8)
    handles = [plt.Line2D([], [], marker="s", linestyle="", color=src_color[s], label=s)
               for s in sources]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1.0),
              fontsize=7, frameon=False, title="source (label colour)", title_fontsize=8)
    d0 = var_table.loc[var_table["status"] == "included", "first_date"].min()
    d1 = var_table.loc[var_table["status"] == "included", "last_date"].max()
    n_cs = int((var_table["status"].eq("included") & var_table["normalization"].eq("CS")).sum())
    n_ts = int((var_table["status"].eq("included") & var_table["normalization"].eq("TS")).sum())
    ax.set_title(f"Monthly factor z-scores — pairwise correlation, {k} variables "
                 f"({n_cs} _CS + {n_ts} _TS), 34 countries, {d0} → {d1}\n"
                 f"clustered order (average linkage on 1−|ρ|); grey = under {min_overlap} overlapping obs",
                 fontsize=11, pad=14)
    fig.tight_layout()
    fig.savefig(path, format="pdf", facecolor="white")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("DESCRIPTION:")[0])
    ap.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    ap.add_argument("--catalog", type=Path, default=CATALOG)
    ap.add_argument("--min-overlap", type=int, default=200,
                    help="minimum (date,country) overlap for a pair to be defined (default 200 ≈ 6 months x 34)")
    ap.add_argument("--pair-floor", type=float, default=0.70,
                    help="|rho| floor for the Top_Pairs sheet")
    ap.add_argument("--cluster-thresholds", type=str, default="0.90,0.80",
                    help="comma-separated |rho| cut levels for duplicate groups")
    args = ap.parse_args()

    t0 = time.time()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RESULTS_ROOT / f"corr_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    setup_logging(run_dir)
    log.info("run dir: %s", run_dir)
    log.info("snapshot: %s", args.snapshot)

    kept, var_table = load_variables(args.snapshot, args.catalog)
    wide = build_wide(kept)
    corr, n = pairwise_corr(wide, args.min_overlap)
    thresholds = [float(x) for x in args.cluster_thresholds.split(",")]
    order, clusters = cluster_order(corr, thresholds)
    corr = corr.loc[order, order]
    n = n.loc[order, order]
    pairs = top_pairs(corr, n, var_table, args.pair_floor)
    csts = cs_vs_ts(corr, n, var_table)

    # completeness by variable (countries covered), so gaps are visible
    cov = (wide.notna().groupby(level="country").any().sum(axis=0))
    thin = cov[cov < 34]
    if len(thin):
        log.info("variables covering fewer than 34 countries: %d (min %d)", len(thin), int(thin.min()))

    p_corr = run_dir / "factor_correlation_matrix.parquet"
    p_n = run_dir / "factor_overlap_n.parquet"
    p_xlsx = run_dir / "factor_correlation_matrix.xlsx"
    p_pdf = run_dir / "factor_correlation_heatmap.pdf"
    p_json = run_dir / "summary.json"

    corr.to_parquet(p_corr)
    n.to_parquet(p_n)
    write_xlsx(p_xlsx, corr, n, var_table, pairs, clusters, args.min_overlap, csts)
    write_heatmap(p_pdf, corr, var_table, args.min_overlap)

    off = corr.values[np.triu_indices_from(corr.values, k=1)]
    off = off[~np.isnan(off)]
    summary = {
        "run_dir": str(run_dir),
        "snapshot": str(args.snapshot),
        "catalog": str(args.catalog),
        "n_variables_included": int(len(corr)),
        "n_variables_included_by_normalization": var_table.loc[var_table["status"] == "included", "normalization"].value_counts().to_dict(),
        "n_variables_cs_ts_total": int(len(var_table)),
        "status_counts": var_table["status"].value_counts().to_dict(),
        "n_base_factors_with_both_cs_ts": int(len(csts)),
        "n_base_factors_cs_ts_abs_rho_ge_0.8": int((csts["abs_rho"] >= 0.8).sum()),
        "source_counts_included": var_table.loc[var_table["status"] == "included", "source"].value_counts().to_dict(),
        "wide_rows": int(wide.shape[0]),
        "date_min": str(wide.index.get_level_values(0).min().date()),
        "date_max": str(wide.index.get_level_values(0).max().date()),
        "min_overlap": args.min_overlap,
        "pair_floor": args.pair_floor,
        "cluster_thresholds": thresholds,
        "n_pairs_defined": int(len(off)),
        "n_pairs_abs_rho_ge_0.9": int((np.abs(off) >= 0.9).sum()),
        "n_pairs_abs_rho_ge_0.8": int((np.abs(off) >= 0.8).sum()),
        "n_pairs_abs_rho_ge_0.7": int((np.abs(off) >= 0.7).sum()),
        "median_abs_rho": float(np.median(np.abs(off))),
        "clusters": {f"{t:.2f}": int(clusters[t].nunique()) for t in thresholds},
        "outputs": [str(p) for p in (p_corr, p_n, p_xlsx, p_pdf)],
        "elapsed_s": round(time.time() - t0, 1),
    }
    p_json.write_text(json.dumps(summary, indent=2))
    log.info("wrote %s", p_xlsx)
    log.info("wrote %s", p_pdf)
    log.info("done in %.1fs", time.time() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
