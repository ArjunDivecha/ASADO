#!/usr/bin/env python3
"""
Build a daily country-level decision layer from the daily GDELT signal panel.

This is the daily analog of build_monthly_metronome.py.  Instead of
snapshotting EWMA-smoothed features at month-end and z-scoring over a
24-month trailing window, this script retains every day and z-scores over
a trailing 504 calendar-day window (~24 months).

The same EWMA spans, composite formulae, and cross-sectional ranking logic
are reused so that the daily and monthly signals are methodologically
comparable.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Column specs — mirrors build_monthly_metronome.py
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS = {
    "date",
    "country_iso3",
    "country_name",
    "country_news_sentiment_raw",
    "country_news_risk_raw",
    "local_attention_share",
    "country_news_attention",
    "local_tone",
    "foreign_tone",
    "tone_dispersion",
}

DAILY_Z_COLUMNS = [
    "sentiment_fast_z",
    "sentiment_slow_z",
    "sentiment_trend_z",
    "attention_fast_z",
    "attention_slow_z",
    "attention_trend_z",
    "risk_fast_z",
    "dispersion_fast_z",
    "local_tone_fast_z",
    "foreign_tone_fast_z",
    "local_foreign_gap_z",
]

DAILY_RAW_COLUMNS = [
    "sentiment_fast",
    "sentiment_slow",
    "sentiment_trend",
    "attention_fast",
    "attention_slow",
    "attention_trend",
    "risk_fast",
    "dispersion_fast",
    "local_tone_fast",
    "foreign_tone_fast",
    "local_foreign_gap",
]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the daily GDELT metronome panel (analog of the monthly metronome)"
    )
    parser.add_argument(
        "--daily-panel-parquet",
        default="data/panels/country_signal_daily.parquet",
        help="Input daily signal parquet produced by build_country_signals.py",
    )
    parser.add_argument(
        "--output-parquet",
        default="data/panels/country_signal_daily_metronome.parquet",
        help="Output parquet path for the daily metronome panel",
    )
    parser.add_argument(
        "--output-csv",
        default="data/panels/country_signal_daily_metronome.csv",
        help="Output CSV path for the daily metronome panel",
    )
    parser.add_argument(
        "--fast-span",
        type=int,
        default=5,
        help="EWMA span for the fast feature block (days)",
    )
    parser.add_argument(
        "--slow-span",
        type=int,
        default=20,
        help="EWMA span for the slow feature block (days)",
    )
    parser.add_argument(
        "--risk-span",
        type=int,
        default=10,
        help="EWMA span for risk and dispersion features (days)",
    )
    parser.add_argument(
        "--z-window-days",
        type=int,
        default=504,
        help="Trailing window in calendar days for within-country z-scores (504 ≈ 24 months)",
    )
    parser.add_argument(
        "--min-history-days",
        type=int,
        default=126,
        help="Minimum number of prior days required before a z-score is emitted (126 ≈ 6 months)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Data loading  (same as monthly version)
# ---------------------------------------------------------------------------

def load_daily_panel(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Daily signal panel not found: {path}")

    frame = pd.read_parquet(path)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(
            f"Daily signal panel is missing required columns: {', '.join(missing)}"
        )

    frame = frame.dropna(subset=["country_iso3"]).copy()
    frame["country_iso3"] = frame["country_iso3"].astype(str).str.strip()
    frame = frame.loc[frame["country_iso3"] != ""].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame = frame.sort_values(["country_iso3", "date"]).drop_duplicates(
        subset=["country_iso3", "date"], keep="last"
    )
    return frame


# ---------------------------------------------------------------------------
# Trailing z-score  (same shift-1 convention as monthly)
# ---------------------------------------------------------------------------

def trailing_zscore(series: pd.Series, window: int, min_history: int) -> pd.Series:
    """Z-score using trailing prior observations (shift-1 to avoid look-ahead)."""
    numeric = pd.to_numeric(series, errors="coerce")
    prior = numeric.shift(1)
    mean = prior.rolling(window=window, min_periods=min_history).mean()
    std = prior.rolling(window=window, min_periods=min_history).std(ddof=0)
    std = std.mask(std == 0)
    return (numeric - mean) / std


# ---------------------------------------------------------------------------
# Per-country daily build
# ---------------------------------------------------------------------------

def build_country_daily(
    country_frame: pd.DataFrame,
    fast_span: int,
    slow_span: int,
    risk_span: int,
    z_window_days: int,
    min_history_days: int,
) -> pd.DataFrame:
    """
    Apply EWMA smoothing, trailing z-scores, and composites for one country.

    Unlike the monthly version, every day is retained — there is no month-end
    snapshot filter.
    """
    df = country_frame.sort_values("date").copy()

    # ── EWMA-smoothed feature blocks (identical to monthly) ───────────────
    df["sentiment_fast"] = df["country_news_sentiment_raw"].ewm(
        span=fast_span, adjust=False, min_periods=1
    ).mean()
    df["sentiment_slow"] = df["country_news_sentiment_raw"].ewm(
        span=slow_span, adjust=False, min_periods=1
    ).mean()
    df["sentiment_trend"] = df["sentiment_fast"] - df["sentiment_slow"]

    df["attention_fast"] = df["local_attention_share"].ewm(
        span=fast_span, adjust=False, min_periods=1
    ).mean()
    df["attention_slow"] = df["local_attention_share"].ewm(
        span=slow_span, adjust=False, min_periods=1
    ).mean()
    df["attention_trend"] = df["attention_fast"] - df["attention_slow"]

    df["risk_fast"] = df["country_news_risk_raw"].ewm(
        span=risk_span, adjust=False, min_periods=1
    ).mean()
    df["dispersion_fast"] = df["tone_dispersion"].ewm(
        span=risk_span, adjust=False, min_periods=1
    ).mean()
    df["local_tone_fast"] = df["local_tone"].ewm(
        span=fast_span, adjust=False, min_periods=1
    ).mean()
    df["foreign_tone_fast"] = df["foreign_tone"].ewm(
        span=fast_span, adjust=False, min_periods=1
    ).mean()
    df["local_foreign_gap"] = df["local_tone_fast"] - df["foreign_tone_fast"]

    # ── Trailing z-scores (daily window instead of monthly window) ────────
    for base in DAILY_RAW_COLUMNS:
        df[f"{base}_z"] = trailing_zscore(
            df[base], window=z_window_days, min_history=min_history_days
        )

    # ── Composites (same formula as monthly) ──────────────────────────────
    df["daily_metronome"] = (
        0.35 * df["sentiment_fast_z"]
        + 0.20 * df["sentiment_slow_z"]
        + 0.20 * df["sentiment_trend_z"]
        + 0.15 * df["attention_fast_z"]
        - 0.10 * df["risk_fast_z"]
    )
    df["daily_risk"] = (
        0.45 * df["risk_fast_z"]
        + 0.30 * df["dispersion_fast_z"]
        - 0.15 * df["sentiment_fast_z"]
        - 0.10 * df["foreign_tone_fast_z"]
    )
    df["daily_defensive"] = -1.0 * df["daily_risk"]

    return df


# ---------------------------------------------------------------------------
# Cross-sectional ranks
# ---------------------------------------------------------------------------

def add_cross_sectional_ranks(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["daily_metronome_rank_pct"] = frame.groupby("date")[
        "daily_metronome"
    ].rank(pct=True)
    frame["daily_risk_rank_pct"] = frame.groupby("date")[
        "daily_risk"
    ].rank(pct=True)
    frame["daily_defensive_rank_pct"] = frame.groupby("date")[
        "daily_defensive"
    ].rank(pct=True)
    return frame


# ---------------------------------------------------------------------------
# Column ordering
# ---------------------------------------------------------------------------

def finalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    preferred = [
        "date",
        "country_iso3",
        "country_name",
        *DAILY_RAW_COLUMNS,
        *DAILY_Z_COLUMNS,
        "daily_metronome",
        "daily_risk",
        "daily_defensive",
        "daily_metronome_rank_pct",
        "daily_risk_rank_pct",
        "daily_defensive_rank_pct",
        # Carry through useful raw columns if present
        "country_news_sentiment_raw",
        "country_news_risk_raw",
        "country_news_attention",
        "local_attention_share",
        "local_tone",
        "foreign_tone",
        "tone_dispersion",
        "attention_shock",
        "n_articles",
        "local_n_articles",
        "day_status",
        "gkg_fetch_share",
    ]
    present = [column for column in preferred if column in frame.columns]
    remainder = [column for column in frame.columns if column not in present]
    result = frame[present + remainder].copy()
    result = result.sort_values(["date", "country_iso3"]).reset_index(drop=True)
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    input_path = Path(args.daily_panel_parquet)
    output_parquet = Path(args.output_parquet)
    output_csv = Path(args.output_csv)
    output_parquet.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    daily = load_daily_panel(input_path)
    metronome_frames = []
    for _iso3, country_frame in daily.groupby("country_iso3", sort=False):
        metronome_frames.append(
            build_country_daily(
                country_frame=country_frame,
                fast_span=args.fast_span,
                slow_span=args.slow_span,
                risk_span=args.risk_span,
                z_window_days=args.z_window_days,
                min_history_days=args.min_history_days,
            )
        )

    if not metronome_frames:
        raise ValueError("No country data found in the daily signal panel")

    panel = pd.concat(metronome_frames, ignore_index=True)
    panel = add_cross_sectional_ranks(panel)
    panel = finalize_columns(panel)

    panel.to_parquet(output_parquet, index=False)
    panel.to_csv(output_csv, index=False)

    print(f"saved {output_parquet}")
    print(f"saved {output_csv}")
    print(
        f"days={panel['date'].nunique()} "
        f"countries={panel['country_iso3'].nunique()} "
        f"rows={len(panel)}"
    )


if __name__ == "__main__":
    main()
