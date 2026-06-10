#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: snapshot_vintages.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/processed/*
  Every collector output panel (parquet), variable catalog (csv), and run
  metadata (json) currently on disk. Read-only; nothing is modified.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/vintages/{YYYY_MM}/processed/*
  A byte-for-byte copy of Data/processed/ frozen for the calendar month.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/vintages/{YYYY_MM}/manifest.json
  Per-file inventory: size, sha256, source mtime, plus snapshot timestamp.

VERSION: 1.0
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 0b)

DESCRIPTION:
Freezes a point-in-time "vintage" of every processed data panel, once per
calendar month. Why: most macro sources silently revise history, so a panel
read today is NOT what was knowable last year. By saving a copy of every
monthly pull starting now, future research can ask "what did the data say at
the time?" instead of trusting revised history. This is the cheapest possible
insurance against lookahead bias (PRD_Alpha_Hunting_Loop.md, section 8,
priority 2). A 10th grader's version: we photocopy the whole filing cabinet
on the first pull of each month, so nobody can quietly rewrite the past.

DEPENDENCIES:
- Python standard library only (shutil, hashlib, json, argparse).

USAGE:
 python scripts/snapshot_vintages.py            # snapshot current month (no-op if exists)
 python scripts/snapshot_vintages.py --force    # overwrite current month's vintage
 python scripts/snapshot_vintages.py --check    # list existing vintages, verify manifests
 python scripts/snapshot_vintages.py --month 2026_07   # snapshot under an explicit label

NOTES:
- Idempotent: one vintage per calendar month. A second run in the same month
  is a loud no-op unless --force is passed (FAIL-IS-FAIL: it never silently
  overwrites).
- ~166 MB per vintage at current panel sizes (~2 GB/year). Stored inside the
  repo's Data/ tree (Dropbox-backed).
- Run automatically as part of the monthly update, or by hand after any
  ad-hoc collector run worth preserving.
=============================================================================
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "Data" / "processed"
VINTAGES_DIR = BASE_DIR / "Data" / "vintages"


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    """Stream a file's sha256 so large parquets don't load into memory."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def build_manifest(src_dir: Path) -> dict:
    files = sorted(p for p in src_dir.rglob("*") if p.is_file())
    entries = []
    for p in files:
        stat = p.stat()
        entries.append(
            {
                "relpath": str(p.relative_to(src_dir)),
                "bytes": stat.st_size,
                "source_mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "sha256": sha256_of(p),
            }
        )
    return {
        "snapshot_ts": datetime.now().isoformat(timespec="seconds"),
        "source_dir": str(src_dir),
        "n_files": len(entries),
        "total_bytes": sum(e["bytes"] for e in entries),
        "files": entries,
    }


def snapshot(month_label: str, force: bool) -> int:
    if not PROCESSED_DIR.exists():
        print(f"ERROR: source directory does not exist: {PROCESSED_DIR}")
        return 1

    target = VINTAGES_DIR / month_label
    if target.exists():
        if not force:
            print(f"Vintage {month_label} already exists at {target} - refusing to overwrite.")
            print("Pass --force to replace it.")
            return 0
        print(f"--force: removing existing vintage {target}")
        shutil.rmtree(target)

    print(f"Building manifest for {PROCESSED_DIR} ...")
    manifest = build_manifest(PROCESSED_DIR)

    print(f"Copying {manifest['n_files']} files ({manifest['total_bytes'] / 1e6:.0f} MB) -> {target}/processed/")
    (target).mkdir(parents=True, exist_ok=True)
    shutil.copytree(PROCESSED_DIR, target / "processed")

    manifest_path = target / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Vintage {month_label} written. Manifest: {manifest_path}")
    return 0


def check() -> int:
    if not VINTAGES_DIR.exists():
        print("No vintages directory yet - nothing snapshotted.")
        return 0
    months = sorted(d for d in VINTAGES_DIR.iterdir() if d.is_dir())
    if not months:
        print("Vintages directory exists but is empty.")
        return 0
    print(f"{len(months)} vintage(s):")
    rc = 0
    for m in months:
        manifest_path = m / "manifest.json"
        if not manifest_path.exists():
            print(f"  {m.name}: MISSING manifest.json")
            rc = 1
            continue
        manifest = json.loads(manifest_path.read_text())
        n_on_disk = sum(1 for p in (m / "processed").rglob("*") if p.is_file())
        ok = "OK" if n_on_disk == manifest["n_files"] else f"MISMATCH (disk={n_on_disk})"
        print(
            f"  {m.name}: {manifest['n_files']} files, "
            f"{manifest['total_bytes'] / 1e6:.0f} MB, snapshot {manifest['snapshot_ts']} [{ok}]"
        )
        if ok != "OK":
            rc = 1
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze a monthly vintage of Data/processed/.")
    parser.add_argument("--month", default=datetime.now().strftime("%Y_%m"), help="Vintage label (default: current YYYY_MM).")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing vintage for the month.")
    parser.add_argument("--check", action="store_true", help="List and verify existing vintages.")
    args = parser.parse_args()

    if args.check:
        return check()
    return snapshot(args.month, args.force)


if __name__ == "__main__":
    sys.exit(main())
