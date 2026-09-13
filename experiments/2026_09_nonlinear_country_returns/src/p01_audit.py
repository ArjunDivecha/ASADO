# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/p01_audit.py
#
# P01 read-only field-level audit for the ASADO Nonlinear Country-Return Study
# (spec ASADO_NL_20260913_V1). Runs ONLY off the frozen snapshot parquet files
# in Data/work/experiments/nonlinear_country_returns/snapshot_2026_09_13/ —
# never opens a DuckDB connection.
#
# Emits (into the worktree experiment dir):
#   audit/coverage_by_feature_market.parquet
#   audit/coverage_waterfall.json
#   audit/market_map.csv
#   audit/snapshot_manifest.json  (content-addressed; covers ALL snapshot files)
#
# CONSUMED BY: governance/data_readiness.md, feature_manifest.bound.yaml
# =============================================================================
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

MAIN = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
SNAP = MAIN / "Data/work/experiments/nonlinear_country_returns/snapshot_2026_09_13"
OUT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-Nonlinear"
           "/experiments/2026_09_nonlinear_country_returns/audit")
OUT.mkdir(parents=True, exist_ok=True)

T2 = [
    "Australia", "Brazil", "Canada", "Chile", "ChinaA", "ChinaH", "Denmark",
    "France", "Germany", "Hong Kong", "India", "Indonesia", "Italy", "Japan",
    "Korea", "Malaysia", "Mexico", "NASDAQ", "Netherlands", "Philippines",
    "Poland", "Saudi Arabia", "Singapore", "South Africa", "Spain", "Sweden",
    "Switzerland", "Taiwan", "Thailand", "Turkey", "U.K.", "U.S.",
    "US SmallCap", "Vietnam",
]

# primitive -> required source variables (market-keyed) or ("GLOBAL", var)
PRIM_REQS = {
    "P01": [("t2_levels_daily", "Tot Return Index")],
    "P02": [("t2_levels_daily", "Tot Return Index")],
    "P03": [("t2_levels_daily", "Tot Return Index")],
    "P04": [("t2_levels_daily", "Tot Return Index")],
    "P05": [("graph_edge_vintages", "trade"), ("t2_levels_daily", "Tot Return Index")],
    "P06": [("graph_edge_vintages", "trade"), ("t2_levels_daily", "Tot Return Index")],
    "P07": [("graph_edge_vintages", "bank"), ("t2_levels_daily", "Tot Return Index")],
    "P08": [("graph_edge_vintages", "bank"), ("t2_levels_daily", "Tot Return Index")],
    "P09": [("market_implied_daily", "FX_IMPVOL_3M_PCT")],
    "P10": [("market_implied_daily", "FX_IMPVOL_1W_PCT"),
            ("market_implied_daily", "FX_IMPVOL_3M_PCT")],
    "P11": [("market_implied_daily", "FX_RR25_1M_PCT")],  # spec says 3M; 1M is all that exists
    "P12": [("market_implied_daily", "FX_CARRY_3M_PCT")],
    "P13": [("sovereign_daily", "SOV_2Y_YIELD_PCT")],
    "P14": [("sovereign_daily", "SOV_10Y_YIELD_PCT")],
    "P15": [("sovereign_daily", "SOV_2Y_YIELD_PCT"), ("sovereign_daily", "SOV_10Y_YIELD_PCT")],
    "P16": [("sovereign_daily", "SOV_2Y_YIELD_PCT")],
    "P17": [("consensus_daily", "CONS_GDP_PCT")],
    "P18": [("consensus_daily", "CONS_CPI_PCT")],
    "P19": [("consensus_daily", "CONS_GDP_PCT"), ("consensus_daily", "CONS_CPI_PCT")],
    "P20": [("consensus_daily", "CONS_GDP_PCT"), ("consensus_daily", "CONS_CPI_PCT")],
    "P21": [("market_implied_daily", "RISK_VIX")],      # GLOBAL, market-invariant
    "P22": [("market_implied_daily", "RISK_MOVE")],     # GLOBAL
    "P23": [("market_implied_daily", "RISK_DXY")],      # GLOBAL
    "P24": [("market_implied_daily", "CMD_CO1"), ("market_implied_daily", "CMD_CO2")],  # GLOBAL Brent
}
GLOBAL_PRIMS = {"P21", "P22", "P23", "P24"}


def load(name):
    return pd.read_parquet(SNAP / f"{name}.parquet")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def var_coverage(df: pd.DataFrame, variable: str) -> pd.DataFrame:
    """per-country first/last/n for one variable."""
    d = df[df["variable"] == variable]
    g = d.groupby("country").agg(first=("date", "min"), last=("date", "max"),
                                 n=("value", "count")).reset_index()
    return g


def edge_coverage(ge: pd.DataFrame, edge_type: str) -> pd.DataFrame:
    """per-focal vintage coverage: first applies_from, last vintage_end,
    vintage count, neighbor-count range at latest vintage."""
    d = ge[ge["edge_type"] == edge_type]
    g = d.groupby("focal").agg(first=("applies_from", "min"),
                               last=("vintage_end", "max"),
                               n_vintages=("vintage_end", "nunique")).reset_index()
    g["first"] = pd.to_datetime(g["first"])
    g["last"] = pd.to_datetime(g["last"])
    g = g.rename(columns={"focal": "country"})
    latest = d[d["vintage_end"] == d["vintage_end"].max()]
    nn = latest.groupby("focal")["neighbor"].nunique().rename("n_neighbors_latest")
    g = g.merge(nn, left_on="country", right_index=True, how="left")
    return g


def main() -> int:
    tables = {t: load(t) for t in
              ["t2_levels_daily", "market_implied_daily", "sovereign_daily",
               "consensus_daily", "consensus_revisions",
               "graph_features_pit_daily", "graph_edge_vintages", "daily_calendar"]}
    ge = tables["graph_edge_vintages"]

    # ── per (primitive, market) coverage ──────────────────────────────────────
    rows = []
    cov_cache: dict[tuple[str, str], pd.DataFrame] = {}
    for var_df_name, var in ({req for reqs in PRIM_REQS.values() for req in reqs}
                             | {("graph_edge_vintages", "holder")}):
        if var_df_name == "graph_edge_vintages":
            cov_cache[(var_df_name, var)] = edge_coverage(ge, var)
        else:
            cov_cache[(var_df_name, var)] = var_coverage(tables[var_df_name], var)

    for pid, reqs in PRIM_REQS.items():
        for c in T2:
            if pid in GLOBAL_PRIMS:
                # market-invariant global series: coverage is the GLOBAL row's
                covs = [cov_cache[r] for r in reqs]
                first = pd.Timestamp(max(cv["first"].min() for cv in covs))
                last = pd.Timestamp(min(cv["last"].max() for cv in covs))
                rows.append({"primitive": pid, "market": c, "first": first,
                             "last": last, "n": int(sum(cv["n"].sum() for cv in covs)),
                             "note": "GLOBAL market-invariant"})
                continue
            # market-keyed: intersection over required vars
            firsts, lasts, ns, missing = [], [], [], []
            for df_name, var in reqs:
                cv = cov_cache[(df_name, var)]
                row = cv[cv["country"] == c]
                if row.empty:
                    missing.append(var)
                else:
                    firsts.append(pd.Timestamp(row["first"].iloc[0]))
                    lasts.append(pd.Timestamp(row["last"].iloc[0]))
                    ns.append(int(row["n"].iloc[0]) if "n" in row else int(row["n_vintages"].iloc[0]))
            rows.append({
                "primitive": pid, "market": c,
                "first": pd.Timestamp(max(firsts)) if firsts else pd.NaT,
                "last": pd.Timestamp(min(lasts)) if lasts else pd.NaT,
                "n": (min(ns) if ns else 0) if not missing else 0,
                "note": "" if not missing else f"missing: {','.join(missing)}",
            })
    cov = pd.DataFrame(rows)
    cov.to_parquet(OUT / "coverage_by_feature_market.parquet", index=False)

    # ── per-market eligible-start = max over its 24 primitives' firsts ────────
    per_mkt = cov.groupby("market").agg(
        eligible_from=("first", "max"), eligible_to=("last", "min"))
    # markets that can NEVER be eligible (any primitive has no data at all)
    never = sorted(set(m for m in T2 if cov[cov.market == m]["n"].min() == 0))
    per_mkt["never_eligible"] = per_mkt.index.isin(never)
    per_mkt.loc[per_mkt["never_eligible"], "eligible_from"] = pd.NaT

    # eligible-market count over time (strict spec = all 24 primitives)
    elig = per_mkt[~per_mkt["never_eligible"]]["eligible_from"].sort_values()
    timeline = [{"date": str(d.date()), "eligible_markets": int((elig <= d).sum())}
                for d in sorted(set(elig))]
    strict_set = sorted(per_mkt[~per_mkt["never_eligible"]].index.tolist())

    def eligible_set_for(prims: list[str]) -> dict[str, pd.Timestamp]:
        """market -> earliest date all required primitives have data (level-1
        eligibility only; ignores warm-up/normalization lead time)."""
        out: dict[str, pd.Timestamp] = {}
        for c in T2:
            firsts = []
            ok = True
            for pid in prims:
                if pid in GLOBAL_PRIMS:
                    continue
                for req in PRIM_REQS[pid]:
                    cv = cov_cache[req]
                    row = cv[cv["country"] == c]
                    if row.empty:
                        ok = False
                        break
                    firsts.append(pd.Timestamp(row["first"].iloc[0]))
                if not ok:
                    break
            if ok:
                out[c] = max(firsts)
        return out

    def scenario(name: str, prims: list[str], note: str) -> dict:
        es = eligible_set_for(prims)
        dates = sorted(set(es.values()))
        tl = [{"date": str(d.date()),
               "eligible_markets": int(sum(1 for v in es.values() if v <= d))}
              for d in dates]
        return {
            "description": note,
            "primitive_count": len(prims),
            "markets_ever_eligible": len(es),
            "eligible_market_set": sorted(es),
            "earliest_date_with_20_markets": next(
                (t["date"] for t in tl if t["eligible_markets"] >= 20), None),
            "max_eligible_markets": max((t["eligible_markets"] for t in tl), default=0),
            "eligibility_timeline": tl,
        }

    waterfall = {
        "strict_spec_complete_case_24_primitives": {
            **scenario("strict", list(PRIM_REQS),
                       "All 24 primitives required per (origin, market) row."),
            "markets_never_eligible": never,
            "floor_required": 20,
            "verdict": "BLOCKED_DATA — strict 24-primitive complete-case ceiling "
                       "is 15 markets < 20 floor at EVERY origin",
        },
        "amendment_scenarios_measured_not_endorsed": {
            "A1_drop_bank_neighbor_primitives": scenario(
                "A1", [p for p in PRIM_REQS if p not in ("P07", "P08")],
                "Drop P07/P08 (bank-claims-weighted neighbor returns); "
                "removes C05 from S (16->15 inputs). 22 markets, >=20 from "
                "2010-07-01."),
            "A2_holder_edges_for_bank": scenario(
                "A2_holder", list(PRIM_REQS),  # placeholder; recomputed below
                "Substitute holder (inbound ownership) edges for bank edges in "
                "P07/P08. Changes the economic concept."),
        },
    }
    # A2 recompute: swap bank->holder in P07/P08 requirements
    saved = PRIM_REQS["P07"], PRIM_REQS["P08"]
    PRIM_REQS["P07"] = [("graph_edge_vintages", "holder"), ("t2_levels_daily", "Tot Return Index")]
    PRIM_REQS["P08"] = PRIM_REQS["P07"]
    waterfall["amendment_scenarios_measured_not_endorsed"]["A2_holder_edges_for_bank"] = scenario(
        "A2", list(PRIM_REQS),
        "Substitute holder (inbound ownership) edges for bank edges in P07/P08. "
        "Changes the economic concept; needs a spec amendment.")
    PRIM_REQS["P07"], PRIM_REQS["P08"] = saved

    (OUT / "coverage_waterfall.json").write_text(json.dumps(waterfall, indent=1, default=str))

    # ── market map ────────────────────────────────────────────────────────────
    fx_pair = {
        "EURUSD": ["France", "Germany", "Italy", "Netherlands", "Spain"],
        "GBPUSD": ["U.K."], "AUDUSD": ["Australia"], "USDJPY": ["Japan"],
        "USDCAD": ["Canada"], "USDCHF": ["Switzerland"], "USDSEK": ["Sweden"],
        "USDBRL": ["Brazil"], "USDCLP": ["Chile"], "USDMXN": ["Mexico"],
        "USDCNH": ["ChinaA", "ChinaH"], "USDHKD": ["Hong Kong"],
        "USDINR": ["India"], "USDIDR": ["Indonesia"], "USDKRW": ["Korea"],
        "USDMYR": ["Malaysia"], "USDPHP": ["Philippines"], "USDSGD": ["Singapore"],
        "USDTWD": ["Taiwan"], "USDTHB": ["Thailand"], "USDPLN": ["Poland"],
        "USDZAR": ["South Africa"], "USDTRY": ["Turkey"], "USDSAR": ["Saudi Arabia"],
    }
    pair_of = {c: p for p, cs in fx_pair.items() for c in cs}
    ccy = {"EURUSD": "EUR", "GBPUSD": "GBP", "AUDUSD": "AUD", "USDJPY": "JPY",
           "USDCAD": "CAD", "USDCHF": "CHF", "USDSEK": "SEK", "USDBRL": "BRL",
           "USDCLP": "CLP", "USDMXN": "MXN", "USDCNH": "CNH", "USDHKD": "HKD",
           "USDINR": "INR", "USDIDR": "IDR", "USDKRW": "KRW", "USDMYR": "MYR",
           "USDPHP": "PHP", "USDSGD": "SGD", "USDTWD": "TWD", "USDTHB": "THB",
           "USDPLN": "PLN", "USDZAR": "ZAR", "USDTRY": "TRY", "USDSAR": "SAR",
           "USDDKK": "DKK"}
    bank_f = set(ge[ge.edge_type == "bank"]["focal"].unique())
    trade_f = set(ge[ge.edge_type == "trade"]["focal"].unique())
    holder_f = set(ge[ge.edge_type == "holder"]["focal"].unique())
    region = {  # draft region map — must be frozen at P01 per spec (leave-region-out x6)
        "U.S.": "US", "NASDAQ": "US", "US SmallCap": "US", "Canada": "US",
        "Mexico": "LatAm", "Brazil": "LatAm", "Chile": "LatAm",
        "U.K.": "Europe", "France": "Europe", "Germany": "Europe",
        "Italy": "Europe", "Netherlands": "Europe", "Spain": "Europe",
        "Sweden": "Europe", "Switzerland": "Europe", "Denmark": "Europe",
        "Poland": "Europe", "Turkey": "Europe",
        "Japan": "Asia_DM", "Hong Kong": "Asia_DM", "Singapore": "Asia_DM",
        "Korea": "Asia_EM", "Taiwan": "Asia_EM", "ChinaA": "Asia_EM",
        "ChinaH": "Asia_EM", "India": "Asia_EM", "Indonesia": "Asia_EM",
        "Malaysia": "Asia_EM", "Philippines": "Asia_EM", "Thailand": "Asia_EM",
        "Vietnam": "Asia_EM",
        "Australia": "Pacific_DM", "South Africa": "MEA", "Saudi Arabia": "MEA",
    }
    mm = pd.DataFrame([{
        "market": c, "currency": (ccy.get(pair_of.get(c, ""), "USD")
                                  if c in {"U.S.", "NASDAQ", "US SmallCap"}
                                  else ccy.get(pair_of.get(c, ""),
                                               "DKK" if c == "Denmark" else "VND")),
        "fx_options_pair": pair_of.get(c, ""),
        "fx_forward_pair": "USDDKK" if c == "Denmark" else pair_of.get(c, ""),
        "trade_edge_focal": c in trade_f, "bank_edge_focal": c in bank_f,
        "holder_edge_focal": c in holder_f,
        "draft_region": region.get(c, "?"),
    } for c in T2])
    mm.to_csv(OUT / "market_map.csv", index=False)

    # ── content-addressed snapshot manifest (all 8 files) ────────────────────
    sm = {"snapshot_dir": str(SNAP), "frozen_at": "2026-09-13",
          "note": "loop-DB and main-DB exports taken minutes apart; watermark = "
                  "last completed nightly loop run (2026-09-11 data, jobs finish "
                  "~07:45 PT); two-DB exports are same-batch because neither DB "
                  "was written between the exports (Sunday, no writers active).",
          "files": {}}
    for f in sorted(SNAP.glob("*.parquet")):
        sm["files"][f.name] = {"sha256": sha256_file(f), "bytes": f.stat().st_size}
    (OUT / "snapshot_manifest.json").write_text(json.dumps(sm, indent=1))

    print("strict eligible markets:", len(strict_set), strict_set)
    print("never eligible:", never)
    print("first date with >=20:", waterfall["strict_spec_complete_case_24_primitives"]
          ["earliest_date_with_20_markets"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
