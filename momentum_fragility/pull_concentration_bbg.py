#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: pull_concentration_bbg.py
=============================================================================

DESCRIPTION:
    Momentum Fragility Index -- Component 7 (Concentration) Bloomberg ingestion.
    (PRD "Momentum Fragility Index", section 2.3.)

    For each of the 34 T2 countries, this script pulls the constituent
    holdings + weights of that country's representative US-listed ETF at
    quarterly snapshots from 2016-06-30 through the most recent completed
    calendar quarter-end, then computes two concentration measures per
    country per quarter:

        top_5_weight       = sum of the 5 largest constituent weights (%)
        tech_sector_weight = sum of constituent weights (%) whose current
                             GICS_SECTOR_NAME == 'Information Technology'

    Holdings + weights come from a BQL query over //blp/bqlsvc with the
    EXCEL clientContext unlock (bds()-based FUND_HOLDINGS is silently blocked
    over DAPI). GICS sector labels come from a SEPARATE plain ReferenceData
    (ref_batch) call per quarter's constituent list -- GICS is NOT requested
    inside the BQL holdings() call. Because a ticker's current GICS sector is
    identical regardless of which ETF/quarter it appears in, GICS lookups are
    cached per-ticker within the run to cut Bloomberg hits (this is a caching
    optimization, not a spec change; sectors are effectively static).

    The country->ETF map is loaded from the authoritative
    config/etf_t2_map.json (all 34 T2 countries have a verified primary US
    ETF; this file is consistent with AssetList.xlsx's Yahoo/Bloomberg
    sheets). No guessed mapping is used.

    Results are cached INCREMENTALLY: each (country, quarter) cell is written
    to an append-only CSV as soon as it is computed, and every Bloomberg call
    is logged to a pull-log CSV. Re-running skips already-completed cells, so
    an interrupted run resumes without re-pulling (Bloomberg data is precious
    -- repo convention). The final tidy panel is written atomically to
    concentration_panel.parquet.

    FAIL IS FAIL: per-cell failures are logged and skipped (so one bad
    country/quarter does not kill the run), but nothing is simulated or
    back-filled with fake values. A Bloomberg quota/capacity error aborts the
    whole run immediately (never retried).

INPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/etf_t2_map.json
        Authoritative map: each of the 34 T2 country names -> {primary ETF
        ticker, alternates}. Only 'primary' is used here.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/src/utils.py
        Provides T2_COUNTRIES (the canonical 34-country list) for reconciliation.
    Bloomberg Terminal (live) via OpusBloomberg (/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg)
        //blp/bqlsvc  -- holdings + weights (BQL, EXCEL unlock)
        //blp/refdata -- GICS_SECTOR_NAME (ReferenceData, ref_batch)

OUTPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility/results/concentration_panel.parquet
        Final tidy panel: columns [date, country, top_5_weight,
        tech_sector_weight, n_holdings_used]. date = quarter-end Timestamp,
        weights in percent (0-100).
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility/results/_cache_cells.csv
        Append-only incremental cache of every computed (country, quarter)
        cell (with status). Read on resume to skip completed cells.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility/results/pull_log.csv
        Append-only Bloomberg call log: timestamp, ticker, quarter, call_type,
        status, n_rows, notes.

VERSION: 1.0
LAST UPDATED: 2026-07-05
AUTHOR: Arjun Divecha (built by Claude Code)

DEPENDENCIES:
    - blpapi, pandas, numpy, pyarrow
    - OpusBloomberg (bbg.py: BBG, bloomberg_setup, detect_vm_ip)

USAGE:
    conda run -p "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv" \
        python3 "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility/pull_concentration_bbg.py"

NOTES:
    - Quarterly cadence only (holdings do not change fast; quota-metered pull).
    - Weights reliable from ~2016-06-30 onward; earlier dates degrade to zero
      / raise "Unable to evaluate universe" -- expected, not a bug; we do not
      pull before 2016.
    - Constituent rows are filtered to those whose id() contains "Equity"
      (drops futures-overlay and "USD Curncy" cash lines).
    - Read-only philosophy: this script never writes to the DuckDB warehouse.
=============================================================================
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import blpapi
import numpy as np
import pandas as pd

# --- OpusBloomberg on path -------------------------------------------------
OPUS_BLOOMBERG_DIR = "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg"
if OPUS_BLOOMBERG_DIR not in sys.path:
    sys.path.insert(0, OPUS_BLOOMBERG_DIR)
from bbg import BBG, bloomberg_setup, detect_vm_ip  # noqa: E402

# --- Paths -----------------------------------------------------------------
MODULE_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility")
RESULTS_DIR = MODULE_DIR / "results"
ETF_MAP_PATH = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/etf_t2_map.json")
REGIME_SRC = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/src")

PANEL_PATH = RESULTS_DIR / "concentration_panel.parquet"
CACHE_PATH = RESULTS_DIR / "_cache_cells.csv"
PULL_LOG_PATH = RESULTS_DIR / "pull_log.csv"

START_QUARTER = "2016-06-30"   # weights unreliable before this (PRD 2.3)
BQL_TIMEOUT_MS = 180_000
TECH_SECTOR = "Information Technology"

CACHE_FIELDS = [
    "date", "country", "ticker",
    "top_5_weight", "tech_sector_weight", "n_holdings_used", "status", "notes",
]

# Capacity-error signatures -> STOP, never retry (bloomberg-skill/bql.md).
_CAPACITY_SIGNS = (
    "daily capacity", "dly lmt", "mth lmt", "bql compute capacity",
    "request is blocked", "#n/a", "-4001", "-4002", "capacity",
)


# ---------------------------------------------------------------------------
# T2 country -> ETF map
# ---------------------------------------------------------------------------
def load_country_etf_map() -> dict[str, str]:
    """Return {country: 'TICKER US Equity'} for all mappable T2 countries."""
    sys.path.insert(0, str(REGIME_SRC))
    from utils import T2_COUNTRIES  # noqa: E402

    raw = json.loads(ETF_MAP_PATH.read_text())["map"]
    out: dict[str, str] = {}
    unmapped: list[str] = []
    for country in T2_COUNTRIES:
        entry = raw.get(country)
        primary = entry.get("primary") if entry else None
        if primary:
            out[country] = f"{primary} US Equity"
        else:
            unmapped.append(country)
    if unmapped:
        print(f"[WARN] Unmapped T2 countries (skipped): {unmapped}")
    print(f"[INFO] Mapped {len(out)}/{len(T2_COUNTRIES)} T2 countries to ETF tickers.")
    return out


def quarter_end_dates(start: str) -> list[str]:
    """Quarter-end dates from `start` through the most recent completed quarter."""
    today = pd.Timestamp(date.today())
    # Most recent quarter-end strictly on/before today.
    end = today.to_period("Q").to_timestamp(how="end").normalize()
    if end > today:
        end = (today.to_period("Q") - 1).to_timestamp(how="end").normalize()
    rng = pd.date_range(start=start, end=end, freq="QE")
    return [d.strftime("%Y-%m-%d") for d in rng]


# ---------------------------------------------------------------------------
# BQL client (EXCEL-unlock pattern from 13F/scripts/screen_hedge_funds_bql.py)
# ---------------------------------------------------------------------------
class BqlClient:
    def __init__(self, host: str, timeout_ms: int = BQL_TIMEOUT_MS) -> None:
        self.host = host
        self.timeout_ms = timeout_ms
        self.session: blpapi.Session | None = None

    def __enter__(self) -> "BqlClient":
        opts = blpapi.SessionOptions()
        opts.setServerHost(self.host)
        opts.setServerPort(8194)
        self.session = blpapi.Session(opts)
        if not self.session.start():
            raise ConnectionError(f"Failed to start Bloomberg session at {self.host}:8194")
        if not self.session.openService("//blp/bqlsvc"):
            raise ConnectionError("Failed to open //blp/bqlsvc")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.session:
            self.session.stop()

    def execute(self, expression: str) -> list[Any]:
        assert self.session is not None
        service = self.session.getService("//blp/bqlsvc")
        request = service.createRequest("sendQuery")
        request.set("expression", expression)
        try:
            request.getElement("clientContext").setElement("appName", "EXCEL")
        except blpapi.NotFoundException:
            pass

        self.session.sendRequest(request)
        responses: list[Any] = []
        while True:
            event = self.session.nextEvent(self.timeout_ms)
            if event.eventType() == blpapi.Event.TIMEOUT:
                raise TimeoutError(f"BQL request timed out after {self.timeout_ms} ms")
            for msg in event:
                if msg.hasElement("responseError"):
                    err = msg.getElement("responseError")
                    raise RuntimeError(err.getElementAsString("message"))
                responses.append(msg.toPy())
            if event.eventType() == blpapi.Event.RESPONSE:
                break
        return responses


def _is_capacity_error(text: str) -> bool:
    low = str(text).lower()
    return any(sig in low for sig in _CAPACITY_SIGNS)


def parse_holdings(responses: list[Any]) -> pd.DataFrame:
    """
    Parse a `get(id(), weights()) for(holdings(...))` BQL response into a tidy
    DataFrame with columns ['ticker', 'weight'] (weight raw, units as returned).

    BQL sendQuery results are a dict keyed by field name (e.g. 'id()',
    'weights()'); each field content has an idColumn (row keys) and a
    valuesColumn, plus optional secondaryColumns. We reassemble per row key.
    """
    exceptions: list[str] = []
    # row_key -> {col_name: value}
    rows: dict[str, dict[str, Any]] = {}

    for response in responses:
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except json.JSONDecodeError:
                continue
        if not isinstance(response, dict):
            continue

        resp_exc = response.get("responseExceptions")
        if resp_exc:
            for ex in resp_exc:
                if isinstance(ex, dict):
                    exceptions.append(
                        ex.get("message") or ex.get("internalMessage") or str(ex)
                    )
            continue

        results = response.get("results")
        if not isinstance(results, dict):
            continue

        for field_name, content in results.items():
            if not isinstance(content, dict):
                continue
            id_vals = content.get("idColumn", {}).get("values", []) or []
            val_vals = content.get("valuesColumn", {}).get("values", []) or []
            for k, v in zip(id_vals, val_vals):
                key = str(k)
                rows.setdefault(key, {})["__ID__"] = key
                rows[key][field_name] = v
            for sec in content.get("secondaryColumns", []) or []:
                sname = sec.get("name")
                svals = sec.get("values", []) or []
                if not sname:
                    continue
                for k, v in zip(id_vals, svals):
                    rows.setdefault(str(k), {})[sname] = v

    if exceptions:
        joined = " | ".join(exceptions)
        if _is_capacity_error(joined):
            raise RuntimeError(f"BQL CAPACITY error (STOP): {joined}")
        raise RuntimeError(f"BQL error: {joined}")

    if not rows:
        raise RuntimeError("BQL holdings response contained no rows")

    df = pd.DataFrame(list(rows.values()))

    # Identify ticker column: prefer 'id()' field; else the row-key ID.
    ticker_col = None
    for cand in ("id()", "ID()", "id"):
        if cand in df.columns:
            ticker_col = cand
            break
    if ticker_col is None:
        ticker_col = "__ID__"

    # Identify weight column: prefer 'weights()' field.
    weight_col = None
    for cand in ("weights()", "weight()", "weights", "WEIGHTS()"):
        if cand in df.columns:
            weight_col = cand
            break
    if weight_col is None:
        # last resort: first numeric column that is not the ticker column
        for c in df.columns:
            if c in (ticker_col, "__ID__"):
                continue
            if pd.to_numeric(df[c], errors="coerce").notna().any():
                weight_col = c
                break
    if weight_col is None:
        raise RuntimeError(f"Could not find weights column in BQL response; cols={list(df.columns)}")

    out = pd.DataFrame({
        "ticker": df[ticker_col].astype(str),
        "weight": pd.to_numeric(df[weight_col], errors="coerce"),
    })
    return out


# ---------------------------------------------------------------------------
# Incremental cache helpers
# ---------------------------------------------------------------------------
def load_completed() -> set[tuple[str, str]]:
    """Return set of (date, country) already computed with status == 'ok'."""
    if not CACHE_PATH.exists():
        return set()
    done: set[tuple[str, str]] = set()
    df = pd.read_csv(CACHE_PATH, dtype=str)
    for _, r in df.iterrows():
        if str(r.get("status")) == "ok":
            done.add((str(r["date"]), str(r["country"])))
    return done


def append_cache_row(row: dict[str, Any]) -> None:
    new = not CACHE_PATH.exists()
    with CACHE_PATH.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CACHE_FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in CACHE_FIELDS})
        f.flush()
        os.fsync(f.fileno())


def append_pull_log(ticker: str, quarter: str, call_type: str,
                    status: str, n_rows: int, notes: str = "") -> None:
    new = not PULL_LOG_PATH.exists()
    fields = ["timestamp", "ticker", "quarter", "call_type", "status", "n_rows", "notes"]
    with PULL_LOG_PATH.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerow({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "ticker": ticker, "quarter": quarter, "call_type": call_type,
            "status": status, "n_rows": n_rows, "notes": notes,
        })
        f.flush()
        os.fsync(f.fileno())


def write_panel_atomic() -> pd.DataFrame:
    """Rebuild the final parquet from the ok cells in the cache (atomic write)."""
    if not CACHE_PATH.exists():
        return pd.DataFrame()
    df = pd.read_csv(CACHE_PATH)
    df = df[df["status"] == "ok"].copy()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    for c in ("top_5_weight", "tech_sector_weight", "n_holdings_used"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = (df[["date", "country", "top_5_weight", "tech_sector_weight", "n_holdings_used"]]
          .drop_duplicates(subset=["date", "country"], keep="last")
          .sort_values(["country", "date"])
          .reset_index(drop=True))
    tmp = PANEL_PATH.with_suffix(".parquet.tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, PANEL_PATH)
    return df


# ---------------------------------------------------------------------------
# Per-cell computation
# ---------------------------------------------------------------------------
def compute_cell(bql: BqlClient, bbg: BBG, gics_cache: dict[str, str],
                 country: str, ticker: str, quarter: str) -> dict[str, Any]:
    """Pull holdings for one ETF at one quarter and compute concentration."""
    expr = f"get(id(), weights()) for(holdings('{ticker}', dates='{quarter}'))"

    # --- 1) holdings + weights (BQL) ---
    try:
        responses = bql.execute(expr)
        raw = parse_holdings(responses)
        append_pull_log(ticker, quarter, "holdings", "ok", len(raw))
    except Exception as e:
        if _is_capacity_error(str(e)):
            append_pull_log(ticker, quarter, "holdings", "CAPACITY", 0, str(e)[:200])
            raise
        append_pull_log(ticker, quarter, "holdings", "fail", 0, str(e)[:200])
        return {"date": quarter, "country": country, "ticker": ticker,
                "status": "fail_holdings", "notes": str(e)[:200]}

    # Filter to equity constituents; drop cash/curncy/futures & NaN weights.
    eq = raw[raw["ticker"].str.contains("Equity", case=False, na=False)].copy()
    eq = eq.dropna(subset=["weight"])
    eq = eq[eq["weight"] != 0.0]
    if eq.empty:
        return {"date": quarter, "country": country, "ticker": ticker,
                "status": "empty_after_filter", "notes": f"raw_rows={len(raw)}"}

    # Weight units: normalize to percent (0-100). Detect fraction vs percent.
    wsum = float(eq["weight"].sum())
    if wsum <= 1.5:            # weights sum ~1.0 -> fractions
        eq["weight"] = eq["weight"] * 100.0
        unit_note = f"frac->pct(sum={wsum:.3f})"
    else:
        unit_note = f"pct(sum={wsum:.1f})"

    eq = eq.sort_values("weight", ascending=False).reset_index(drop=True)
    top_5_weight = float(eq["weight"].head(5).sum())
    n_holdings_used = int(len(eq))

    # --- 2) GICS sector (ref_batch) with per-ticker global cache ---
    constituents = eq["ticker"].tolist()
    need = [t for t in constituents if t not in gics_cache]
    if need:
        try:
            batch = bbg.ref_batch(need, ["GICS_SECTOR_NAME"])
            append_pull_log(ticker, quarter, "gics_ref_batch", "ok", len(need),
                            f"new_tickers={len(need)}")
            for t in need:
                val = batch.get(t, {}).get("GICS_SECTOR_NAME")
                if isinstance(val, dict):   # {"error": ...}
                    val = None
                gics_cache[t] = val if val is not None else ""
        except Exception as e:
            if _is_capacity_error(str(e)):
                append_pull_log(ticker, quarter, "gics_ref_batch", "CAPACITY", 0, str(e)[:200])
                raise
            append_pull_log(ticker, quarter, "gics_ref_batch", "fail", 0, str(e)[:200])
            return {"date": quarter, "country": country, "ticker": ticker,
                    "status": "fail_gics", "notes": str(e)[:200]}

    eq["gics"] = eq["ticker"].map(gics_cache)
    tech_sector_weight = float(eq.loc[eq["gics"] == TECH_SECTOR, "weight"].sum())

    return {
        "date": quarter, "country": country, "ticker": ticker,
        "top_5_weight": round(top_5_weight, 4),
        "tech_sector_weight": round(tech_sector_weight, 4),
        "n_holdings_used": n_holdings_used,
        "status": "ok",
        "notes": unit_note,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    country_etf = load_country_etf_map()
    quarters = quarter_end_dates(START_QUARTER)
    print(f"[INFO] Quarters: {len(quarters)} ({quarters[0]} .. {quarters[-1]})")
    total_cells = len(country_etf) * len(quarters)
    print(f"[INFO] Total (country x quarter) cells: {total_cells}")

    completed = load_completed()
    print(f"[INFO] Already-completed cells in cache: {len(completed)} (will skip)")

    # Connect once.
    print("[INFO] bloomberg_setup() ...")
    bloomberg_setup(verbose=True)
    host = detect_vm_ip()
    print(f"[INFO] Bloomberg host: {host}")

    gics_cache: dict[str, str] = {}
    n_ok = n_skip = n_fail = 0

    with BqlClient(host) as bql, BBG(host=host) as bbg:
        for country, ticker in country_etf.items():
            for quarter in quarters:
                key = (quarter, country)
                if key in completed:
                    n_skip += 1
                    continue
                t0 = time.time()
                try:
                    row = compute_cell(bql, bbg, gics_cache, country, ticker, quarter)
                except Exception as e:
                    # Capacity / hard-stop: persist what we have and abort.
                    print(f"[ABORT] {country} {quarter}: {e}")
                    write_panel_atomic()
                    raise
                append_cache_row(row)
                dt = time.time() - t0
                if row.get("status") == "ok":
                    n_ok += 1
                    print(f"[OK]   {country:<13} {quarter}  "
                          f"top5={row['top_5_weight']:.1f}%  "
                          f"tech={row['tech_sector_weight']:.1f}%  "
                          f"n={row['n_holdings_used']}  ({dt:.1f}s)")
                else:
                    n_fail += 1
                    print(f"[FAIL] {country:<13} {quarter}  "
                          f"status={row.get('status')}  {row.get('notes','')[:80]}")
                # Rebuild panel periodically so partial results are durable.
                if (n_ok + n_fail) % 20 == 0:
                    write_panel_atomic()

    panel = write_panel_atomic()
    print(f"\n[DONE] ok={n_ok} skipped={n_skip} fail={n_fail}")
    if not panel.empty:
        print(f"[DONE] Panel: {len(panel)} rows, "
              f"{panel['country'].nunique()} countries, "
              f"{panel['date'].min().date()} .. {panel['date'].max().date()}")
        print(f"[DONE] Written: {PANEL_PATH}")

        # --- Sanity check: Taiwan / Korea most recent quarter ---
        for c in ("Taiwan", "Korea"):
            sub = panel[panel["country"] == c]
            if not sub.empty:
                last = sub.sort_values("date").iloc[-1]
                print(f"[SANITY] {c} {last['date'].date()}: "
                      f"top_5_weight={last['top_5_weight']:.1f}%  "
                      f"tech_sector_weight={last['tech_sector_weight']:.1f}%  "
                      f"n={int(last['n_holdings_used'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
