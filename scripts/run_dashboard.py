#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run_dashboard.py
=============================================================================

DESCRIPTION:
    Serves a live, auto-refreshing HTML dashboard over HTTP to monitor an ASADO
    monthly_update pipeline run in real time. The dashboard shows two panels:

    1. Pipeline — lists every stage as it runs (done / running / failed) with
       elapsed time and per-stage metrics (variables processed, row counts,
       date ranges, output files written) parsed from the monthly update log.
    2. Warehouse — for each DuckDB table, shows row count, distinct variables,
       and the latest data date. Queries the database read-only; displays
       "rebuilding" while the DB is locked.

    The server is a pure stdlib HTTP server. It re-parses the log file and
    re-queries DuckDB on every page load (5-second auto-refresh via meta tag).

INPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/logs/monthly_update_*.log
        Run log files produced by the ASADO monthly_update pipeline. The
        dashboard auto-discovers the newest file by modification time, or
        accepts an explicit path via --log. Parsed for STEP banners, timestamps,
        metrics (variables, rows, date ranges), and output writes.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
        DuckDB database file queried read-only for the Warehouse panel. Shows
        row counts, distinct variables, and latest data date for each table.
        Displays "DB locked (rebuilding)" if the database is unavailable.

OUTPUT FILES:
    (none — this script serves a live HTML dashboard over HTTP)

VERSION: 1.0
LAST UPDATED: 2026-06-05
AUTHOR: Arjun Divecha

DEPENDENCIES:
    - duckdb (from the ASADO venv)
    - Python standard library (http.server, argparse, re, datetime, pathlib)

USAGE:
    python run_dashboard.py                         # newest log, port 8765
    python run_dashboard.py --port 8800
    python run_dashboard.py --log /path/to/run.log

NOTES:
    - Pure stdlib HTTP server + duckdb. Light mode only.
    - Re-parses the log and re-queries the DB on every page load (5s auto-refresh).
    - Run from the ASADO project root or any directory — paths are resolved
      relative to the script's location.
=============================================================================
"""
from __future__ import annotations

import argparse
import html
import re
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import duckdb

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "Data" / "logs"
DB_PATH = BASE_DIR / "Data" / "asado.duckdb"

# Key warehouse tables to surface (in display order). Others are added below.
KEY_TABLES = [
    "external_factors", "extended_factors", "imf_factors", "macrostructure_factors",
    "bloomberg_factors", "commodity_panel", "gdelt_panel", "t2_master",
    "t2_raw", "factor_returns", "factor_returns_daily", "t2_factors_daily",
    "gdelt_factors_daily", "unified_panel",
]

TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
STEP_RE = re.compile(r"STEP:\s*(.+?)\s*(?:\(([^)]+\.py)\))?\s*$")


def _newest_log() -> Path | None:
    logs = sorted(LOG_DIR.glob("monthly_update_*.log"), key=lambda p: p.stat().st_mtime)
    return logs[-1] if logs else None


def _parse_ts(line: str):
    m = TS_RE.search(line)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    return None


def parse_log(log_path: Path) -> dict:
    """Parse the run log into ordered stages + per-stage metrics."""
    text = log_path.read_text(errors="replace") if log_path.exists() else ""
    lines = text.splitlines()
    finished = ("Total elapsed:" in text) or ("FINAL SUMMARY" in text and "Total elapsed" in text)
    aborted = "ABORTING UPDATE" in text or "ABORTING" in text

    # Find STEP banners with their line index + timestamp.
    steps = []
    for i, ln in enumerate(lines):
        m = STEP_RE.search(ln)
        if m:
            steps.append({"name": m.group(1).strip(), "script": (m.group(2) or ""),
                          "line": i, "ts": _parse_ts(ln)})

    # For each step, scan its block (until next step) for processed metrics.
    for idx, st in enumerate(steps):
        start = st["line"]
        end = steps[idx + 1]["line"] if idx + 1 < len(steps) else len(lines)
        block = lines[start:end]
        metrics = {}
        for ln in block:
            for key, label in (("Variables", "vars"), ("Total rows", "rows"),
                               ("Date range", "dates")):
                m = re.search(rf"{key}\s*:\s*(.+)$", ln)
                if m and label not in metrics:
                    metrics[label] = m.group(1).strip()
            mw = re.search(r"Wrote .*?([\w .\-]+\.(?:csv|xlsx|parquet))\s*\(([^)]+)\)", ln)
            if mw and "wrote" not in metrics:
                metrics["wrote"] = f"{mw.group(1).strip()} ({mw.group(2).strip()})"
            mr = re.search(r"rows=([\d,]+)", ln)
            if mr and "rows" not in metrics:
                metrics["rows"] = mr.group(1)
        st["metrics"] = metrics
        # status
        last_ts = None
        for ln in reversed(block):
            last_ts = _parse_ts(ln)
            if last_ts:
                break
        st["last_ts"] = last_ts
        if idx < len(steps) - 1:
            st["status"] = "done"
        else:
            st["status"] = "failed" if aborted else ("done" if finished else "running")
        if st["ts"] and st["last_ts"]:
            st["elapsed"] = (st["last_ts"] - st["ts"]).total_seconds()
        else:
            st["elapsed"] = None

    # Overall
    started = _parse_ts(lines[0]) if lines else None
    last = None
    for ln in reversed(lines):
        last = _parse_ts(ln)
        if last:
            break
    total_elapsed = (last - started).total_seconds() if started and last else None
    return {
        "steps": steps, "finished": finished, "aborted": aborted,
        "started": started, "last": last, "total_elapsed": total_elapsed,
        "log_name": log_path.name if log_path else "—",
    }


def query_warehouse() -> tuple[list[dict], str | None]:
    """Per-table row count, distinct variables, latest date. Read-only; graceful."""
    if not DB_PATH.exists():
        return [], "DB not found"
    try:
        con = duckdb.connect(str(DB_PATH), read_only=True)
    except Exception as e:
        return [], f"DB locked (rebuilding): {str(e)[:60]}"
    try:
        present = set(con.execute("SHOW TABLES").fetchdf()["name"])
        ordered = [t for t in KEY_TABLES if t in present] + \
                  sorted(t for t in present if t not in KEY_TABLES)
        rows = []
        for t in ordered:
            try:
                cols = set(con.execute(f'DESCRIBE "{t}"').fetchdf()["column_name"])
                n = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                nv = (con.execute(f'SELECT COUNT(DISTINCT variable) FROM "{t}"').fetchone()[0]
                      if "variable" in cols else None)
                latest = (con.execute(f'SELECT MAX(date) FROM "{t}"').fetchone()[0]
                          if "date" in cols else None)
                status, note = _freshness(latest, "daily" in t)
                rows.append({"table": t, "rows": n, "vars": nv,
                             "latest": str(latest)[:10] if latest else "—",
                             "status": status, "note": note, "key": t in KEY_TABLES})
            except Exception:
                rows.append({"table": t, "rows": None, "vars": None, "latest": "—",
                             "status": "empty", "note": "", "key": t in KEY_TABLES})
        return rows, None
    finally:
        con.close()


def _month_index(d) -> int:
    return d.year * 12 + (d.month - 1)


def _freshness(latest, is_daily: bool) -> tuple[str, str]:
    """Classify a table's latest date. Returns (status, human note).

    status ∈ {ok, stale, very_stale, forecast, empty}. Forecast (future) dates
    are not 'stale' — they're WEO/projection rows. Monthly tables are judged
    against the last completed calendar month; daily tables against today.
    """
    if latest is None:
        return "empty", ""
    ld = latest.date() if isinstance(latest, datetime) else latest
    today = date.today()
    if ld > today:
        # A stamp up to ~1 month ahead is the month-end→first-of-next-month
        # convention (current data), not a real forecast. Far-future = forecast.
        months_ahead = _month_index(ld) - _month_index(today.replace(day=1))
        if not is_daily and months_ahead <= 1:
            return "ok", "current"
        return "forecast", "forecast"
    if is_daily:
        days = (today - ld).days
        if days <= 4:
            return "ok", "current"
        if days <= 10:
            return "stale", f"{days}d behind"
        return "very_stale", f"{days}d behind"
    # monthly: compare to last completed month
    last_completed = _month_index(today.replace(day=1)) - 1
    behind = last_completed - _month_index(ld)
    if behind <= 0:
        return "ok", "current"
    if behind == 1:
        return "stale", "1 mo behind"
    return "very_stale", f"{behind} mo behind"


def _fmt_secs(s):
    if s is None:
        return ""
    s = int(s)
    return f"{s//60}m {s%60}s" if s >= 60 else f"{s}s"


def render(log_path: Path) -> str:
    info = parse_log(log_path) if log_path else {"steps": [], "finished": False,
                                                 "aborted": False, "started": None,
                                                 "total_elapsed": None, "log_name": "—"}
    wh, wh_err = query_warehouse()

    if info["aborted"]:
        state, badge = "ABORTED", "fail"
    elif info["finished"]:
        state, badge = "COMPLETE", "done"
    else:
        state, badge = "RUNNING", "run"
    done = sum(1 for s in info["steps"] if s["status"] == "done")
    total = len(info["steps"])

    step_rows = []
    for s in info["steps"]:
        dot = {"done": "done", "running": "run", "failed": "fail"}[s["status"]]
        icon = {"done": "✓", "running": "⟳", "failed": "✕"}[s["status"]]
        m = s["metrics"]
        bits = []
        if m.get("vars"):
            bits.append(f'<span class="chip">{html.escape(m["vars"])} vars</span>')
        if m.get("rows"):
            bits.append(f'<span class="chip">{html.escape(m["rows"])} rows</span>')
        if m.get("dates"):
            bits.append(f'<span class="chip cal">{html.escape(m["dates"])}</span>')
        if m.get("wrote"):
            bits.append(f'<span class="chip wrote">{html.escape(m["wrote"])}</span>')
        meta = " ".join(bits) or '<span class="muted">—</span>'
        el = _fmt_secs(s["elapsed"]) if s["status"] != "running" else "running…"
        step_rows.append(f"""
        <div class="step {dot}">
          <div class="stephead"><span class="dot {dot}">{icon}</span>
            <span class="stepname">{html.escape(s['name'])}</span>
            <span class="elapsed">{el}</span></div>
          <div class="stepmeta">{meta}</div>
        </div>""")

    wh_rows = []
    for r in wh:
        cls = "keyrow" if r["key"] else ""
        rows_txt = f'{r["rows"]:,}' if isinstance(r["rows"], int) else "—"
        vars_txt = f'{r["vars"]:,}' if isinstance(r["vars"], int) else "—"
        st = r.get("status", "ok")
        note = f'<span class="fnote {st}">{html.escape(r.get("note") or "")}</span>' if r.get("note") else ""
        wh_rows.append(f"""<tr class="{cls}"><td class="tname">{html.escape(r['table'])}</td>
          <td class="num">{rows_txt}</td><td class="num">{vars_txt}</td>
          <td class="date date-{st}">{html.escape(r['latest'])} {note}</td></tr>""")
    wh_table = ("".join(wh_rows) if wh_rows
                else f'<tr><td colspan="4" class="muted">{html.escape(wh_err or "no data")}</td></tr>')

    # Stale-data warning (key tables that are behind).
    stale_key = [r for r in wh if r["key"] and r.get("status") in ("stale", "very_stale")]
    stale_warn = ""
    if stale_key:
        names = ", ".join(f'{r["table"]} ({r["note"]})' for r in stale_key)
        stale_warn = f'<div class="warn">⚠ Stale data: {html.escape(names)}</div>'

    now = datetime.now().strftime("%H:%M:%S")
    pct = int(100 * done / total) if total else 0
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="5">
<title>ASADO Monthly Update</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:#f6f7f9; color:#1c2230;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif; }}
  .wrap {{ max-width:1180px; margin:0 auto; padding:28px 24px 60px; }}
  header {{ display:flex; align-items:center; gap:16px; margin-bottom:8px; flex-wrap:wrap; }}
  h1 {{ font-size:20px; font-weight:650; margin:0; letter-spacing:-.2px; }}
  .sub {{ color:#6b7480; font-size:13px; }}
  .badge {{ font-size:12px; font-weight:700; padding:5px 12px; border-radius:999px; letter-spacing:.4px; }}
  .badge.done {{ background:#e3f6ea; color:#137a3c; }}
  .badge.run  {{ background:#fff3dc; color:#9a6300; }}
  .badge.fail {{ background:#fde6e6; color:#b3261e; }}
  .bar {{ height:8px; background:#e7eaef; border-radius:999px; overflow:hidden; margin:14px 0 22px; }}
  .bar > i {{ display:block; height:100%; width:{pct}%; background:linear-gradient(90deg,#4c8dff,#2bb673); transition:width .4s; }}
  .grid {{ display:grid; grid-template-columns:1.15fr .85fr; gap:22px; align-items:start; }}
  @media (max-width:880px){{ .grid {{ grid-template-columns:1fr; }} }}
  .card {{ background:#fff; border:1px solid #e7eaef; border-radius:14px; padding:6px 6px;
    box-shadow:0 1px 2px rgba(20,30,50,.04); }}
  .card h2 {{ font-size:12px; text-transform:uppercase; letter-spacing:.7px; color:#8a93a0;
    margin:14px 16px 10px; font-weight:700; }}
  .step {{ padding:10px 16px; border-top:1px solid #f0f2f5; }}
  .step:first-of-type {{ border-top:none; }}
  .stephead {{ display:flex; align-items:center; gap:10px; }}
  .stepname {{ font-size:14px; font-weight:550; flex:1; }}
  .elapsed {{ font-size:12px; color:#8a93a0; font-variant-numeric:tabular-nums; }}
  .dot {{ width:20px; height:20px; border-radius:50%; display:grid; place-items:center;
    font-size:11px; font-weight:800; color:#fff; flex:none; }}
  .dot.done {{ background:#2bb673; }} .dot.run {{ background:#f0a500; animation:spin 1.4s linear infinite; }}
  .dot.fail {{ background:#d8443c; }}
  @keyframes spin {{ to {{ transform:rotate(360deg); }} }}
  .step.run {{ background:#fffbf2; }}
  .stepmeta {{ margin:7px 0 0 30px; display:flex; gap:6px; flex-wrap:wrap; }}
  .chip {{ font-size:11.5px; background:#eef2f8; color:#3a4658; padding:3px 9px; border-radius:7px;
    font-variant-numeric:tabular-nums; }}
  .chip.cal {{ background:#eaf3ff; color:#2b5fa8; }}
  .chip.wrote {{ background:#e9f7ee; color:#1d7a44; }}
  .muted {{ color:#aab2bd; font-size:12px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ text-align:right; font-size:11px; text-transform:uppercase; letter-spacing:.5px; color:#9aa2ad;
    padding:8px 16px; font-weight:700; }}
  th:first-child {{ text-align:left; }}
  td {{ padding:8px 16px; font-size:13px; border-top:1px solid #f0f2f5; }}
  td.tname {{ font-weight:550; }} td.num,td.date {{ text-align:right; font-variant-numeric:tabular-nums; }}
  td.date {{ color:#2b5fa8; font-weight:600; }}
  td.date-ok {{ color:#137a3c; }}
  td.date-stale {{ color:#9a6300; }}
  td.date-very_stale {{ color:#b3261e; }}
  td.date-forecast {{ color:#6b7480; }}
  .fnote {{ font-size:10.5px; font-weight:700; padding:2px 6px; border-radius:6px; margin-left:6px; }}
  .fnote.ok {{ background:#e3f6ea; color:#137a3c; }}
  .fnote.stale {{ background:#fff3dc; color:#9a6300; }}
  .fnote.very_stale {{ background:#fde6e6; color:#b3261e; }}
  .fnote.forecast {{ background:#eef2f8; color:#6b7480; }}
  .warn {{ background:#fde6e6; color:#b3261e; border:1px solid #f6c7c4; border-radius:10px;
    padding:10px 16px; font-size:13px; font-weight:600; margin:0 0 18px; }}
  tr.keyrow td.tname {{ color:#1c2230; }}
  tr:not(.keyrow) td {{ color:#7a828d; }}
  footer {{ margin-top:18px; color:#aab2bd; font-size:12px; text-align:center; }}
</style></head><body><div class="wrap">
  <header>
    <h1>ASADO Monthly Update</h1>
    <span class="badge {badge}">{state}</span>
    <span class="sub">{done}/{total} stages · {_fmt_secs(info['total_elapsed'])} · {html.escape(info['log_name'])}</span>
  </header>
  <div class="bar"><i></i></div>
  {stale_warn}
  <div class="grid">
    <div class="card"><h2>Pipeline</h2>{''.join(step_rows) or '<div class="step"><span class="muted">waiting for first stage…</span></div>'}</div>
    <div class="card"><h2>Warehouse — latest data</h2>
      <table><thead><tr><th>Table</th><th>Rows</th><th>Vars</th><th>Latest</th></tr></thead>
      <tbody>{wh_table}</tbody></table></div>
  </div>
  <footer>auto-refreshes every 5s · rendered {now}</footer>
</div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    log_path: Path | None = None

    def do_GET(self):
        if self.path not in ("/", "/index.html"):
            self.send_response(404); self.end_headers(); return
        try:
            body = render(self.log_path or _newest_log()).encode("utf-8")
        except Exception as e:
            body = f"<pre>dashboard error: {html.escape(str(e))}</pre>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # quiet
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", type=Path, default=None, help="Run log (default: newest monthly_update_*.log)")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    Handler.log_path = args.log
    srv = HTTPServer(("127.0.0.1", args.port), Handler)
    print(f"ASADO dashboard → http://localhost:{args.port}  (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
