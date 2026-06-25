#!/usr/bin/env python3
"""
Refresh the upstream GDELT daily parquet panel for ASADO.

Daily GDELT is intentionally parquet-only. This script does not read, write,
or export Excel workbooks. It owns the missing daily step that ASADO used to
assume had happened elsewhere:

1. Refresh the GDELT repo masterfile list.
2. Build any missing country_day/YYYY-MM-DD.parquet files through target date.
3. Rebuild data/panels/country_signal_daily.parquet.
4. Verify the panel is fresh and non-empty.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_GDELT_REPO = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT")
MASTERFILELIST_URL = "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt"


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [gdelt-refresh] {msg}", flush=True)


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def default_target_date() -> date:
    return date.today() - timedelta(days=1)


def refresh_masterfilelist(repo: Path) -> Path:
    out = repo / "data" / "lookups" / "masterfilelist.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="masterfilelist.", suffix=".txt", dir=str(out.parent))
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        log(f"refreshing GDELT masterfilelist from {MASTERFILELIST_URL}")
        urllib.request.urlretrieve(MASTERFILELIST_URL, tmp)
        if tmp.stat().st_size < 10_000_000:
            raise RuntimeError(f"downloaded masterfilelist is suspiciously small: {tmp.stat().st_size} bytes")
        tmp.replace(out)
    finally:
        if tmp.exists():
            tmp.unlink()
    return out


def latest_master_gkg_date(masterfile: Path) -> date | None:
    latest: date | None = None
    with masterfile.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if ".gkg.csv.zip" not in line:
                continue
            stamp = line.rsplit("/", 1)[-1].split(".", 1)[0]
            if len(stamp) < 8 or not stamp[:8].isdigit():
                continue
            dt = datetime.strptime(stamp[:8], "%Y%m%d").date()
            latest = dt if latest is None or dt > latest else latest
    return latest


def latest_country_day(repo: Path) -> date | None:
    files = sorted((repo / "data" / "country_day").glob("*.parquet"))
    if not files:
        return None
    return parse_date(files[-1].stem)


def panel_max_date(repo: Path) -> date | None:
    panel = repo / "data" / "panels" / "country_signal_daily.parquet"
    if not panel.exists():
        return None
    df = pd.read_parquet(panel, columns=["date"])
    if df.empty:
        return None
    return pd.to_datetime(df["date"], errors="coerce").max().date()


def run(cmd: list[str], repo: Path, timeout: int) -> None:
    log("CMD: " + " ".join(cmd))
    subprocess.run(cmd, cwd=str(repo), check=True, timeout=timeout)


def build_missing_days(repo: Path, target: date, workers: int, timeout: int) -> None:
    latest = latest_country_day(repo)
    start = target if latest is None else latest + timedelta(days=1)
    if start > target:
        log(f"country_day cache already current through {latest}")
        return
    run([
        sys.executable,
        "scripts/stream_backfill_country_day.py",
        "--start-date", start.isoformat(),
        "--end-date", target.isoformat(),
        "--day-workers", str(workers),
    ], repo=repo, timeout=timeout)


def rebuild_signal_panel(repo: Path, timeout: int) -> None:
    run([
        sys.executable,
        "scripts/build_country_signals.py",
        "--country-day-dir", "data/country_day",
        "--manifest-dir", "data/manifests/country_day",
        "--window", "30",
        "--min-history", "10",
    ], repo=repo, timeout=timeout)


def verify(repo: Path, target: date) -> None:
    max_dt = panel_max_date(repo)
    if max_dt is None:
        raise RuntimeError("GDELT signal panel is missing or empty")
    if max_dt < target:
        raise RuntimeError(f"GDELT signal panel stale: max_date={max_dt}, target={target}")
    log(f"GDELT signal panel fresh through {max_dt}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh GDELT daily parquet inputs for ASADO.")
    parser.add_argument("--gdelt-repo", type=Path, default=DEFAULT_GDELT_REPO)
    parser.add_argument("--target-date", default=default_target_date().isoformat())
    parser.add_argument("--day-workers", type=int, default=2)
    parser.add_argument("--skip-master-refresh", action="store_true")
    parser.add_argument("--force-panel-rebuild", action="store_true")
    parser.add_argument("--backfill-timeout-sec", type=int, default=7200)
    parser.add_argument("--panel-timeout-sec", type=int, default=1800)
    args = parser.parse_args()

    repo = args.gdelt_repo.expanduser().resolve()
    if not repo.exists():
        raise FileNotFoundError(repo)
    target = parse_date(args.target_date)

    master = repo / "data" / "lookups" / "masterfilelist.txt"
    if not args.skip_master_refresh or not master.exists():
        master = refresh_masterfilelist(repo)
    latest_master = latest_master_gkg_date(master)
    if latest_master is None or latest_master < target:
        raise RuntimeError(f"GDELT masterfilelist stale: latest={latest_master}, target={target}")
    log(f"masterfilelist latest GKG date: {latest_master}")

    build_missing_days(repo, target, args.day_workers, args.backfill_timeout_sec)

    panel_dt = panel_max_date(repo)
    if args.force_panel_rebuild or panel_dt is None or panel_dt < target:
        rebuild_signal_panel(repo, args.panel_timeout_sec)
    else:
        log(f"signal panel already current through {panel_dt}")

    verify(repo, target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
