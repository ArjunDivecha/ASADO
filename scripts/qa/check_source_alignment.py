"""
=============================================================================
SCRIPT NAME: scripts/qa/check_source_alignment.py
=============================================================================

INPUT FILES:
- Data/T2 Master.xlsx       :: original T2 country-factor source workbook
- Data/GDELT.xlsx           :: original GDELT country-sentiment source workbook
- config/country_mapping.json :: canonical country name -> identifier crosswalk

OUTPUT:
- Console report (one line per check, PASS / WARN / FAIL)
- Optional markdown report via --out <path>

VERSION: 1.0
LAST UPDATED: 2026-06-30
AUTHOR: Arjun Divecha (built by agent session)

DESCRIPTION:
Stand-alone alignment / reconciliation check across the ORIGINAL source
workbooks that ship in the repo (T2 Master.xlsx, GDELT.xlsx). It does NOT
need the warehouse (Data/asado.duckdb) and so can run on a fresh clone.

It verifies that the things which must line up before any cross-source join
actually do:

  1. COUNTRY NAMING  - the exact country label strings used by each source,
     and whether they reconcile to the canonical T2 names after a known
     rename map. Mismatched labels are the classic silent-join bug.
  2. DATE GRAIN      - that every source is monthly first-of-month, and that
     one source's date axis is a clean subset of the other's (full overlap).
  3. SLEEVE RESOLUTION - whether a source actually distinguishes the
     market sleeves (ChinaA vs ChinaH; U.S. vs NASDAQ vs US SmallCap) or
     broadcasts one sovereign value to all of them. GDELT broadcasts; T2
     does not. A date x country join is then duplicating, not aligning.
  4. INTERNAL CONSISTENCY - that every sheet inside T2 Master shares one
     identical (date axis x country columns) frame.

Exit code is non-zero if any FAIL-level check trips, so it can gate CI.

DEPENDENCIES:
- pandas, openpyxl

USAGE:
  python scripts/qa/check_source_alignment.py
  python scripts/qa/check_source_alignment.py --out Data/reports/source_alignment.md
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "Data"
CONFIG_PATH = BASE_DIR / "config" / "country_mapping.json"
T2_WORKBOOK = DATA_DIR / "T2 Master.xlsx"
GDELT_WORKBOOK = DATA_DIR / "GDELT.xlsx"

# GDELT display labels -> canonical T2 names. GDELT pivots on country_iso3 and
# uses its own header labels (see scripts/gdelt_ingest/export_country_sentiment_workbook.py
# COUNTRY_BUCKETS); these three differ from the T2 Master headers.
GDELT_TO_T2 = {
    "China A": "ChinaA",
    "China H": "ChinaH",
    "U.S. NASDAQ": "NASDAQ",
}

# Sleeves that share an underlying sovereign. A source that keys on ISO3 cannot
# distinguish the members of each group.
SLEEVE_GROUPS = [
    ("China sovereign", ["ChinaA", "ChinaH"]),
    ("USA sovereign", ["U.S.", "NASDAQ", "US SmallCap"]),
]


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failed = False

    def add(self, level: str, title: str, detail: str = "") -> None:
        if level == "FAIL":
            self.failed = True
        line = f"[{level:4}] {title}"
        if detail:
            line += f"\n         {detail}"
        self.lines.append(line)
        print(line)

    def to_markdown(self) -> str:
        out = ["# Source alignment report", ""]
        for line in self.lines:
            out.append("- " + line.replace("\n         ", " — ").strip())
        return "\n".join(out) + "\n"


def _canonical_countries() -> list[str]:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return list(cfg["countries"].keys())


def _first_col_to_date_index(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={df.columns[0]: "date"})
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")


def _country_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if not str(c).startswith("Unnamed")]


def check_country_naming(rep: Report) -> tuple[set[str], set[str]]:
    canon = set(_canonical_countries())
    t2 = pd.read_excel(T2_WORKBOOK, "1MRet")
    t2_cols = set(_country_columns(_first_col_to_date_index(t2)))
    g = pd.read_excel(GDELT_WORKBOOK, "monthly_metronome")
    g_cols = set(_country_columns(_first_col_to_date_index(g)))

    # T2 vs canonical config
    extra_canon = canon - t2_cols
    if t2_cols - canon:
        rep.add("FAIL", "T2 labels not in canonical config",
                f"{sorted(t2_cols - canon)}")
    else:
        rep.add("PASS", f"T2 uses {len(t2_cols)} labels, all present in canonical config",
                f"(config lists {len(canon)} total; {len(extra_canon)} extra not in T2 universe)")

    # GDELT raw labels vs T2
    raw_diff = g_cols - t2_cols
    if raw_diff:
        rep.add("WARN", "GDELT raw labels differ from T2 (rename required before join)",
                f"GDELT-only: {sorted(raw_diff)}")
    # GDELT after rename
    g_mapped = {GDELT_TO_T2.get(c, c) for c in g_cols}
    if g_mapped == t2_cols:
        rep.add("PASS", "GDELT reconciles to T2 country set after known rename map",
                f"map={GDELT_TO_T2}")
    else:
        rep.add("FAIL", "GDELT does NOT reconcile to T2 even after rename",
                f"GDELT-only: {sorted(g_mapped - t2_cols)}; T2-only: {sorted(t2_cols - g_mapped)}")
    return t2_cols, g_cols


def check_date_grain(rep: Report) -> None:
    t2 = _first_col_to_date_index(pd.read_excel(T2_WORKBOOK, "1MRet"))
    g = _first_col_to_date_index(pd.read_excel(GDELT_WORKBOOK, "monthly_metronome"))

    for name, df in (("T2", t2), ("GDELT", g)):
        if (df.index.day == 1).all():
            rep.add("PASS", f"{name} dates are all monthly first-of-month",
                    f"{df.index.min().date()} .. {df.index.max().date()} ({len(df.index)} months)")
        else:
            bad = [d.date() for d in df.index[df.index.day != 1]][:5]
            rep.add("FAIL", f"{name} has non-first-of-month dates", f"e.g. {bad}")

    missing = g.index.difference(t2.index)
    if len(missing) == 0:
        rep.add("PASS", "GDELT date axis is a clean subset of T2 (full overlap)",
                f"overlap = {len(g.index.intersection(t2.index))} months")
    else:
        rep.add("FAIL", "GDELT has dates absent from T2",
                f"{[d.date() for d in missing][:10]}")


def check_sleeve_resolution(rep: Report) -> None:
    # T2: sleeves must be distinct return series.
    t2 = _first_col_to_date_index(pd.read_excel(T2_WORKBOOK, "1MRet"))
    for label, members in SLEEVE_GROUPS:
        present = [m for m in members if m in t2.columns]
        identical = all(t2[present[0]].equals(t2[m]) for m in present[1:])
        if identical and len(present) > 1:
            rep.add("WARN", f"T2 sleeves identical for {label} (expected distinct)",
                    f"{present}")
        else:
            rep.add("PASS", f"T2 distinguishes {label} sleeves", f"{present}")

    # GDELT: maps members to one ISO3 -> identical broadcast. Flag as caveat.
    g = _first_col_to_date_index(pd.read_excel(GDELT_WORKBOOK, "monthly_metronome"))
    inv = {v: k for k, v in GDELT_TO_T2.items()}
    for label, members in SLEEVE_GROUPS:
        g_members = [inv.get(m, m) for m in members]
        present = [m for m in g_members if m in g.columns]
        if len(present) <= 1:
            continue
        identical = all(g[present[0]].equals(g[m]) for m in present[1:])
        if identical:
            rep.add("WARN",
                    f"GDELT broadcasts ONE value across {label} sleeves (no sleeve resolution)",
                    f"{present} are bit-identical -> a date x country join duplicates sentiment")
        else:
            rep.add("PASS", f"GDELT distinguishes {label} sleeves", f"{present}")


def check_t2_internal(rep: Report) -> None:
    xl = pd.ExcelFile(T2_WORKBOOK)
    base_dates: set | None = None
    base_cols: set | None = None
    issues: list[str] = []
    for sheet in xl.sheet_names:
        df = xl.parse(sheet)
        if df.empty:
            continue
        try:
            df = _first_col_to_date_index(df)
        except (ValueError, TypeError):
            continue
        dates = set(df.index)
        cols = set(_country_columns(df))
        if base_dates is None:
            base_dates, base_cols = dates, cols
            continue
        if cols != base_cols:
            issues.append(f"{sheet}: country columns differ "
                          f"(+{sorted(cols - base_cols)} -{sorted(base_cols - cols)})")
        if dates != base_dates:
            issues.append(f"{sheet}: date axis differs ({len(dates)} vs {len(base_dates)})")
    if issues:
        rep.add("FAIL", "T2 sheets are not internally aligned",
                "; ".join(issues[:10]))
    else:
        rep.add("PASS",
                f"All {len(xl.sheet_names)} T2 sheets share one identical date x country frame")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None,
                        help="optional path to write a markdown report")
    args = parser.parse_args()

    for path in (T2_WORKBOOK, GDELT_WORKBOOK, CONFIG_PATH):
        if not path.exists():
            print(f"ERROR: required input missing: {path}", file=sys.stderr)
            return 2

    rep = Report()
    print("=== Country naming ===")
    check_country_naming(rep)
    print("\n=== Date grain ===")
    check_date_grain(rep)
    print("\n=== Sleeve resolution ===")
    check_sleeve_resolution(rep)
    print("\n=== T2 internal consistency ===")
    check_t2_internal(rep)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rep.to_markdown(), encoding="utf-8")
        print(f"\nWrote {args.out}")

    print("\nRESULT:", "FAIL" if rep.failed else "OK (warnings are by-design caveats)")
    return 1 if rep.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
