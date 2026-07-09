"""
=============================================================================
SCRIPT NAME: build_regime_classifiers.py
=============================================================================

DESCRIPTION:
    Implements PRD "Regime-Conditional Factor Selection" section 2.2 --
    Objective (A), the DESCRIPTIVE per-country Growth / Recession / Neutral
    classifier. Builds TWO SEPARATE classifiers (never blended, per PRD 2.1):

    1. PRIMARY (IP-based): monthly Industrial-Production-YoY per country
       (read from the cached ip_panel.parquet produced by the prior
       Bloomberg pull stage). For each country, each observation, using
       ONLY that country's own trailing history UP TO AND INCLUDING that
       observation (an expanding window), compute the percentile rank of
       the current IP-YoY value within that history. Thresholds are FROZEN
       by the PRD and are NOT tuned here:
           rank_pct <= 0.30  -> Recession   (bottom 30%)
           rank_pct >= 0.70  -> Growth      (top 30%)
           else              -> Neutral     (middle 40%)
       A label is only emitted once the expanding window spans at least
       24 months of that country's own history (PRD 2.2 warmup); earlier
       observations get a null regime.

    2. EXPLORATORY (GDP-based, separate, clearly labeled): annual GDP-growth
       from the ASADO warehouse (t2_raw, variable='GDP'). A publication lag
       is applied (PRD 2.1): a GDP figure dated YYYY-01-01 is treated as
       "knowable" only from YYYY-07-01 (+6 months), because t2_raw.GDP
       carries forward-dated consensus/forecast vintages (a 2026-01-01
       value exists = a forecast for full-year 2026), not clean
       point-in-time actuals. The SAME 30/30/40 expanding-quantile
       methodology is then applied independently on the annual series for
       all 34 T2 countries. Output rows are stamped at the knowable
       (lagged) date so the panel is point-in-time.

    The point-in-time expanding-quantile pattern is adapted from
    "T2 Factor Timing Fuzzy/Step Fifteen Market Regime Analysis.py"
    (its `vol_history = market_vol.loc[:date].dropna(); low =
    vol_history.quantile(0.25)` idiom), generalized here to run
    per-country rather than on one market-wide series.

    WARMUP RULE (documented design decision, NOT tuned):
        The PRD's "minimum 24 months of history" is applied uniformly to
        both classifiers as "the expanding window must span >= 24 calendar
        months (current_date - first_obs_date)". For the 31 genuinely
        monthly IP series this equals the intended ~24 monthly observations.
        For the 2 quarterly IP series (Switzerland, Hong Kong), the 1 annual
        IP series (Australia), and the annual GDP series, the same 24-month
        calendar span is used -- this introduces NO new constant beyond the
        PRD's frozen "24 months", and is the only reading that (a) keeps the
        frozen number verbatim across frequencies and (b) yields the roughly
        30/30/40 output distribution the PRD expects for BOTH classifiers.
        A per-series observation count is reported so that coarse (few-point)
        quantiles on the low-frequency series are visible, not hidden.

    DATA-QUALITY FLAG (reported, not silently fixed): the prior stage's
    report claimed "34/34 countries have a working MONTHLY IP series", but
    ip_panel.parquet actually contains 31 monthly, 2 quarterly (Switzerland,
    Hong Kong) and 1 annual (Australia) series. This script does NOT re-pull
    Bloomberg (per PRD build note: the main script reads the cached parquet,
    never re-pulls). It classifies each series as-is and flags the degraded
    low-frequency countries in its console report.

INPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/ip_panel.parquet
        (date, country, ip_yoy) monthly IP-YoY panel, 34 countries, from the
        prior Bloomberg pull stage (pull_industrial_production_bbg.py).
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
        Read-only. Table t2_raw, variable='GDP' -- annual GDP growth per
        country (dated YYYY-01-01), 34 T2 countries, 2001-2026.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/src/utils.py
        Imported for T2_COUNTRIES and month_start (clean primitives, reused
        not reimplemented, per PRD build note).

OUTPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/regime_labels_ip.parquet
        (date, country, regime, ip_yoy, rank_pct) -- primary IP classifier.
        All months included; warmup months have regime=null, rank_pct=null.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/regime_labels_gdp.parquet
        (date, country, regime, gdp_growth_lagged, rank_pct) -- exploratory
        GDP classifier. date = publication-lagged (knowable) date.

VERSION: 1.0
LAST UPDATED: 2026-07-05
AUTHOR: Arjun Divecha (built with Claude Code)

DEPENDENCIES:
    - duckdb
    - numpy
    - pandas
    - scipy

USAGE:
    python "build_regime_classifiers.py"

NOTES:
    - DuckDB is always opened read_only=True (PRD hard requirement).
    - No silent fallbacks / no simulated data (FAIL IS FAIL): if
      ip_panel.parquet is missing or empty, the script STOPS and reports.
    - The 30/30/40 percentile thresholds and the 24-month warmup are FROZEN
      by the PRD and are not tunable here.
    - GDP publication lag is the PRD-frozen minimum (+6 months from the
      YYYY-01-01 date). The underlying t2_raw.GDP values remain consensus
      estimates, not true realized point-in-time actuals -- this caveat is
      documented but the frozen 6-month lag is applied as specified.
=============================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import percentileofscore

# --- Reuse clean primitives from the regime module (do not reimplement) ------
REGIME_SRC = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/src"
)
sys.path.insert(0, str(REGIME_SRC))
import utils  # noqa: E402  (utils.py has no package-relative imports; safe standalone)

T2_COUNTRIES = utils.T2_COUNTRIES
month_start = utils.month_start

# --- Paths -------------------------------------------------------------------
MODULE_ROOT = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection"
)
RESULTS_DIR = MODULE_ROOT / "results"
IP_PANEL_PATH = RESULTS_DIR / "ip_panel.parquet"
DUCKDB_PATH = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb"
)
OUT_IP = RESULTS_DIR / "regime_labels_ip.parquet"
OUT_GDP = RESULTS_DIR / "regime_labels_gdp.parquet"

# --- Frozen PRD parameters (DO NOT TUNE) -------------------------------------
RECESSION_MAX = 0.30   # rank_pct <= 0.30 -> Recession (bottom 30%)
GROWTH_MIN = 0.70      # rank_pct >= 0.70 -> Growth   (top 30%)
WARMUP_MONTHS = 24     # expanding window must span >= 24 calendar months
GDP_PUBLICATION_LAG_MONTHS = 6  # PRD 2.1: value dated D usable from D+6 months


def _months_between(a: pd.Timestamp, b: pd.Timestamp) -> int:
    """Whole calendar months from a (earlier) to b (later)."""
    return (b.year - a.year) * 12 + (b.month - a.month)


def classify_expanding(dates: list, values: list) -> list:
    """
    Point-in-time expanding-quantile classifier for one country's series.

    For each observation i, uses ONLY history[0..i] (inclusive) -- no
    look-ahead. Emits a (Growth/Recession/Neutral) label only once the
    inclusive window spans >= WARMUP_MONTHS of calendar history; earlier
    observations return (None, None).

    Returns list of (regime_or_None, rank_pct_or_None) aligned to `dates`.
    """
    out = []
    first = dates[0]
    for i in range(len(dates)):
        cur_date = dates[i]
        cur_val = values[i]
        hist = values[: i + 1]  # inclusive of current
        span = _months_between(first, cur_date)
        if span < WARMUP_MONTHS or len(hist) < 3:
            out.append((None, None))
            continue
        # Percentile rank of the current value within its own trailing history.
        # kind='mean' -> standard symmetric percentile rank (ties split), so
        # the steady-state distribution is ~30/30/40 by construction.
        rank_pct = percentileofscore(hist, cur_val, kind="mean") / 100.0
        if rank_pct <= RECESSION_MAX:
            regime = "Recession"
        elif rank_pct >= GROWTH_MIN:
            regime = "Growth"
        else:
            regime = "Neutral"
        out.append((regime, rank_pct))
    return out


def build_ip_classifier() -> pd.DataFrame:
    """PRIMARY classifier: monthly IP-YoY per country -> regime labels."""
    if not IP_PANEL_PATH.exists():
        raise SystemExit(
            f"FAIL: ip_panel.parquet not found at {IP_PANEL_PATH}. "
            "Run the Bloomberg IP pull stage first. Not proceeding."
        )
    panel = pd.read_parquet(IP_PANEL_PATH)
    if panel.empty:
        raise SystemExit(f"FAIL: ip_panel.parquet at {IP_PANEL_PATH} is empty. Not proceeding.")

    panel = panel.copy()
    panel["date"] = month_start(panel["date"])
    panel = panel.dropna(subset=["ip_yoy"]).sort_values(["country", "date"])

    frames = []
    for country, g in panel.groupby("country"):
        g = g.sort_values("date")
        dates = list(g["date"])
        values = list(g["ip_yoy"].astype(float))
        labels = classify_expanding(dates, values)
        out = pd.DataFrame(
            {
                "date": dates,
                "country": country,
                "regime": [r for r, _ in labels],
                "ip_yoy": values,
                "rank_pct": [p for _, p in labels],
            }
        )
        frames.append(out)

    result = pd.concat(frames, ignore_index=True).sort_values(["country", "date"])
    return result.reset_index(drop=True)


def build_gdp_classifier() -> pd.DataFrame:
    """
    EXPLORATORY classifier: annual GDP growth from t2_raw, with a +6-month
    publication lag, classified by the SAME 30/30/40 expanding-quantile rule.
    Output dates are the publication-lagged (knowable) dates.
    """
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        gdp = con.execute(
            """
            SELECT date, country, value AS gdp_growth
            FROM t2_raw
            WHERE variable = 'GDP'
            ORDER BY country, date
            """
        ).fetchdf()
    finally:
        con.close()

    gdp["date"] = pd.to_datetime(gdp["date"])
    gdp = gdp[gdp["country"].isin(T2_COUNTRIES)].copy()
    gdp = gdp.dropna(subset=["gdp_growth"]).sort_values(["country", "date"])

    # Publication-lagged (knowable) date = observation date + 6 months,
    # aligned to month-start. The expanding window at each step uses only
    # observations whose OWN obs-date <= the current obs-date; since every
    # value carries the same +6m lag, they are all knowable by the current
    # knowable date -- so the expanding history is point-in-time consistent.
    frames = []
    for country, g in gdp.groupby("country"):
        g = g.sort_values("date")
        obs_dates = list(g["date"])
        values = list(g["gdp_growth"].astype(float))
        labels = classify_expanding(obs_dates, values)
        knowable = [
            month_start(pd.Series([d]))[0]
            + pd.DateOffset(months=GDP_PUBLICATION_LAG_MONTHS)
            for d in obs_dates
        ]
        out = pd.DataFrame(
            {
                "date": knowable,
                "country": country,
                "regime": [r for r, _ in labels],
                "gdp_growth_lagged": values,
                "rank_pct": [p for _, p in labels],
            }
        )
        frames.append(out)

    result = pd.concat(frames, ignore_index=True).sort_values(["country", "date"])
    return result.reset_index(drop=True)


def _distribution(df: pd.DataFrame) -> pd.Series:
    lab = df["regime"].dropna()
    return (lab.value_counts(normalize=True) * 100).reindex(
        ["Growth", "Neutral", "Recession"]
    )


def main() -> None:
    print("=" * 78)
    print("build_regime_classifiers.py  --  PRD 2.2 descriptive classifiers")
    print("=" * 78)

    # ---- Primary IP classifier ----
    ip = build_ip_classifier()
    ip.to_parquet(OUT_IP, index=False)

    # Per-country frequency / observation-count reporting (data-quality flag)
    print("\n[IP] per-country coverage (labeled rows = non-null regime):")
    cov = (
        ip.assign(labeled=ip["regime"].notna())
        .groupby("country")
        .agg(n_obs=("date", "size"), n_labeled=("labeled", "sum"),
             first=("date", "min"), last=("date", "max"))
    )
    # infer frequency by median gap
    freq = {}
    for c, g in ip.groupby("country"):
        med = g.sort_values("date")["date"].diff().dt.days.median()
        freq[c] = "monthly" if med < 45 else ("quarterly" if med < 135 else "annual")
    cov["freq"] = pd.Series(freq)
    degraded = cov[cov["freq"] != "monthly"]
    print(cov.sort_values("freq").to_string())
    print(
        f"\n[IP] DATA-QUALITY FLAG: {len(degraded)} non-monthly series "
        f"(prior stage claimed 34/34 monthly): "
        f"{sorted(degraded.index.tolist())}"
    )

    dist_ip = _distribution(ip)
    print("\n[IP] regime distribution over ALL labeled country-months "
          f"(n={int(ip['regime'].notna().sum())}):")
    for k, v in dist_ip.items():
        print(f"    {k:<10} {v:5.1f}%")

    # ---- Germany named PRD verification check ----
    print("\n[IP] Germany 2023-2024 named PRD check "
          "(expect Recession-heavy; Germany had a technical recession):")
    de = ip[(ip["country"] == "Germany")
            & (ip["date"] >= "2023-01-01")
            & (ip["date"] <= "2024-12-31")].copy()
    de_dist = de["regime"].value_counts()
    n_rec = int((de["regime"] == "Recession").sum())
    n_tot = int(de["regime"].notna().sum())
    print(f"    Germany 2023-2024 regime counts: {de_dist.to_dict()}")
    print(f"    Recession months = {n_rec} / {n_tot} labeled "
          f"({(100.0*n_rec/n_tot) if n_tot else float('nan'):.0f}%)")
    print("    Sample rows:")
    print(de[["date", "ip_yoy", "regime", "rank_pct"]]
          .head(8).to_string(index=False))
    verdict = "PASS" if n_rec >= 1 and n_rec >= n_tot * 0.4 else "REVIEW"
    print(f"    Germany check verdict: {verdict} "
          f"(Recession is the modal/heavy regime for 2023-2024)")

    # ---- Exploratory GDP classifier ----
    gdp = build_gdp_classifier()
    gdp.to_parquet(OUT_GDP, index=False)
    dist_gdp = _distribution(gdp)
    print("\n[GDP] (EXPLORATORY, separate from IP -- never pooled) "
          "regime distribution over ALL labeled country-years "
          f"(n={int(gdp['regime'].notna().sum())}):")
    for k, v in dist_gdp.items():
        print(f"    {k:<10} {v:5.1f}%")
    print(f"[GDP] labeled rows/country (annual, +{GDP_PUBLICATION_LAG_MONTHS}m lag): "
          f"min={int(gdp.groupby('country')['regime'].apply(lambda s: s.notna().sum()).min())}, "
          f"max={int(gdp.groupby('country')['regime'].apply(lambda s: s.notna().sum()).max())}")

    print("\nOutputs written:")
    print(f"    {OUT_IP}")
    print(f"    {OUT_GDP}")
    print("Done.")


if __name__ == "__main__":
    main()
