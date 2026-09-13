# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/features.py
#
# P03 — causal feature primitives (AM-1: 21 active of 24) and the 15-input S
# representation. All inputs are the frozen P01 snapshot parquets; every value
# at (origin, market) uses only information available at the 23:59 UTC origin.
#
# Normalization contract (PRD §7.5): per primitive on its own natural axis,
# z over up to 252 prior valid observations EXCLUDING the current one,
# >=126 required, ddof=1, clip [-3,3]; sd <= 1e-12 -> unavailable.
#
# Freshness contract (PRD §7.4): latest source observation <= 4 calendar days
# old (and, for session sources, at most one missed session — identical given
# mark-derived sessions). Consensus levels persist but the feed must have
# printed within the preceding 5 local sessions. Graph weights use vintage
# (applies_from) validity, not daily freshness.
#
# AM-1 changes: P07/P08/P11 removed; C05 removed; C06 = (Z(P09)+Z(P10))/2.
# S = {C01..C04, C06..C12, G01..G04} = 15 inputs. X = all 21 primitives.
# =============================================================================
from __future__ import annotations

import numpy as np
import pandas as pd

# AM-1 market universe (22)
MARKETS = [
    "Australia", "Brazil", "Canada", "ChinaA", "France", "Germany", "India",
    "Indonesia", "Italy", "Japan", "Korea", "Mexico", "Netherlands", "Poland",
    "Singapore", "South Africa", "Spain", "Sweden", "Switzerland", "Thailand",
    "Turkey", "U.K.",
]

REVISION_TOL = 0.049   # ECFC reports to 0.1pp; |d| > 0.049 = real revision
FRESH_DAYS = 4         # max calendar days a source obs may lag the origin
GRAPH_MIN_ENTITIES = 3
GRAPH_MIN_MASS = 0.80

Z_WINDOW, Z_MIN = 252, 126

SESSION_PRIMS = ["P01", "P02", "P03", "P04", "P13", "P14", "P15", "P16"]
SOURCE_PRIMS = ["P09", "P10", "P12"]            # market-level source-day series
GLOBAL_PRIMS = ["P21", "P22", "P23", "P24"]
GRAPH_PRIMS = ["P05", "P06"]
CONS_PRIMS = ["P17", "P18", "P19", "P20"]
ALL_PRIMS = (SESSION_PRIMS + GRAPH_PRIMS + SOURCE_PRIMS +
             CONS_PRIMS + GLOBAL_PRIMS)


def zscore_trailing(s: pd.Series, window: int = Z_WINDOW,
                    min_obs: int = Z_MIN) -> pd.Series:
    """Trailing z excluding the current value; sd<=1e-12 -> NaN; clip +-3."""
    prev = s.shift(1)
    mu = prev.rolling(window, min_periods=min_obs).mean()
    sd = prev.rolling(window, min_periods=min_obs).std(ddof=1)
    z = (s - mu) / sd.where(sd > 1e-12)
    return z.clip(-3, 3)


def asof_values(src_dates: np.ndarray, src_vals: np.ndarray,
                query_dates: np.ndarray, max_age_days: int | None = None):
    """Latest source value at each query date. Returns (values, obs_dates).
    If max_age_days is set, values older than that are NaN (obs date kept)."""
    idx = np.searchsorted(src_dates, query_dates, side="right") - 1
    vals = np.full(len(query_dates), np.nan)
    obs = np.empty(len(query_dates), dtype="datetime64[ns]")
    ok = idx >= 0
    vals[ok] = src_vals[idx[ok]]
    obs[ok] = src_dates[idx[ok]]
    obs[~ok] = np.datetime64("NaT")
    if max_age_days is not None:
        age = (query_dates - obs) / np.timedelta64(1, "D")
        vals[~np.isfinite(age) | (age > max_age_days)] = np.nan
    return vals, obs


# ---------------------------------------------------------------------------
# Session-axis primitives: P01-P04 (own returns/vol), P13-P16 (sovereign),
# computed per market on its own session sequence.
# ---------------------------------------------------------------------------
def session_primitives(cal: pd.DataFrame, sov: pd.DataFrame) -> pd.DataFrame:
    """Per (market, session_idx): P01-P04, P13-P16 raw values + obs dates."""
    out = []
    sov2 = sov[sov["variable"] == "SOV_2Y_YIELD_PCT"]
    sov10 = sov[sov["variable"] == "SOV_10Y_YIELD_PCT"]
    for mkt, g in cal.groupby("market"):
        g = g.sort_values("session_idx").reset_index(drop=True)
        tri = g["tri_close"]
        r1 = tri.pct_change()
        f = pd.DataFrame({
            "market": mkt, "session_idx": g["session_idx"], "date": g["date"],
            "P01": tri / tri.shift(5) - 1.0,
            "P02": tri / tri.shift(21) - 1.0,
            "P03": tri / tri.shift(63) - 1.0,
            "P04": r1.rolling(21, min_periods=21).std(ddof=1),
        })
        sdates = g["date"].values
        for var, alias in ((sov2, "sov2y"), (sov10, "sov10y")):
            s = var[var["country"] == mkt].sort_values("date")
            v, obs = asof_values(pd.to_datetime(s["date"]).values,
                                 s["value"].values, sdates)
            f[alias] = v
            f[alias + "_obs"] = obs
        f["P13"] = f["sov2y"]
        f["P14"] = f["sov10y"]
        f["P15"] = f["sov10y"] - f["sov2y"]
        f["P16"] = f["sov2y"] - f["sov2y"].shift(21)
        out.append(f)
    return pd.concat(out, ignore_index=True)


# ---------------------------------------------------------------------------
# Graph impulse: P05/P06 = PIT trade-weighted neighbor trailing 21/63-session
# returns, rebuilt from graph_edge_vintages + session marks (spec §7.2:
# non-self weights normalized to 1, one rep market per entity — the edge
# table already uses one market per economy — >=3 entities and >=80% of
# pre-missingness mass usable, else unavailable; coverage recorded).
# Evaluated on the DAILY origin axis: neighbor marks are each <=4 days old.
# ---------------------------------------------------------------------------
def neighbor_return_matrix(cal: pd.DataFrame, horizon: int,
                           all_dates: pd.DatetimeIndex) -> pd.DataFrame:
    """(date x market) trailing-`horizon`-session return of the market's
    latest session <= date, NaN if that session is older than 4 days."""
    cols = {}
    for mkt, g in cal.groupby("market"):
        g = g.sort_values("session_idx")
        r = g["tri_close"].values / np.roll(g["tri_close"].values, horizon) - 1.0
        r[:horizon] = np.nan
        v, _ = asof_values(g["date"].values, r, all_dates.values,
                           max_age_days=FRESH_DAYS)
        cols[mkt] = v
    return pd.DataFrame(cols, index=all_dates)


def graph_impulse(edges: pd.DataFrame, R: pd.DataFrame) -> pd.DataFrame:
    """Per (date, focal): weighted neighbor return + support stats.

    edges: graph_edge_vintages filtered to edge_type='trade'.
    R: neighbor_return_matrix output (dates x neighbor markets).
    Returns long frame: date, market, value, mass_used, n_entities, status.
    """
    edges = edges.copy()
    edges["applies_from"] = pd.to_datetime(edges["applies_from"])
    vintages = np.sort(edges["applies_from"].unique())
    rows = []
    for focal, fe in edges.groupby("focal"):
        for v_end, seg in fe.groupby("applies_from"):
            w = seg.set_index("neighbor")["weight"].clip(lower=0)
            w = w[~w.index.duplicated(keep="first")]
            w = w[w.index.isin(R.columns)]
            w = w / w.sum() if w.sum() > 0 else w * np.nan
            # vintage applies on [applies_from, next applies_from)
            nxt = vintages[vintages > v_end]
            lo, hi = pd.Timestamp(v_end), (pd.Timestamp(nxt[0])
                                           if len(nxt) else R.index.max()
                                           + pd.Timedelta(days=1))
            dmask = (R.index >= lo) & (R.index < hi)
            sub = R.loc[dmask, w.index]
            usable = sub.notna()
            mass_used = usable.mul(w, axis=1).sum(axis=1)
            n_ent = usable.sum(axis=1)
            total_mass = w.sum()  # 1.0 after normalize (pre-missingness mass)
            val = sub.mul(w, axis=1).sum(axis=1) / mass_used.replace(0, np.nan)
            ok = (n_ent >= GRAPH_MIN_ENTITIES) & (mass_used >= GRAPH_MIN_MASS)
            d = pd.DataFrame({
                "date": sub.index, "market": focal, "value": val,
                "mass_used": mass_used, "n_entities": n_ent,
                "status": np.where(ok, "OK", "LOW_SUPPORT")})
            d.loc[~ok, "value"] = np.nan
            rows.append(d)
    return pd.concat(rows, ignore_index=True)


# ---------------------------------------------------------------------------
# Consensus revision primitives (origin-axis; spec §7.3). For origin date D:
#   F = year(D)+1; comparisons at market's last 21 sessions <= D; value at
#   each comparison = as-of consensus level for (market, F). Revisions are
#   |d| > REVISION_TOL. P17/P18 = signed sum (GDP/CPI); P19 = distinct
#   session buckets where either changed; P20 = sessions since last event
#   (full available F-history; NaN if none). Feed gate: a consensus row for
#   the market (any target) within its last 5 sessions, else unavailable.
# ---------------------------------------------------------------------------
def consensus_at_origins(cons: pd.DataFrame, cal: pd.DataFrame,
                         origin_dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Per (origin date, market): P17/P18/P19/P20.

    For market m and target year F we build the full as-of consensus level
    series on m's session axis (one step-function lookup per session), then:
      P17 = signed sum of GDP revisions (|d|>tol) over last 21 sessions
      P18 = same for CPI
      P19 = distinct session buckets where either series revised, in window
      P20 = sessions since the last revision event for F (full history; if
            none, sessions since the F series' first observation)
    A window contributes only if the market has >=2 valid comparison levels;
    the feed gate (any consensus row within m's last 5 sessions) must hold.
    """
    cons = cons.copy()
    cons["date"] = pd.to_datetime(cons["date"])
    F_years = np.sort(np.unique(origin_dates.year + 1))
    rows = []
    for mkt, g in cal.groupby("market"):
        sdates = g.sort_values("session_idx")["date"].values
        n_sess = len(sdates)
        sidx = np.searchsorted(sdates, origin_dates.values, side="right") - 1
        # feed-observation gate: latest consensus row (any target) >= date of
        # the session 5 positions back
        feed = cons[cons["country"] == mkt].sort_values("date")
        _, feed_obs = asof_values(feed["date"].values,
                                  feed["date"].values.astype("int64"),
                                  origin_dates.values)
        s5 = np.full(len(origin_dates), np.datetime64("NaT"),
                     dtype="datetime64[ns]")
        ok5 = sidx >= 4
        s5[ok5] = sdates[sidx[ok5] - 4]
        feed_ok = feed_obs >= s5

        p17 = np.full(len(origin_dates), np.nan)
        p18 = np.full(len(origin_dates), np.nan)
        p19 = np.full(len(origin_dates), np.nan)
        p20 = np.full(len(origin_dates), np.nan)

        for F in F_years:
            omask = origin_dates.year + 1 == F
            if not omask.any():
                continue
            V = {}
            for var, key in (("CONS_GDP_PCT", "g"), ("CONS_CPI_PCT", "c")):
                src = cons[(cons["country"] == mkt) &
                           (cons["target_year"] == F) &
                           (cons["variable"] == var)].sort_values("date")
                if len(src):
                    v, _ = asof_values(src["date"].values, src["value"].values,
                                       sdates)
                else:
                    v = np.full(n_sess, np.nan)
                V[key] = v
            Vg, Vc = V["g"], V["c"]
            dg = np.concatenate([[np.nan], np.diff(Vg)])
            dc = np.concatenate([[np.nan], np.diff(Vc)])
            rg = np.abs(dg) > REVISION_TOL
            rc = np.abs(dc) > REVISION_TOL
            ev = rg | rc
            # cumulative sums let the 21-session window be position arithmetic
            cs_rg = np.nancumsum(np.where(rg, dg, 0.0))
            cs_rc = np.nancumsum(np.where(rc, dc, 0.0))
            cs_ev = np.cumsum(ev)
            has_any = np.cumsum(~np.isnan(Vg) | ~np.isnan(Vc)) > 0
            # last revision position <= p (full F history)
            ev_pos = np.where(ev, np.arange(n_sess), -1)
            last_ev = np.maximum.accumulate(ev_pos)
            first_pos = np.argmax(has_any) if has_any.any() else n_sess

            pos = sidx[omask]          # latest session index per origin
            p = pos.copy()             # window = positions (p-20 .. p); a
                                       # revision is attributed to the
                                       # session where the level first differs
            valid = (p >= 0)
            # need >=2 comparison points in the window -> p >= 1 at least;
            # window may be shorter early on: use max(p-21, 0) lower bound.
            lo = np.maximum(p - 21, -1)
            in_w = valid & (p >= 1)
            p17[omask] = np.where(in_w, cs_rg[np.clip(p, 0, n_sess - 1)] -
                                  np.where(lo >= 0, cs_rg[np.clip(lo, 0, n_sess - 1)], 0.0), np.nan)
            p18[omask] = np.where(in_w, cs_rc[np.clip(p, 0, n_sess - 1)] -
                                  np.where(lo >= 0, cs_rc[np.clip(lo, 0, n_sess - 1)], 0.0), np.nan)
            p19[omask] = np.where(in_w, cs_ev[np.clip(p, 0, n_sess - 1)] -
                                  np.where(lo >= 0, cs_ev[np.clip(lo, 0, n_sess - 1)], 0), np.nan)
            le = last_ev[np.clip(p, 0, n_sess - 1)]
            p20[omask] = np.where(in_w & has_any[np.clip(p, 0, n_sess - 1)],
                                  np.where(le >= 0, p - le,
                                           p - first_pos), np.nan)
            # positions before the F series begins -> all NaN (p < first_pos)
            early = p < first_pos
            for arr in (p17, p18, p19, p20):
                tmp = arr[omask]; tmp[early] = np.nan; arr[omask] = tmp

        # feed gate + session existence gate
        dead = ~feed_ok | (sidx < 0)
        for arr in (p17, p18, p19, p20):
            arr[dead] = np.nan
        rows.append(pd.DataFrame({
            "date": origin_dates, "market": mkt, "P17": p17, "P18": p18,
            "P19": p19, "P20": p20,
            "status": np.where(np.isnan(p17), "MISSING", "OK")}))
    return pd.concat(rows, ignore_index=True)


# ---------------------------------------------------------------------------
# Source-day primitives: FX surface (P09/P10/P12) per market; globals
# (P21/P22 levels, P23/P24 21-obs returns) once on the GLOBAL axis.
# ---------------------------------------------------------------------------
def market_source_panel(mi: pd.DataFrame) -> pd.DataFrame:
    """Per (date, market): P09, P10, P12 raw source-day values."""
    piv = mi.pivot_table(index=["date", "country"], columns="variable",
                         values="value")
    piv["P09"] = piv["FX_IMPVOL_3M_PCT"]
    piv["P10"] = piv["FX_IMPVOL_1W_PCT"] - piv["FX_IMPVOL_3M_PCT"]
    piv["P12"] = piv["FX_CARRY_3M_PCT"]
    out = piv[["P09", "P10", "P12"]].reset_index()
    out["date"] = pd.to_datetime(out["date"])
    return out[out["country"].isin(MARKETS)]


def global_source_panel(mi: pd.DataFrame) -> pd.DataFrame:
    """Per date on the GLOBAL axis: P21 VIX, P22 MOVE, P23 DXY 21-obs ret,
    P24 Brent front generic 21-obs return (quoted level incl. roll jumps —
    PIT convention documented in the manifest)."""
    g = mi[mi["country"] == "GLOBAL"].pivot_table(
        index="date", columns="variable", values="value")
    g["P21"] = g["RISK_VIX"]
    g["P22"] = g["RISK_MOVE"]
    g["P23"] = g["RISK_DXY"] / g["RISK_DXY"].shift(21) - 1.0
    g["P24"] = g["CMD_CO1"] / g["CMD_CO1"].shift(21) - 1.0
    out = g[["P21", "P22", "P23", "P24"]].reset_index()
    out["date"] = pd.to_datetime(out["date"])
    return out


# ---------------------------------------------------------------------------
# S representation (AM-1): C05 removed; C06 = (Z9+Z10)/2.
# ---------------------------------------------------------------------------
S_MAP = {
    "C01": ("Z", "P02"), "C02": ("Z", "P03"), "C03": ("Z", "P04"),
    "C04": ("Z", "P05"),
    "C06": ("AVG", ["P09", "P10"]),                    # AM-1 weights 0.5/0.5
    "C07": ("Z", "P12"), "C08": ("Z", "P15"), "C09": ("Z", "P16"),
    "C10": ("Z", "P17"), "C11": ("Z", "P18"),
    "C12": ("AVG2", ("P19", "P20")),                   # (Z19 - Z20)/2
    "G01": ("Z", "P21"), "G02": ("Z", "P22"),
    "G03": ("Z", "P23"), "G04": ("Z", "P24"),
}


def build_S(Z: pd.DataFrame) -> pd.DataFrame:
    """Z: frame with ZP01..ZP24 columns (active set). Returns S columns."""
    out = pd.DataFrame(index=Z.index)
    for cname, spec in S_MAP.items():
        kind = spec[0]
        if kind == "Z":
            out[cname] = Z[f"Z{spec[1]}"]
        elif kind == "AVG":
            out[cname] = Z[[f"Z{p}" for p in spec[1]]].mean(axis=1)
        elif kind == "AVG2":
            a, b = spec[1]
            out[cname] = (Z[f"Z{a}"] - Z[f"Z{b}"]) / 2.0
    return out
