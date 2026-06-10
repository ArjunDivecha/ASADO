#!/usr/bin/env python3
"""
Unified incremental pipeline: GDELT source → monthly fullhistory workbook.

Single command that:
  1. Fetches any new daily data from GDELT (incremental – skips cached dates)
  2. Computes daily signals from all cached country-day files
  3. Computes monthly metronome features
  4. Exports the final Excel workbook

The only persistent cache is data/country_day/*.parquet (one file per date).
No intermediate panel files are required.

Usage:
    python3 scripts/build_fullhistory_workbook.py
    python3 scripts/build_fullhistory_workbook.py --workers 4
    python3 scripts/build_fullhistory_workbook.py --start-date 2020-01-01
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Ensure scripts/ is on sys.path so we can import sibling modules
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from gdelt_support import ensure_support_files, fetch_bytes, load_gkg_urls_by_date  # noqa: E402

# Reuse core logic from existing pipeline modules
from build_country_signals import (  # noqa: E402
    compute_country_signals,
    load_aggregate_panel,
    load_manifest_coverage,
)
from build_monthly_metronome import (  # noqa: E402
    MONTHLY_RAW_COLUMNS,
    add_cross_sectional_ranks,
    build_country_monthly,
    finalize_columns,
)
from build_daily_metronome import (  # noqa: E402
    DAILY_RAW_COLUMNS,
    build_country_daily,
    add_cross_sectional_ranks as daily_add_cross_sectional_ranks,
    finalize_columns as daily_finalize_columns,
)
from export_country_sentiment_workbook import (  # noqa: E402
    COUNTRY_BUCKETS,
    INDICATORS,
    add_readme_sheet,
    add_variable_dictionary_sheet,
    build_indicator_panel,
    make_style_book,
    populate_sheet,
)
from export_daily_workbook import (  # noqa: E402
    export_daily_workbook,
    load_daily_panel as load_daily_metronome_panel,
)

# ---------------------------------------------------------------------------
# Project root (one level above scripts/)
# ---------------------------------------------------------------------------
PROJECT_ROOT = _SCRIPT_DIR.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Unified pipeline: GDELT → monthly fullhistory workbook"
    )
    parser.add_argument(
        "--start-date",
        default="2015-02-18",
        help="Earliest date to consider fetching (default: GKG v2 start).",
    )
    parser.add_argument(
        "--end-date",
        default="",
        help="Latest date to fetch (default: yesterday).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Parallel workers for GDELT day fetching.",
    )
    parser.add_argument(
        "--output",
        default="output/spreadsheet/GDELT.xlsx",
        help="Path to the output Excel workbook.",
    )
    parser.add_argument(
        "--template-xlsx",
        default="",
        help="Optional template workbook to borrow styles from.",
    )
    parser.add_argument(
        "--country-day-dir",
        default="data/country_day",
        help="Directory for daily country aggregate parquet files (cache).",
    )
    parser.add_argument(
        "--manifest-dir",
        default="data/manifests/country_day",
        help="Directory for per-day manifest JSON files.",
    )
    parser.add_argument(
        "--lookups-dir",
        default="data/lookups",
        help="Directory for lookup files (masterfilelist, country codes, etc.).",
    )
    parser.add_argument(
        "--panels-dir",
        default="data/panels",
        help="Directory for intermediate signal panels (used with --save-panels). "
             "Pass an absolute path to override the project-relative default "
             "(ASADO wires this to Data/gdelt/panels).",
    )
    parser.add_argument(
        "--signal-window",
        type=int,
        default=30,
        help="Trailing lookback window in days for daily z-scored features.",
    )
    parser.add_argument(
        "--signal-min-history",
        type=int,
        default=10,
        help="Minimum prior observations for daily z-scores.",
    )
    parser.add_argument(
        "--fast-span",
        type=int,
        default=5,
        help="EWMA span for fast monthly features.",
    )
    parser.add_argument(
        "--slow-span",
        type=int,
        default=20,
        help="EWMA span for slow monthly features.",
    )
    parser.add_argument(
        "--risk-span",
        type=int,
        default=10,
        help="EWMA span for risk and dispersion features.",
    )
    parser.add_argument(
        "--z-window-months",
        type=int,
        default=24,
        help="Trailing monthly window for within-country z-scores.",
    )
    parser.add_argument(
        "--min-history-months",
        type=int,
        default=6,
        help="Minimum months before emitting monthly z-scores.",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Skip the GDELT fetch step; just rebuild from cached country-day files.",
    )
    parser.add_argument(
        "--save-panels",
        action="store_true",
        help="Also save intermediate daily and monthly panel parquet/CSV files.",
    )
    parser.add_argument(
        "--fetch-workers",
        type=int,
        default=8,
        help="Parallel threads per day for downloading GKG ZIP files (intra-day parallelism).",
    )
    parser.add_argument(
        "--daily",
        action="store_true",
        help="Also produce a daily-frequency workbook (GDELT_DAILY.xlsx).",
    )
    parser.add_argument(
        "--output-daily",
        default="output/spreadsheet/GDELT_DAILY.xlsx",
        help="Path to the daily output Excel workbook (used with --daily).",
    )
    parser.add_argument(
        "--z-window-days",
        type=int,
        default=504,
        help="Trailing window in calendar days for daily z-scores (504 ≈ 24 months).",
    )
    parser.add_argument(
        "--min-history-days",
        type=int,
        default=126,
        help="Minimum prior days before emitting daily z-scores (126 ≈ 6 months).",
    )
    return parser.parse_args()


# ── Step 1: Refresh masterfilelist and fetch new days ─────────────────────


def refresh_masterfilelist(lookups_dir: Path) -> Path:
    """Re-download masterfilelist if it is stale (>12 hours old)."""
    path = lookups_dir / "masterfilelist.txt"
    if path.exists():
        age_hours = (time.time() - path.stat().st_mtime) / 3600
        if age_hours > 12:
            print(f"masterfilelist is {age_hours:.1f}h old – refreshing")
            path.unlink()
    # ensure_support_files will re-download if missing
    return path


def discover_cached_dates(country_day_dir: Path) -> set[str]:
    """Return set of YYYY-MM-DD date labels already cached locally."""
    if not country_day_dir.exists():
        return set()
    return {p.stem for p in country_day_dir.glob("*.parquet")}


def discover_available_dates(masterfilelist_path: Path) -> set[str]:
    """Parse the masterfilelist to find all date keys with GKG data."""
    dates = set()
    with masterfilelist_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.strip().split()
            if not parts:
                continue
            url = parts[-1]
            if not url.endswith(".gkg.csv.zip"):
                continue
            basename = url.rsplit("/", 1)[-1]
            raw_key = basename[:8]  # YYYYMMDD
            try:
                dt = datetime.strptime(raw_key, "%Y%m%d").date()
                dates.add(dt.isoformat())
            except ValueError:
                continue
    return dates


def find_dates_to_fetch(
    country_day_dir: Path,
    masterfilelist_path: Path,
    start_date: date,
    end_date: date | None = None,
) -> list[str]:
    """Return sorted list of date labels that need fetching."""
    cached = discover_cached_dates(country_day_dir)
    available = discover_available_dates(masterfilelist_path)

    start_label = start_date.isoformat()
    end_label = end_date.isoformat() if end_date else (max(available) if available else start_label)

    missing = sorted(
        d for d in available
        if d not in cached and start_label <= d <= end_label
    )
    return missing


def fetch_single_day(date_label: str, lookups_dir: str, output_dir: str, manifest_dir: str, fetch_workers: int = 8) -> str:
    """Run stream_build_country_day.py for a single date via subprocess."""
    cmd = [
        sys.executable,
        str(_SCRIPT_DIR / "stream_build_country_day.py"),
        "--date", date_label,
        "--lookups-dir", lookups_dir,
        "--output-dir", output_dir,
        "--manifest-dir", manifest_dir,
        "--fetch-workers", str(fetch_workers),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return f"ok {date_label}"
    except subprocess.CalledProcessError as exc:
        return f"FAIL {date_label}: {exc.stderr[:200] if exc.stderr else exc}"


def fetch_new_days(
    dates: list[str],
    lookups_dir: str,
    output_dir: str,
    manifest_dir: str,
    workers: int,
    fetch_workers: int = 8,
) -> None:
    """Fetch all missing days in parallel."""
    if not dates:
        print("no new dates to fetch")
        return

    print(f"fetching {len(dates)} new dates ({dates[0]} → {dates[-1]}) with {workers} workers")
    completed = 0
    total = len(dates)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(fetch_single_day, d, lookups_dir, output_dir, manifest_dir, fetch_workers): d
            for d in dates
        }
        for future in as_completed(futures):
            completed += 1
            result = future.result()
            print(f"  [{completed}/{total}] {result}")

    print(f"fetch complete: {completed} dates processed")


# ── Step 2: Build daily signals ───────────────────────────────────────────


def build_daily_signal_panel(
    country_day_dir: Path,
    manifest_dir: Path,
    window: int,
    min_history: int,
) -> pd.DataFrame:
    """Load all country-day files and compute daily signal panel in memory."""
    print("loading country-day parquet files...")
    frame = load_aggregate_panel(country_day_dir)
    print(f"  loaded {len(frame)} rows, {frame['date'].nunique()} dates, {frame['country_iso3'].nunique()} countries")

    manifest_frame = load_manifest_coverage(manifest_dir)
    if not manifest_frame.empty:
        frame = frame.merge(manifest_frame, on="date", how="left", validate="many_to_one")

    print("computing daily signals...")
    signals = compute_country_signals(
        frame,
        window=window,
        min_history=min_history,
        observation_windows=False,
    )
    print(f"  daily signal panel: {len(signals)} rows")
    return signals


# ── Step 3: Build monthly metronome ───────────────────────────────────────


def _prepare_metronome_frame(daily_signals: pd.DataFrame) -> pd.DataFrame:
    """Common cleaning/prep for both monthly and daily metronome builds."""
    from build_monthly_metronome import REQUIRED_COLUMNS
    missing = sorted(REQUIRED_COLUMNS - set(daily_signals.columns))
    if missing:
        raise ValueError(f"Daily signal panel missing columns for metronome build: {', '.join(missing)}")

    frame = daily_signals.dropna(subset=["country_iso3"]).copy()
    frame["country_iso3"] = frame["country_iso3"].astype(str).str.strip()
    frame = frame.loc[frame["country_iso3"] != ""].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame = frame.sort_values(["country_iso3", "date"]).drop_duplicates(
        subset=["country_iso3", "date"], keep="last"
    )
    return frame


def build_monthly_panel(
    daily_signals: pd.DataFrame,
    fast_span: int,
    slow_span: int,
    risk_span: int,
    z_window_months: int,
    min_history_months: int,
) -> pd.DataFrame:
    """Compute monthly metronome panel from daily signal panel in memory."""
    print("building monthly metronome...")
    frame = _prepare_metronome_frame(daily_signals)

    monthly_frames = []
    for _iso3, country_frame in frame.groupby("country_iso3", sort=False):
        monthly_frames.append(
            build_country_monthly(
                country_frame=country_frame,
                fast_span=fast_span,
                slow_span=slow_span,
                risk_span=risk_span,
                z_window_months=z_window_months,
                min_history_months=min_history_months,
            )
        )

    if not monthly_frames:
        raise ValueError("No country data found for monthly metronome build")

    monthly = pd.concat(monthly_frames, ignore_index=True)
    monthly = add_cross_sectional_ranks(monthly)
    monthly = finalize_columns(monthly)

    print(
        f"  monthly panel: {len(monthly)} rows, "
        f"{monthly['signal_month'].nunique()} months, "
        f"{monthly['country_iso3'].nunique()} countries"
    )
    return monthly


# ── Step 3b: Build daily metronome ────────────────────────────────────────


def build_daily_metronome_panel(
    daily_signals: pd.DataFrame,
    fast_span: int,
    slow_span: int,
    risk_span: int,
    z_window_days: int,
    min_history_days: int,
) -> pd.DataFrame:
    """Compute daily metronome panel from daily signal panel in memory."""
    print("building daily metronome...")
    frame = _prepare_metronome_frame(daily_signals)

    daily_frames = []
    for _iso3, country_frame in frame.groupby("country_iso3", sort=False):
        daily_frames.append(
            build_country_daily(
                country_frame=country_frame,
                fast_span=fast_span,
                slow_span=slow_span,
                risk_span=risk_span,
                z_window_days=z_window_days,
                min_history_days=min_history_days,
            )
        )

    if not daily_frames:
        raise ValueError("No country data found for daily metronome build")

    panel = pd.concat(daily_frames, ignore_index=True)
    panel = daily_add_cross_sectional_ranks(panel)
    panel = daily_finalize_columns(panel)

    print(
        f"  daily metronome panel: {len(panel)} rows, "
        f"{panel['date'].nunique()} days, "
        f"{panel['country_iso3'].nunique()} countries"
    )
    return panel


# ── Step 4: Export workbook ───────────────────────────────────────────────


def prepare_workbook_frame(monthly: pd.DataFrame) -> pd.DataFrame:
    """Prepare the monthly panel for workbook export (same transforms as load_panel)."""
    frame = monthly.copy()
    frame = frame.dropna(subset=["country_iso3"])
    frame["country_iso3"] = frame["country_iso3"].astype(str).str.strip()
    frame = frame.loc[frame["country_iso3"] != ""].copy()

    if "signal_month_end_date" in frame.columns:
        frame["row_date"] = pd.to_datetime(frame["signal_month_end_date"]).dt.normalize()
    elif "signal_month" in frame.columns:
        frame["row_date"] = (
            pd.to_datetime(frame["signal_month"].astype(str), errors="coerce")
            .dt.to_period("M")
            .dt.to_timestamp(how="end")
            .dt.normalize()
        )
    else:
        frame["row_date"] = pd.to_datetime(frame["date"]).dt.normalize()

    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()

    # Flag partial (month-to-date) months instead of dropping them.
    # A month is partial when the last observed day is earlier than the calendar month-end.
    if "month_end_date_used" in frame.columns and "signal_month_end_date" in frame.columns:
        used = pd.to_datetime(frame["month_end_date_used"]).dt.normalize()
        cal_end = pd.to_datetime(frame["signal_month_end_date"]).dt.normalize()
        frame["is_partial_month"] = used < cal_end
    else:
        frame["is_partial_month"] = False

    # Shift row_date to the first of the next month
    frame["row_date"] = (frame["row_date"] + pd.offsets.MonthBegin(1)).dt.normalize()

    frame = frame.sort_values(["row_date", "country_iso3", "date"]).drop_duplicates(
        subset=["row_date", "country_iso3"], keep="last"
    )
    return frame


def export_workbook(monthly: pd.DataFrame, output_path: Path, template_xlsx: str) -> None:
    """Export monthly panel to Excel workbook."""
    print(f"exporting workbook to {output_path}...")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    frame = prepare_workbook_frame(monthly)
    wb, style_refs = make_style_book(template_xlsx)
    add_readme_sheet(wb, frame)
    add_variable_dictionary_sheet(wb, frame)

    sheet_count = 0
    for sheet_name, indicator in INDICATORS:
        if indicator not in frame.columns:
            continue
        wide = build_indicator_panel(frame, indicator)
        ws = wb.create_sheet(sheet_name)
        populate_sheet(ws, wide, sheet_name, indicator, style_refs)
        sheet_count += 1

    wb.save(output_path)
    print(
        f"  saved {output_path} "
        f"({sheet_count} sheets, "
        f"{frame['row_date'].nunique()} dates, "
        f"{len(COUNTRY_BUCKETS)} country buckets)"
    )


# ── Main ──────────────────────────────────────────────────────────────────


def main() -> None:
    args = parse_args()

    # Resolve all paths relative to project root
    country_day_dir = PROJECT_ROOT / args.country_day_dir
    manifest_dir = PROJECT_ROOT / args.manifest_dir
    lookups_dir = PROJECT_ROOT / args.lookups_dir
    output_path = PROJECT_ROOT / args.output

    end_date = (
        datetime.strptime(args.end_date, "%Y-%m-%d").date()
        if args.end_date
        else None
    )
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()

    # ── Step 1: Fetch new days from GDELT ──
    if not args.skip_fetch:
        refresh_masterfilelist(lookups_dir)
        support = ensure_support_files(lookups_dir)
        dates_to_fetch = find_dates_to_fetch(
            country_day_dir, support["masterfilelist"], start_date, end_date
        )
        fetch_new_days(
            dates_to_fetch,
            str(lookups_dir),
            str(country_day_dir),
            str(manifest_dir),
            args.workers,
            args.fetch_workers,
        )
    else:
        print("skipping GDELT fetch (--skip-fetch)")

    # ── Step 2: Build daily signals ──
    daily_signals = build_daily_signal_panel(
        country_day_dir,
        manifest_dir,
        window=args.signal_window,
        min_history=args.signal_min_history,
    )

    # ── Step 3: Build monthly metronome ──
    monthly = build_monthly_panel(
        daily_signals,
        fast_span=args.fast_span,
        slow_span=args.slow_span,
        risk_span=args.risk_span,
        z_window_months=args.z_window_months,
        min_history_months=args.min_history_months,
    )

    # ── Step 3b: Build daily metronome (if --daily) ──
    daily_metronome = None
    if args.daily:
        daily_metronome = build_daily_metronome_panel(
            daily_signals,
            fast_span=args.fast_span,
            slow_span=args.slow_span,
            risk_span=args.risk_span,
            z_window_days=args.z_window_days,
            min_history_days=args.min_history_days,
        )

    # ── Step 4: Optionally save intermediate panels ──
    if args.save_panels:
        panels_dir = PROJECT_ROOT / args.panels_dir
        panels_dir.mkdir(parents=True, exist_ok=True)

        daily_parquet = panels_dir / "country_signal_daily.parquet"
        daily_csv = panels_dir / "country_signal_daily.csv"
        daily_signals.to_parquet(daily_parquet, index=False)
        daily_signals.to_csv(daily_csv, index=False)
        print(f"  saved {daily_parquet}")
        print(f"  saved {daily_csv}")

        monthly_parquet = panels_dir / "country_signal_monthly_fullhistory.parquet"
        monthly_csv = panels_dir / "country_signal_monthly_fullhistory.csv"
        monthly.to_parquet(monthly_parquet, index=False)
        monthly.to_csv(monthly_csv, index=False)
        print(f"  saved {monthly_parquet}")
        print(f"  saved {monthly_csv}")

        if daily_metronome is not None:
            dm_parquet = panels_dir / "country_signal_daily_metronome.parquet"
            dm_csv = panels_dir / "country_signal_daily_metronome.csv"
            daily_metronome.to_parquet(dm_parquet, index=False)
            daily_metronome.to_csv(dm_csv, index=False)
            print(f"  saved {dm_parquet}")
            print(f"  saved {dm_csv}")

    # ── Step 5: Export workbooks ──
    export_workbook(monthly, output_path, args.template_xlsx)

    if daily_metronome is not None:
        daily_output = PROJECT_ROOT / args.output_daily
        # Prepare frame for export (add row_date)
        daily_metronome["row_date"] = pd.to_datetime(daily_metronome["date"]).dt.normalize()
        export_daily_workbook(daily_metronome, daily_output, args.template_xlsx)

    print("\ndone.")


if __name__ == "__main__":
    main()
