#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run.py
=============================================================================

DESCRIPTION:
    Interactive top-level launcher for the ASADO monthly update pipeline.
    Prompts for one manual prerequisite (Bloomberg pull), then runs every
    automated step in sequence with real-time streaming output and a running
    status board so you always know exactly where things stand.

    GDELT shallow and deep pipelines now run automatically — no manual prompt.
    Shallow: build_fullhistory_workbook.py (incremental stream + signals + monthly).
    Deep: backfill articles (last 60 days) → theme/GCAM/event features → join →
          monthly metronome → EWMA treatments → ASADO ingest.

    Same step order and flags as monthly_update.py, but with:
      - Live streaming output per step (no waiting for step to finish)
      - Step banner showing inputs/outputs/CWD before each step starts
      - One-line status summary after each step (status + elapsed + running count)
      - Full status board at the end of each stage and at completion

INPUT FILES:
    (none directly — orchestrates the full monthly update pipeline via subprocess calls)

OUTPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/logs/run_YYYY_MM_DD_HHMMSS.log
        Full session log file written by the runner for the entire pipeline run.
    - All step outputs produced by the monthly_update.py stages called as subprocesses.

VERSION: 1.0
LAST UPDATED: 2026-04-29
AUTHOR: Arjun Divecha

DEPENDENCIES:
    - All ASADO dependencies (requirements.txt)
    - Neo4j: brew services start neo4j  (or pass --skip-neo4j)
    - Bloomberg: Parallels + Terminal open  (or pass --skip-bloomberg)

USAGE:
    python run.py                      # full interactive run
    python run.py --skip-bloomberg     # skip Bloomberg Terminal steps
    python run.py --skip-neo4j         # skip Neo4j rebuild
    python run.py --skip-deep          # skip GDELT Deep
    python run.py --collectors-only    # data collection only
    python run.py --db-only            # database rebuilds only
    python run.py --dry-run            # dry-run mode for collectors
    python run.py --yes                # auto-confirm manual prerequisite prompts

NOTES:
    - All T2 Step Two / Three / Four scripts run with cwd set to their
      respective T2 directories so relative path references resolve correctly.
    - Log file is written to /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/logs/.
=============================================================================
"""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Validator module (lazy-loaded so missing deps don't block the import) ─────

def _load_validators():
    """Return the step_validators module, or None if it can't be imported."""
    qa_dir = Path(__file__).resolve().parent / "scripts" / "qa"
    if str(qa_dir) not in sys.path:
        sys.path.insert(0, str(qa_dir))
    try:
        import step_validators as _sv
        return _sv
    except Exception:
        return None

_SV = _load_validators()

# ── Paths ─────────────────────────────────────────────────────────────────────

BASE_DIR     = Path(__file__).resolve().parent
SCRIPTS_DIR  = BASE_DIR / "scripts"
LOG_DIR      = BASE_DIR / "Data" / "logs"
PYTHON       = sys.executable

T2_FUZZY_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy")
T2_GDELT_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 GDELT")
T2_ECON_DIR  = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Econ")
BBG_ENV      = "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv"
BBG_MASTER   = Path("/Users/arjundivecha/Dropbox/AAA Backup/Master Database") \
               / "Country Bloomberg Data Master T.xlsx"

GDELT_DIR      = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT")
GDELT_DEEP_DIR = GDELT_DIR / "Deep"

NEO4J_HOST      = "localhost"
NEO4J_BOLT_PORT = 7687

# ── Status constants ──────────────────────────────────────────────────────────

OK      = "OK"
FAILED  = "FAILED"
SKIPPED = "SKIPPED"
PENDING = "pending"
RUNNING = "running"

# ── Terminal colour helpers ───────────────────────────────────────────────────

def _c(text, code):
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text

def green(t):  return _c(t, "32")
def red(t):    return _c(t, "31")
def yellow(t): return _c(t, "33")
def cyan(t):   return _c(t, "36")
def bold(t):   return _c(t, "1")
def dim(t):    return _c(t, "2")


# ── Status formatting ─────────────────────────────────────────────────────────

def status_badge(s):
    if s == OK:      return green("[OK  ]")
    if s == FAILED:  return red("[FAIL]")
    if s == SKIPPED: return yellow("[SKIP]")
    if s == RUNNING: return cyan("[>>>> ]")
    return dim("[    ]")


def running_counts(steps):
    done = sum(1 for s in steps if s["status"] == OK)
    failed = sum(1 for s in steps if s["status"] == FAILED)
    skipped = sum(1 for s in steps if s["status"] == SKIPPED)
    total = len(steps)
    return done, failed, skipped, total


# ── Scoreboard ────────────────────────────────────────────────────────────────

def print_scoreboard(steps, elapsed_total, title="STATUS"):
    W = 72
    done, failed, skipped, total = running_counts(steps)
    now = datetime.now().strftime("%H:%M:%S")
    summary = f"  {now}  |  {done} OK  {failed} FAIL  {skipped} SKIP  |  {elapsed_total:.0f}s"

    print()
    print("╔" + "═" * (W - 2) + "╗")
    hdr = f"  {title}"
    print(f"║{bold(hdr):<{W - 2}}║")
    print(f"║{summary:<{W - 2}}║")
    print("╠" + "═" * (W - 2) + "╣")

    for s in steps:
        badge = status_badge(s["status"])
        name  = s["name"][:42]
        if s["status"] == OK:
            t = f"{s['elapsed']:.1f}s"
        elif s["status"] == RUNNING:
            t = "running…"
        elif s["status"] == SKIPPED:
            t = "—"
        else:
            t = f"{s['elapsed']:.1f}s" if s.get("elapsed") else ""

        note = f"  ← {s['note']}" if s.get("note") else ""
        line = f"  {badge}  {name:<42}  {t:<10}{note}"
        if s["status"] == FAILED:
            line = red(line)
        print(f"║{line:<{W - 2}}║")

    print("╚" + "═" * (W - 2) + "╝")
    print()


def print_plan(steps):
    W = 72
    total = len(steps)
    print()
    print("╔" + "═" * (W - 2) + "╗")
    hdr = "  ASADO MONTHLY UPDATE — PLAN"
    print(f"║{bold(hdr):<{W - 2}}║")
    print(f"║  {total} steps queued{'':<{W - 20}}║")
    print("╠" + "═" * (W - 2) + "╣")
    for i, s in enumerate(steps, 1):
        badge = status_badge(s["status"])  # PENDING or SKIPPED at plan time
        name  = s["name"][:50]
        note  = s.get("io_note", "")[:16]
        line  = f"  {badge}  {i:>2}.  {name:<50}  {dim(note)}"
        print(f"║{line:<{W - 2}}║")
    print("╚" + "═" * (W - 2) + "╝")
    print()


# ── Step execution ────────────────────────────────────────────────────────────

def _step_header(spec, step_num, total):
    W = 68
    tag = f"STEP {step_num}/{total}"
    print()
    print("┌" + "─" * (W - 2) + "┐")
    print(f"│  {bold(tag)}  {spec['name']:<{W - len(tag) - 6}}│")
    if spec.get("io_note"):
        print(f"│  {dim(spec['io_note']):<{W - 4}}│")
    if spec.get("type") not in ("manual", "inline"):
        scr = spec.get("script", "")
        cwd = spec.get("cwd") or BASE_DIR
        cmd_preview = str(scr)[:55]
        print(f"│  {dim('cmd: ' + cmd_preview):<{W - 4}}│")
        print(f"│  {dim('cwd: ' + str(cwd)[:55]):<{W - 4}}│")
    print("└" + "─" * (W - 2) + "┘")


def _step_footer(name, status, elapsed, step_num, total, steps):
    done, failed, skipped, _ = running_counts(steps)
    if status == OK:
        icon = green("✓")
        s_text = green(OK)
    elif status == SKIPPED:
        icon = yellow("○")
        s_text = yellow(SKIPPED)
    else:
        icon = red("✗")
        s_text = red(FAILED)
    count = f"({done} done, {failed} failed, {skipped} skipped / {total} total)"
    print(f"\n  {icon}  {bold(name[:45])}  {elapsed:.1f}s  {s_text}  {dim(count)}")
    print()


def stream_script_step(spec, log_file, step_num, total, steps):
    if spec.get("type") == "conda":
        cmd = ["conda", "run", "-p", BBG_ENV, "python", str(spec["script"])] \
              + spec.get("args", [])
    else:
        script_path = Path(spec["script"])
        if not script_path.is_absolute():
            script_path = SCRIPTS_DIR / script_path
        cmd = [PYTHON, str(script_path)] + spec.get("args", [])

    cwd = str(spec.get("cwd") or BASE_DIR)

    # Write step header to log immediately — dashboard reads this to know the step started
    with open(log_file, "a") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"STEP: {spec['name']}\n")
        f.write(f"CMD: {' '.join(str(c) for c in cmd)}\n")
        f.write(f"CWD: {cwd}\n")

    start = time.time()
    exit_code = -1
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        # Stream each line to terminal AND log immediately so dashboard sees it live
        with open(log_file, "a", buffering=1) as lf:
            for line in proc.stdout:
                print(f"  {line}", end="", flush=True)
                lf.write(line)
        proc.wait()
        elapsed   = time.time() - start
        status    = OK if proc.returncode == 0 else FAILED
        exit_code = proc.returncode
    except Exception as exc:
        elapsed = time.time() - start
        status  = FAILED
        err_line = f"Exception: {exc}\n"
        print(f"  {red('ERROR:')} {exc}")
        with open(log_file, "a") as f:
            f.write(err_line)

    # STATUS/ELAPSED written after step completes
    with open(log_file, "a") as f:
        f.write(f"STATUS: {status} (exit {exit_code})\n")
        f.write(f"ELAPSED: {elapsed:.1f}s\n")

    spec["status"]  = status
    spec["elapsed"] = elapsed
    return spec


def run_inline_step(spec, log_file, step_num, total, steps):
    with open(log_file, "a") as f:
        f.write(f"\n{'='*60}\nINLINE: {spec['name']}\n")

    start = time.time()
    try:
        spec["fn"]()
        elapsed = time.time() - start
        status  = OK
    except Exception as exc:
        elapsed = time.time() - start
        status  = FAILED
        spec["note"] = str(exc)
        print(f"  {red('ERROR:')} {exc}")
        with open(log_file, "a") as f:
            f.write(f"ERROR: {exc}\n")

    with open(log_file, "a") as f:
        f.write(f"STATUS: {status}\nELAPSED: {elapsed:.1f}s\n")

    spec["status"]  = status
    spec["elapsed"] = elapsed
    return spec


def run_manual_step(spec, log_file, yes):
    W = 68
    print()
    print("┌" + "─" * (W - 2) + "┐")
    hdr = f"  MANUAL PREREQUISITE: {spec['name']}"
    print(f"│{bold(hdr):<{W - 2}}│")
    print("├" + "─" * (W - 2) + "┤")
    for line in spec.get("description", "").splitlines():
        print(f"│  {line:<{W - 5}}│")

    # Show file info if a check path is provided
    check_path = spec.get("check")
    if check_path:
        print("│" + " " * (W - 2) + "│")
        if check_path.exists():
            mtime    = datetime.fromtimestamp(check_path.stat().st_mtime)
            size_kb  = check_path.stat().st_size // 1024
            age_days = (datetime.now() - mtime).days
            age_str  = f"{age_days}d ago" if age_days > 0 else "today"
            print(f"│  {dim('File  : ' + str(check_path.name)):<{W - 4}}│")
            print(f"│  {dim('Size  : ' + str(size_kb) + ' KB'):<{W - 4}}│")
            ts_line  = f"Modified: {mtime.strftime('%Y-%m-%d %H:%M')}  ({age_str})"
            if age_days == 0:
                ts_line = green("✓ " + ts_line)
            elif age_days <= 7:
                ts_line = yellow("⚠ " + ts_line)
            else:
                ts_line = red("✗ " + ts_line + "  — STALE, should be updated")
            print(f"│  {ts_line:<{W - 4}}│")
        else:
            print(f"│  {red('✗ File not found: ' + str(check_path)):<{W - 4}}│")
    print("└" + "─" * (W - 2) + "┘")

    if yes:
        print(f"  {yellow('--yes flag: auto-confirming')}")
        spec["status"]  = OK
        spec["elapsed"] = 0.0
        with open(log_file, "a") as f:
            f.write(f"\nMANUAL: {spec['name']} → auto-confirmed (--yes)\n")
        return spec

    while True:
        try:
            ans = input(f"\n  Done? [y / s=skip / q=quit]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n  Aborted.")
            sys.exit(0)
        if ans in ("y", "yes", ""):
            spec["status"] = OK
            break
        if ans in ("s", "skip"):
            spec["status"] = SKIPPED
            break
        if ans in ("q", "quit"):
            print("\n  Aborted.")
            sys.exit(0)

    spec["elapsed"] = 0.0
    with open(log_file, "a") as f:
        f.write(f"\nMANUAL: {spec['name']} → {spec['status']}\n")
    return spec


def dispatch_step(spec, log_file, step_num, total, steps, yes):
    """Route a step to its runner, print header/footer, update spec in-place."""
    if spec["status"] == SKIPPED:
        print(f"  {yellow('[SKIP]')} {spec['name']}")
        return spec

    _step_header(spec, step_num, total)
    spec["status"] = RUNNING

    t = spec.get("type", "script")
    if t == "manual":
        spec = run_manual_step(spec, log_file, yes)
    elif t == "inline":
        spec = run_inline_step(spec, log_file, step_num, total, steps)
    else:  # "script" or "conda"
        spec = stream_script_step(spec, log_file, step_num, total, steps)

    _step_footer(spec["name"], spec["status"], spec.get("elapsed", 0.0),
                 step_num, total, steps)
    return spec


# ── Dashboard launcher ───────────────────────────────────────────────────────

def _launch_dashboard(log_file: Path):
    """Open dashboard.py in a new Terminal window monitoring this run's log."""
    dashboard = BASE_DIR / "dashboard.py"
    if not dashboard.exists():
        return
    cmd_str = (
        f'cd \\"{BASE_DIR}\\" && '
        f'source venv/bin/activate && '
        f'python \\"{dashboard}\\" \\"{log_file}\\"; '
        f'echo \\"\\nDone. Press Enter to close.\\"; read'
    )
    try:
        subprocess.Popen(
            ["osascript", "-e",
             f'tell application "Terminal" to do script "{cmd_str}"'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print(f"  Dashboard launched in new Terminal window")
    except Exception as e:
        print(f"  (Could not auto-launch dashboard: {e} — run: python dashboard.py)")


# ── Neo4j helpers ─────────────────────────────────────────────────────────────

def neo4j_is_reachable():
    try:
        with socket.create_connection((NEO4J_HOST, NEO4J_BOLT_PORT), timeout=2):
            return True
    except (ConnectionRefusedError, OSError):
        return False


def ensure_neo4j():
    if neo4j_is_reachable():
        print("  Neo4j already running (bolt://localhost:7687)")
        return True
    print("  Neo4j not running — trying brew services start neo4j …")
    try:
        subprocess.run(["brew", "services", "start", "neo4j"],
                       capture_output=True, text=True, timeout=15)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    for i in range(15):
        time.sleep(2)
        if neo4j_is_reachable():
            print(f"  Neo4j ready ({(i + 1) * 2}s)")
            return True
    print("  Neo4j did not respond within 30s")
    return False


# ── Step list builder ─────────────────────────────────────────────────────────

def build_steps(args):
    """Return the ordered list of step specs based on CLI args."""
    collector_flags = ["--force"] + (["--dry-run"] if args.dry_run else [])
    skip_bbg  = args.skip_bloomberg
    skip_deep = args.skip_deep
    skip_neo4j = args.skip_neo4j
    db_only   = args.db_only
    coll_only = args.collectors_only

    def S(name, script, extra_args=None, cwd=None, skip=False, io_note=""):
        return {
            "name":     name,
            "type":     "script",
            "script":   script,
            "args":     extra_args or [],
            "cwd":      cwd,
            "status":   SKIPPED if skip else PENDING,
            "elapsed":  0.0,
            "io_note":  io_note,
        }

    def C(name, script, extra_args=None, skip=False, io_note=""):
        return {
            "name":    name,
            "type":    "conda",
            "script":  str(SCRIPTS_DIR / script),
            "args":    extra_args or [],
            "status":  SKIPPED if skip else PENDING,
            "elapsed": 0.0,
            "io_note": io_note,
        }

    def I(name, fn, io_note="", skip=False):
        return {
            "name":    name,
            "type":    "inline",
            "fn":      fn,
            "status":  SKIPPED if skip else PENDING,
            "elapsed": 0.0,
            "io_note": io_note,
        }

    def V(name, validator_fn, skip=False, io_note=""):
        """Inline validation step. Wraps validator_fn; skips gracefully if validator
        module didn't load."""
        if _SV is None or validator_fn is None:
            fn = lambda: print("  (validators not loaded — skipping check)")
        else:
            fn = validator_fn
        return I(f"  ✓ validate: {name}", fn, io_note=io_note, skip=skip)

    def M(name, description, check=None, io_note=""):
        d = {
            "name":        name,
            "type":        "manual",
            "description": description,
            "status":      PENDING,
            "elapsed":     0.0,
            "io_note":     io_note,
        }
        if check:
            d["check"] = check
        return d

    def skipped(name):
        return {"name": name, "type": "script", "script": "", "args": [],
                "status": SKIPPED, "elapsed": 0.0, "io_note": ""}

    steps = []

    # ── Manual prerequisites ──────────────────────────────────────────────────
    if not db_only:
        steps.append(M(
            "Update Bloomberg Data Master T.xlsx",
            "Open Bloomberg Terminal in Parallels and pull fresh data.\n"
            "Save the file before continuing.",
            check=BBG_MASTER,
            io_note="manual — Bloomberg Terminal",
        ))

    # ── Stage 1: Data collection ──────────────────────────────────────────────
    sv = _SV  # shorthand reference

    if not db_only:
        steps.append(S("Program 1: External Sources (7)",
                       "collect_external.py", collector_flags,
                       io_note="→ external_factors_panel.parquet"))
        steps.append(V("Program 1", sv.validate_external_collector if sv else None))

        steps.append(S("Program 2: Extended Sources (12)",
                       "collect_extended.py", collector_flags,
                       io_note="→ extended_factors_panel.parquet"))
        steps.append(V("Program 2", sv.validate_extended_collector if sv else None))

        steps.append(S("Program 3: IMF Datasets (7)",
                       "collect_imf.py", collector_flags,
                       io_note="→ imf_factors_panel.parquet"))
        steps.append(V("Program 3", sv.validate_imf_collector if sv else None))

        steps.append(S("Program 4: Bilateral Data",
                       "collect_bilateral.py", [],
                       io_note="→ trade / banking / portfolio matrices"))
        steps.append(V("Program 4", sv.validate_bilateral_collector if sv else None))

        steps.append(S("Program 5: Macrostructure Panel",
                       "collect_macrostructure.py", collector_flags,
                       io_note="→ macrostructure_panel.parquet"))
        steps.append(V("Program 5", sv.validate_macrostructure_collector if sv else None))

        if not skip_bbg:
            bbg_flags = ["--force"] + (["--dry-run"] if args.dry_run else [])
            steps.append(C("Program 6: Bloomberg",
                           "collect_bloomberg.py", bbg_flags,
                           io_note="→ bloomberg_factors_panel.parquet"))
            steps.append(V("Program 6", sv.validate_bloomberg_collector if sv else None))
        else:
            steps.append(skipped("Program 6: Bloomberg"))

        t2m_flags = (["--dry-run"] if args.dry_run else []) \
                    + (["--skip-p2p"] if skip_bbg else [])
        steps.append(S("Program 6b: T2 Master (P2P + Bloomberg)",
                       "build_t2_master.py", t2m_flags,
                       io_note="→ T2 Master.xlsx × 3 dirs"))
        steps.append(V("Program 6b", sv.validate_t2_master if sv else None))

        # ── GDELT Shallow pipeline (automated, incremental) ───────────────────
        # --save-panels is REQUIRED so country_signal_daily.parquet is refreshed;
        # the Deep join below depends on that file being current.
        steps.append(S(
            "GDELT Shallow  (stream + signals + monthly)",
            str(GDELT_DIR / "scripts" / "build_fullhistory_workbook.py"),
            ["--save-panels"], cwd=GDELT_DIR,
            io_note="→ country_signal_daily.parquet + monthly + GDELT workbook",
        ))
        steps.append(V("GDELT Shallow", sv.validate_gdelt_shallow if sv else None))

        # ── GDELT Deep pipeline (automated, incremental, skip with --skip-deep)
        steps.append(S(
            "GDELT Deep  Article backfill (incremental)",
            str(GDELT_DEEP_DIR / "scripts" / "backfill_article_daily.py"),
            ["--day-workers", "4"],
            cwd=GDELT_DIR, skip=skip_deep,
            io_note="→ article_themes_daily/, article_gcam_daily/ (auto from last date)",
        ))
        steps.append(V("GDELT Deep articles", sv.validate_gdelt_deep_articles if sv else None,
                       skip=skip_deep))

        steps.append(S(
            "GDELT Deep  Theme features (country-day)",
            str(GDELT_DEEP_DIR / "scripts" / "build_theme_features.py"),
            ["--article-themes-dir",
             str(GDELT_DEEP_DIR / "data" / "features" / "article_themes_daily"),
             "--output",
             str(GDELT_DEEP_DIR / "data" / "features" / "country_themes_daily.parquet")],
            cwd=GDELT_DIR, skip=skip_deep,
            io_note="→ country_themes_daily.parquet",
        ))
        steps.append(V("GDELT Deep themes", sv.validate_gdelt_deep_themes if sv else None,
                       skip=skip_deep))

        steps.append(S(
            "GDELT Deep  GCAM features (country-day)",
            str(GDELT_DEEP_DIR / "scripts" / "build_gcam_features.py"),
            ["--article-gcam-dir",
             str(GDELT_DEEP_DIR / "data" / "features" / "article_gcam_daily"),
             "--output",
             str(GDELT_DEEP_DIR / "data" / "features" / "country_gcam_daily.parquet")],
            cwd=GDELT_DIR, skip=skip_deep,
            io_note="→ country_gcam_daily.parquet",
        ))
        steps.append(V("GDELT Deep GCAM", sv.validate_gdelt_deep_gcam if sv else None,
                       skip=skip_deep))

        steps.append(S(
            "GDELT Deep  Event features (country-day)",
            str(GDELT_DEEP_DIR / "scripts" / "build_event_features.py"),
            ["--events-dir",
             str(GDELT_DEEP_DIR / "data" / "features" / "events_normalized"),
             "--output",
             str(GDELT_DEEP_DIR / "data" / "features" / "country_events_daily.parquet")],
            cwd=GDELT_DIR, skip=skip_deep,
            io_note="→ country_events_daily.parquet",
        ))
        steps.append(V("GDELT Deep events", sv.validate_gdelt_deep_events if sv else None,
                       skip=skip_deep))

        steps.append(S(
            "GDELT Deep  Join features → daily panel",
            str(GDELT_DEEP_DIR / "scripts" / "join_to_daily_panel.py"),
            ["--daily-panel",
             str(GDELT_DIR / "data" / "panels" / "country_signal_daily.parquet"),
             "--themes",
             str(GDELT_DEEP_DIR / "data" / "features" / "country_themes_daily.parquet"),
             "--gcam",
             str(GDELT_DEEP_DIR / "data" / "features" / "country_gcam_daily.parquet"),
             "--events",
             str(GDELT_DEEP_DIR / "data" / "features" / "country_events_daily.parquet"),
             "--output",
             str(GDELT_DIR / "data" / "panels" / "country_signal_daily_deep.parquet")],
            cwd=GDELT_DIR, skip=skip_deep,
            io_note="→ country_signal_daily_deep.parquet",
        ))
        steps.append(V("GDELT Deep join", sv.validate_gdelt_deep_join if sv else None,
                       skip=skip_deep))

        steps.append(S(
            "GDELT Deep  Monthly metronome (deep panel)",
            str(GDELT_DIR / "scripts" / "build_monthly_metronome.py"),
            ["--daily-panel-parquet",
             str(GDELT_DIR / "data" / "panels" / "country_signal_daily_deep.parquet"),
             "--output-parquet",
             str(GDELT_DEEP_DIR / "data" / "features" / "country_signal_monthly_deep.parquet")],
            cwd=GDELT_DIR, skip=skip_deep,
            io_note="→ country_signal_monthly_deep.parquet",
        ))
        steps.append(V("GDELT Deep monthly", sv.validate_gdelt_deep_monthly if sv else None,
                       skip=skip_deep))

        steps.append(S(
            "GDELT Deep  Monthly treatments (EWMA + z-scores)",
            str(GDELT_DEEP_DIR / "scripts" / "build_monthly_deep_treatments.py"),
            ["--monthly-panel",
             str(GDELT_DEEP_DIR / "data" / "features" / "country_signal_monthly_deep.parquet"),
             "--output",
             str(GDELT_DEEP_DIR / "data" / "features" / "country_signal_monthly_deep_treated.parquet")],
            cwd=GDELT_DIR, skip=skip_deep,
            io_note="→ country_signal_monthly_deep_treated.parquet",
        ))
        steps.append(V("GDELT Deep treatments", sv.validate_gdelt_deep_treatments if sv else None,
                       skip=skip_deep))

        # ── Ingest GDELT Deep treated panel into ASADO tidy warehouse ─────────
        steps.append(S("Program 7: GDELT Deep  (ASADO ingest)",
                       "collect_gdelt_deep.py",
                       ["--dry-run"] if args.dry_run else [],
                       skip=skip_deep,
                       io_note="→ gdelt_deep_panel.parquet"))
        steps.append(V("Program 7", sv.validate_gdelt_deep_ingest if sv else None,
                       skip=skip_deep))

    # ── Stage 2A: DuckDB pass 1 ───────────────────────────────────────────────
    if not coll_only:
        steps.append(S("DuckDB Rebuild  (pass 1)",
                       "setup_duckdb.py", [],
                       io_note="→ asado.duckdb (from parquet + prior CSVs)"))
        steps.append(V("DuckDB pass 1", sv.validate_duckdb_pass1 if sv else None))
        steps.append(S("Normalization Layer  (pass 1)",
                       "build_normalized_panel.py", [],
                       io_note="→ normalized_panel / feature_panel views"))
        steps.append(V("Normalization pass 1", sv.validate_normalization_pass1 if sv else None))

        # ── Stage 2B: Workbook exports ────────────────────────────────────────
        steps.append(S("Econ Workbook Export  (Econ.xlsx)",
                       "build_econ_panel.py", [],
                       io_note="→ T2 Econ/Econ.xlsx (146 vars, 34 countries)"))
        steps.append(V("Econ workbook", sv.validate_econ_workbook if sv else None))

        steps.append(S("GDELT Workbook Export  (GDELT.xlsx)",
                       "build_gdelt_panel.py", [],
                       skip=skip_deep,
                       io_note="→ T2 GDELT/GDELT.xlsx (685 sheets)"))
        steps.append(V("GDELT workbook", sv.validate_gdelt_workbook if sv else None,
                       skip=skip_deep))

        # ── Stage 2C: T2 Step Twos ────────────────────────────────────────────
        steps.append(S("T2 Fuzzy  Step Two  (Normalized CSV)",
                       str(T2_FUZZY_DIR / "Step Two Create Normalized Tidy.py"),
                       [], cwd=T2_FUZZY_DIR,
                       io_note="→ Normalized_T2_MasterCSV.csv"))
        steps.append(V("T2 Fuzzy Step Two", sv.validate_t2_step_two_fuzzy if sv else None))

        def _copy_normalized():
            src = T2_FUZZY_DIR / "Normalized_T2_MasterCSV.csv"
            if not src.exists():
                raise FileNotFoundError(f"Not found: {src}")
            for dst_dir in (T2_GDELT_DIR, T2_ECON_DIR):
                shutil.copy2(src, dst_dir / "Normalized_T2_MasterCSV.csv")
                print(f"    Copied → {dst_dir.name}/Normalized_T2_MasterCSV.csv")

        steps.append(I("Distribute Normalized_T2_MasterCSV.csv",
                       _copy_normalized,
                       io_note="T2 Fuzzy → T2 GDELT + T2 Econ"))

        steps.append(S("T2 GDELT  Step Two  (GDELT_Factors MasterCSV)",
                       str(T2_GDELT_DIR / "Step Two GDELT Create Tidy.py"),
                       [], cwd=T2_GDELT_DIR, skip=skip_deep,
                       io_note="→ GDELT_Factors_MasterCSV.csv"))
        steps.append(V("T2 GDELT Step Two", sv.validate_t2_step_two_gdelt if sv else None,
                       skip=skip_deep))

        steps.append(S("T2 Econ   Step Two  (Econ_Factors MasterCSV)",
                       str(T2_ECON_DIR / "Step Two Econ Create Tidy.py"),
                       [], cwd=T2_ECON_DIR,
                       io_note="→ Econ_Factors_MasterCSV.csv"))
        steps.append(V("T2 Econ Step Two", sv.validate_t2_step_two_econ if sv else None))

        # ── Stage 2C: T2 Step Threes + Fours ─────────────────────────────────
        steps.append(S("T2 Fuzzy  Step Three  (Top-20 Exposure)",
                       str(T2_FUZZY_DIR / "Step Three Top20 Portfolios Fast.py"),
                       [], cwd=T2_FUZZY_DIR,
                       io_note="→ T2_Top_20_Exposure.csv"))
        steps.append(S("T2 Fuzzy  Step Four   (T2_Optimizer.xlsx)",
                       str(T2_FUZZY_DIR / "Step Four Create Monthly Top20 Returns FAST.py"),
                       [], cwd=T2_FUZZY_DIR,
                       io_note="→ T2_Optimizer.xlsx"))
        steps.append(V("T2 Fuzzy Steps 3+4", sv.validate_t2_steps_34_fuzzy if sv else None))

        steps.append(S("T2 GDELT  Step Three  (GDELT Top-20 Exposure)",
                       str(T2_GDELT_DIR / "Step Three GDELT Top20 Portfolios Fast.py"),
                       [], cwd=T2_GDELT_DIR, skip=skip_deep,
                       io_note="→ GDELT_Top_20_Exposure.csv"))
        steps.append(S("T2 GDELT  Step Four   (GDELT_Optimizer.xlsx)",
                       str(T2_GDELT_DIR / "Step Four GDELT Create Monthly Top20 Returns FAST.py"),
                       [], cwd=T2_GDELT_DIR, skip=skip_deep,
                       io_note="→ GDELT_Optimizer.xlsx"))
        steps.append(V("T2 GDELT Steps 3+4", sv.validate_t2_steps_34_gdelt if sv else None,
                       skip=skip_deep))

        steps.append(S("T2 Econ   Step Three  (Econ Top-20 Exposure)",
                       str(T2_ECON_DIR / "Step Three Econ Top20 Portfolios Fast.py"),
                       [], cwd=T2_ECON_DIR,
                       io_note="→ Econ_Top_20_Exposure.csv"))
        steps.append(S("T2 Econ   Step Four   (Econ_Optimizer.xlsx)",
                       str(T2_ECON_DIR / "Step Four Econ Create Monthly Top20 Returns FAST.py"),
                       [], cwd=T2_ECON_DIR,
                       io_note="→ Econ_Optimizer.xlsx"))
        steps.append(V("T2 Econ Steps 3+4", sv.validate_t2_steps_34_econ if sv else None))

        steps.append(S("Optimizer Returns + Top-20 Ingest",
                       "collect_optimizer_returns.py", collector_flags,
                       io_note="→ factor_returns / factor_top20_membership"))
        steps.append(V("Optimizer ingest", sv.validate_optimizer_ingest if sv else None))

        # ── Stage 2D: DuckDB pass 2 ───────────────────────────────────────────
        steps.append(S("DuckDB Rebuild  (pass 2 — fresh CSVs)",
                       "setup_duckdb.py", [],
                       io_note="→ asado.duckdb (with new T2/GDELT CSVs)"))
        steps.append(V("DuckDB pass 2", sv.validate_duckdb_pass2 if sv else None))

        steps.append(S("Normalization Layer  (pass 2)",
                       "build_normalized_panel.py", [],
                       io_note="→ normalized_panel / feature_panel (final)"))

        # ── Stage 2E: GDELT Deep DB ───────────────────────────────────────────
        steps.append(S("GDELT Deep → DuckDB  (gdelt_deep_factors)",
                       "load_gdelt_deep_to_duckdb.py", [], skip=skip_deep,
                       io_note="→ gdelt_deep_factors table"))
        steps.append(S("GDELT Deep _CS variants",
                       "build_gdelt_deep_cs.py", [], skip=skip_deep,
                       io_note="→ gdelt_deep_factors_cs table"))
        steps.append(V("GDELT Deep DuckDB", sv.validate_gdelt_deep_duckdb if sv else None,
                       skip=skip_deep))
        steps.append(S("GDELT Deep PIT audit",
                       "qa/pit_audit_gdelt_deep.py", [], skip=skip_deep,
                       io_note="→ pit_audit_gdelt_deep.csv"))

        # ── Stage 3: Neo4j + schema ───────────────────────────────────────────
        if not skip_neo4j:
            steps.append(S("Neo4j Knowledge Graph",
                           "setup_neo4j.py", [],
                           io_note="→ graph nodes + bilateral edges"))
            steps.append(V("Neo4j", sv.validate_neo4j if sv else None))
            steps.append(S("Country-State Embeddings",
                           "build_embeddings.py", [],
                           io_note="→ 34-d cosine state vectors"))
            steps.append(S("Schema Cache Refresh",
                           "build_schema_registry.py", [],
                           io_note="→ Data/cache/query_assistant/"))
        else:
            for n in ("Neo4j Knowledge Graph", "Country-State Embeddings"):
                steps.append(skipped(n))
            steps.append(S("Schema Cache Refresh  (DuckDB only)",
                           "build_schema_registry.py", ["--duck-only"],
                           io_note="→ Data/cache/query_assistant/"))

        steps.append(V("Schema registry", sv.validate_schema_registry if sv else None))

        steps.append(S("Factor Reference  (docs/factor_reference.md)",
                       "build_factor_reference.py", [],
                       io_note="→ docs/factor_reference.md"))
        steps.append(V("Factor reference", sv.validate_factor_reference if sv else None))

    return steps


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ASADO Monthly Update — interactive launcher with live step feedback"
    )
    parser.add_argument("--skip-neo4j",    action="store_true")
    parser.add_argument("--skip-bloomberg",action="store_true")
    parser.add_argument("--skip-deep",     action="store_true")
    parser.add_argument("--collectors-only", action="store_true")
    parser.add_argument("--db-only",       action="store_true")
    parser.add_argument("--dry-run",       action="store_true")
    parser.add_argument("--yes",           action="store_true",
                        help="Auto-confirm manual prerequisite prompts")
    args = parser.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts       = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    log_file = LOG_DIR / f"run_{ts}.log"

    steps = build_steps(args)
    total = len(steps)

    # ── Opening banner ────────────────────────────────────────────────────────
    print()
    print(bold("=" * 68))
    print(bold("  ASADO MONTHLY UPDATE"))
    print(f"  Started : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Log     : {log_file}")
    print(f"  Steps   : {total}  ({sum(1 for s in steps if s['status'] == SKIPPED)} pre-skipped)")
    print(bold("=" * 68))

    with open(log_file, "w") as f:
        f.write(f"ASADO Monthly Update\nStarted: {datetime.now().isoformat()}\nArgs: {vars(args)}\n\n")

    _launch_dashboard(log_file)
    print_plan(steps)

    if not args.yes:
        try:
            input("  Press ENTER to start (Ctrl-C to abort) … ")
        except (KeyboardInterrupt, EOFError):
            print("\n  Aborted.")
            sys.exit(0)

    total_start = time.time()
    neo4j_skipped_at_runtime = False

    for i, spec in enumerate(steps):
        step_num = i + 1

        # Special pre-flight for Neo4j step: check connectivity and handle failure
        if spec.get("name", "").startswith("Neo4j Knowledge Graph") \
                and spec["status"] != SKIPPED:
            print(f"\n  Checking Neo4j availability …")
            if not ensure_neo4j():
                print(f"  {red('Neo4j unreachable')} — skipping graph stages")
                neo4j_skipped_at_runtime = True
                spec["status"] = SKIPPED
                spec["note"]   = "unreachable at runtime"
                # Also pre-skip Embeddings (next step); Schema will use --duck-only
                if i + 1 < total and steps[i + 1]["name"].startswith("Country-State"):
                    steps[i + 1]["status"] = SKIPPED
                    steps[i + 1]["note"]   = "Neo4j unreachable"
                # Patch Schema Refresh to duck-only mode
                for j in range(i, total):
                    if "Schema Cache Refresh" in steps[j].get("name", ""):
                        steps[j]["args"] = ["--duck-only"]
                        steps[j]["name"] += "  (DuckDB-only fallback)"
                        steps[j]["io_note"] = "Neo4j unavailable — DuckDB only"
                        break

        spec = dispatch_step(spec, log_file, step_num, total, steps, args.yes)
        steps[i] = spec

        # Print a stage-level scoreboard at key milestones
        stage_boundaries = {
            "Program 7: GDELT Deep  (ASADO ingest)": "STAGE 1 — COLLECTION COMPLETE",
            "Normalization Layer  (pass 1)":         "STAGE 2A — DUCKDB PASS 1 COMPLETE",
            "T2 Econ   Step Two  (Econ_Factors MasterCSV)":
                                                     "STAGE 2C — T2 STEP TWOS COMPLETE",
            "Optimizer Returns + Top-20 Ingest":     "STAGE 2C — T2 STEPS 3+4 COMPLETE",
            "Normalization Layer  (pass 2)":         "STAGE 2D — DUCKDB PASS 2 COMPLETE",
            "GDELT Deep PIT audit":                  "STAGE 2E — GDELT DEEP DB COMPLETE",
        }
        if spec["name"] in stage_boundaries:
            elapsed_so_far = time.time() - total_start
            print_scoreboard(steps, elapsed_so_far,
                             title=stage_boundaries[spec["name"]])

    total_elapsed = time.time() - total_start

    # ── Final scoreboard ──────────────────────────────────────────────────────
    print_scoreboard(steps, total_elapsed, title="FINAL SUMMARY")

    done, failed, skipped, _ = running_counts(steps)
    print(bold("=" * 68))
    if failed == 0:
        print(f"  {green('ALL STEPS COMPLETED SUCCESSFULLY')}  "
              f"({done} OK, {skipped} skipped)  {total_elapsed / 60:.1f} min")
    else:
        failed_names = [s["name"] for s in steps if s["status"] == FAILED]
        print(f"  {red(f'{failed} STEP(S) FAILED:')} {', '.join(failed_names)}")
        print(f"  {done} OK, {skipped} skipped  ·  {total_elapsed / 60:.1f} min total")
    print(f"  Log: {log_file}")
    print(bold("=" * 68))
    print()

    with open(log_file, "a") as f:
        f.write(f"\n{'='*60}\nFINAL SUMMARY\n")
        for s in steps:
            f.write(f"  [{s['status']:<7}]  {s['name']}  {s.get('elapsed', 0):.1f}s\n")
        f.write(f"Total: {total_elapsed:.1f}s\n")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
