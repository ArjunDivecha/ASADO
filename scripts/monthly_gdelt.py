#!/usr/bin/env python3
"""Strict monthly GDELT staging; all writes below a monthly run's staging root.

Input: ASADO/Data/gdelt/{country_day,manifests,lookups} copied by monthly_stage.py.
Output: staged completed-month caches, manifest, panels and GDELT.xlsx; no canonical
write or daily export. Reuses scripts/gdelt_ingest/ logic with one HTTP attempt.
"""
import argparse
import calendar
from datetime import date, timedelta
from pathlib import Path
import sys
from monthly_readiness import read, atomic, sha


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--context", type=Path, required=True)
    ap.add_argument("--day")
    args = ap.parse_args()
    c = read(args.context)
    base = Path(c["run"]) / "stage/ASADO/Data/gdelt"
    code = Path(c["root"]) / "scripts/gdelt_ingest"
    sys.path.insert(0, str(code))
    import gdelt_support as support
    original_fetch = support.fetch_bytes
    def once(url, retries=1, timeout=60):
        from monthly_owner import assert_owner
        assert_owner(c)
        return original_fetch(url, retries=1, timeout=timeout)
    support.fetch_bytes = once
    if args.day:
        import stream_build_country_day as stream
        stream.fetch_bytes = once
        sys.argv = [str(code / "stream_build_country_day.py"), "--date", args.day,
                    "--output-dir", str(base / "country_day"), "--manifest-dir", str(base / "manifests/country_day"),
                    "--lookups-dir", str(base / "lookups"), "--fetch-workers", "4"]
        stream.main()
        return
    import build_fullhistory_workbook as builder
    builder.fetch_bytes = once
    support_ready = False
    y, m = map(int, c["observation_month"].split("-"))
    import subprocess
    days = []
    for day in range(1, calendar.monthrange(y, m)[1] + 1):
        d = f"{y:04d}-{m:02d}-{day:02d}"
        p = base / "country_day" / (d + ".parquet")
        manifest = base / "manifests/country_day" / (d + ".json")
        meta = read(manifest, {})
        complete = p.exists() and meta.get("status") == "ok" and meta.get("gkg_fetch_share") == 1.0 and meta.get("gkg_files_missing") == 0 and meta.get('gkg_files_expected')==96 and meta.get('gkg_files_fetched')==96
        if not complete:
            if not support_ready:
                builder.refresh_masterfilelist(base / "lookups")
                support.ensure_support_files(base / "lookups")
                support_ready = True
            # Only the staging copy is discarded; canonical caches are untouched.
            p.unlink(missing_ok=True); manifest.unlink(missing_ok=True)
            subprocess.run([sys.executable, str(Path(__file__)), "--context", str(args.context), "--day", d], check=True)
            meta = read(manifest, {})
        if not p.exists() or meta.get("status") != "ok" or meta.get("gkg_fetch_share") != 1.0 or meta.get("gkg_files_missing") != 0 or meta.get('gkg_files_expected')!=96 or meta.get('gkg_files_fetched')!=96:
            raise RuntimeError("Incomplete GDELT day; no retry/publication: " + d)
        days.append(d)
    # All required target days are independently checked, not trusted to a
    # fetch loop's exit code (legacy fetch_new_days prints some failures).
    sys.argv = [str(code / "build_fullhistory_workbook.py"), "--skip-fetch", "--save-panels", "--completed-months-only",
                "--country-day-dir", str(base / "country_day"), "--manifest-dir", str(base / "manifests/country_day"),
                "--lookups-dir", str(base / "lookups"), "--panels-dir", str(base / "panels"),
                "--output", str(base / "spreadsheet/GDELT.xlsx")]
    builder.main()
    files=[]
    for d in days:
        manifest=base/'manifests/country_day'/(d+'.json')
        meta=read(manifest)
        meta['output_path']=str(Path(c['root'])/'Data/gdelt/country_day'/(d+'.parquet'))
        atomic(manifest,meta)
        files.append(dict(date=d,parquet_sha256=sha(base/'country_day'/(d+'.parquet')),manifest_sha256=sha(manifest),expected_gkg_files=96,fetched_gkg_files=96))
    atomic(Path(c["run"]) / "GDELT_SOURCE_VALIDATED.json", {"complete_days": days, "files":files,"failed_days": [], "http_retries": 0})


if __name__ == "__main__":
    main()
