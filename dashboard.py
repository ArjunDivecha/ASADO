#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: dashboard.py
=============================================================================

INPUT FILES:
- Data/logs/run_*.log  (written by run.py — auto-discovers latest if no arg)

OUTPUT FILES:
- (none — read-only live monitor)

VERSION: 1.0
LAST UPDATED: 2026-04-29
AUTHOR: Arjun Divecha

DESCRIPTION:
Real-time terminal dashboard for an ASADO monthly update run.
Tails the run log produced by run.py and displays a live updating view of:
  - All pipeline steps with their status and elapsed time
  - Data metrics per collector (variables, countries, row counts)
  - DuckDB table sizes after each rebuild pass
  - Optimizer ingest results (factor counts, return rows)
  - Errors and tracebacks as they appear
  - Live output from the currently running step (last 15 lines)
  - Feature processing progress bar for long-running steps

Launched automatically by run.py in a new Terminal window. Can also be
run manually: python dashboard.py [path/to/run_*.log]

DEPENDENCIES:
- rich >= 13.0  (pip install rich)

USAGE:
  python dashboard.py                          # monitor latest log
  python dashboard.py Data/logs/run_XYZ.log   # monitor specific run
=============================================================================
"""

import re
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

try:
    from rich import box
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("dashboard.py requires 'rich':  pip install rich")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR  = BASE_DIR / "Data" / "logs"

# ── Regex patterns ────────────────────────────────────────────────────────────

RE_STEP      = re.compile(r'^STEP: (.+)$')
RE_INLINE    = re.compile(r'^INLINE: (.+)$')
RE_MANUAL    = re.compile(r'^MANUAL: (.+) → (.+)$')
RE_STATUS    = re.compile(r'^STATUS: (OK|FAILED|SKIPPED)(?: \(exit (-?\d+)\))?')
RE_ELAPSED   = re.compile(r'^ELAPSED: ([\d.]+)s')
RE_STARTED   = re.compile(r'^Started: (.+)$')

# Collector obs summary line: "→ source: N obs, M countries, K variable(s)"
RE_OBS       = re.compile(r'→ (\S+?):?\s+([\d,]+) obs,\s*(\d+) countries?,\s*(\d+) variable')
# Feature processing progress
RE_FEATURES  = re.compile(r'Processed (\d+)/(\d+) features')
RE_PROC_TOT  = re.compile(r'Processing (\d+) features')
# DuckDB verify table row: "  tablename          :   1,234 rows, 35 vars"
RE_DUCK_TBL  = re.compile(r'^\s{2,4}(\w[\w_]+)\s+:\s+([\d,]+) rows,\s+(\d+) (vars?|factors?)')
RE_DUCK_UNI  = re.compile(r'(unified_panel|feature_panel)\s+:\s+([\d,]+) rows,\s+(\d+) vars?')
# Optimizer ingest OK line
RE_OPT_OK    = re.compile(
    r'\[([\w_]+)\] OK — returns=([\d,]+) membership=([\d,]+) factors=(\d+) countries=(\d+)'
)
# Errors
RE_ERR_KW    = re.compile(
    r'(ModuleNotFoundError|ImportError|FileNotFoundError|PermissionError'
    r'|KeyError|AttributeError|RuntimeError|AssertionError): (.{1,80})'
)
RE_TRACEBACK = re.compile(r'^Traceback \(most recent call last\)')
# Log timestamp prefix to strip from display
RE_LOGTIMESTAMP = re.compile(
    r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - \w+ - '
)

# ── State ─────────────────────────────────────────────────────────────────────

class Step:
    def __init__(self, name: str, step_type: str = "script"):
        self.name      = name
        self.type      = step_type   # script | inline | manual
        self.status    = "running"
        self.elapsed   = None
        self.exit_code = None


class RunState:
    def __init__(self):
        self.steps:    list[Step] = []
        self.current:  Step | None = None

        self.start_time: datetime | None = None
        self.run_complete = False

        # Per-source metrics: source → {rows, countries, vars}
        self.collector_metrics: dict[str, dict] = {}

        # Feature-processing progress for current long-running step
        self.feature_progress: tuple | None = None  # (current, total)
        self.feature_total_announced: int | None = None

        # DuckDB sizes (updated each pass)
        self.duckdb_tables: dict[str, dict] = {}   # table → {rows, vars}
        self.unified_rows: str | None = None
        self.unified_vars: str | None = None

        # Optimizer ingest results
        self.optimizer_results: list[dict] = []

        # Errors: list of (step_name, message)
        self.errors: list[tuple] = []

        # Live output from current step (last N cleaned lines)
        self.last_lines: deque = deque(maxlen=15)

        self._in_output = False   # True after STEP: line until STATUS: line

    # ── Feed one log line ─────────────────────────────────────────────────────

    def feed(self, raw: str):
        line = raw.rstrip("\n")

        # Skip separator lines
        if line.startswith("=====") or line.startswith("-----"):
            return

        # Run start timestamp
        m = RE_STARTED.match(line)
        if m:
            try:
                self.start_time = datetime.fromisoformat(m.group(1))
            except Exception:
                pass
            return

        # New script/inline step
        m = RE_STEP.match(line) or RE_INLINE.match(line)
        if m:
            s = Step(m.group(1), "inline" if "INLINE" in line else "script")
            self.steps.append(s)
            self.current = s
            self._in_output = False
            self.feature_progress = None
            self.feature_total_announced = None
            return

        # Manual step result
        m = RE_MANUAL.match(line)
        if m:
            name, result = m.group(1), m.group(2)
            s = Step(name, "manual")
            s.status  = "OK" if result.upper().startswith("OK") else "SKIPPED"
            s.elapsed = 0.0
            self.steps.append(s)
            return

        # CMD / CWD metadata — skip
        if line.startswith("CMD: ") or line.startswith("CWD: "):
            return

        # STATUS line — marks end of output for this step
        m = RE_STATUS.match(line)
        if m and self.current:
            self.current.status = m.group(1)
            if m.group(2):
                self.current.exit_code = int(m.group(2))
            self._in_output = False
            return

        # ELAPSED line
        m = RE_ELAPSED.match(line)
        if m and self.current:
            self.current.elapsed = float(m.group(1))
            return

        # All other lines are step output — parse for metrics and add to last_lines
        self._in_output = True
        self._parse_metrics(line)
        clean = RE_LOGTIMESTAMP.sub("", line).rstrip()
        if clean:
            self.last_lines.append(clean)

    def _parse_metrics(self, line: str):
        # Collector summary
        m = RE_OBS.search(line)
        if m:
            src = m.group(1).lower().rstrip(":")
            self.collector_metrics[src] = {
                "rows":      m.group(2),
                "countries": int(m.group(3)),
                "vars":      int(m.group(4)),
            }
            return

        # Feature progress
        m = RE_FEATURES.search(line)
        if m:
            self.feature_progress = (int(m.group(1)), int(m.group(2)))
            return

        m = RE_PROC_TOT.search(line)
        if m:
            self.feature_total_announced = int(m.group(1))
            return

        # DuckDB table size
        m = RE_DUCK_TBL.match(line)
        if m:
            self.duckdb_tables[m.group(1)] = {"rows": m.group(2), "vars": m.group(3)}
            return

        m = RE_DUCK_UNI.search(line)
        if m:
            self.unified_rows = m.group(2)
            self.unified_vars = m.group(3)
            return

        # Optimizer ingest result
        m = RE_OPT_OK.search(line)
        if m:
            # Avoid duplicates
            src = m.group(1)
            if not any(r["source"] == src for r in self.optimizer_results):
                self.optimizer_results.append({
                    "source":     src,
                    "returns":    m.group(2),
                    "membership": m.group(3),
                    "factors":    m.group(4),
                    "countries":  m.group(5),
                })
            return

        # Errors
        m = RE_ERR_KW.search(line)
        if m:
            step_name = self.current.name if self.current else "?"
            err = f"{m.group(1)}: {m.group(2).strip()}"
            key = (step_name, m.group(1))
            if not any(e[0] == step_name and m.group(1) in e[1]
                       for e in self.errors):
                self.errors.append((step_name, err))
            return

        if RE_TRACEBACK.match(line):
            step_name = self.current.name if self.current else "?"
            if not any(e[0] == step_name and "Traceback" in e[1]
                       for e in self.errors):
                self.errors.append((step_name, "Traceback — see log for details"))


# ── Rich rendering ────────────────────────────────────────────────────────────

def _badge(status: str) -> tuple[str, str]:
    """Return (badge_text, colour) for a step status."""
    return {
        "OK":      ("[OK  ]", "bold green"),
        "FAILED":  ("[FAIL]", "bold red"),
        "SKIPPED": ("[SKIP]", "yellow"),
        "running": ("[>>>>]", "bold cyan"),
    }.get(status, ("[    ]", "dim white"))


def render_steps(state: RunState) -> Table:
    t = Table(box=box.SIMPLE_HEAD, expand=True, show_header=True,
              padding=(0, 1), header_style="bold")
    t.add_column("", width=7, no_wrap=True)
    t.add_column("Step", min_width=34, no_wrap=True)
    t.add_column("Time", width=7, justify="right")

    for step in state.steps:
        badge, colour = _badge(step.status)
        timing = (
            f"{step.elapsed:.0f}s" if step.elapsed is not None
            else ("…" if step.status == "running" else "—")
        )
        row_style = "red" if step.status == "FAILED" else ""
        t.add_row(
            Text(badge, style=colour),
            Text(step.name[:40]),
            Text(timing, justify="right"),
            style=row_style,
        )
    return t


def render_metrics(state: RunState) -> str:
    parts = []

    if state.collector_metrics:
        parts.append("[bold]Collectors[/bold]")
        parts.append("─" * 34)
        for src, m in state.collector_metrics.items():
            v = str(m.get("vars", "?"))
            c = f"{m.get('countries', '?')}/34"
            r = m.get("rows", "?")
            parts.append(
                f"[cyan]{src:<16}[/cyan]  {v:>3} vars  {c:>5}  {r} rows"
            )

    if state.duckdb_tables:
        parts.append("")
        parts.append("[bold]DuckDB tables[/bold]")
        parts.append("─" * 34)
        key_tables = [
            "external_factors", "extended_factors", "imf_factors",
            "bloomberg_factors", "gdelt_panel", "macrostructure_factors",
            "normalized_panel", "t2_master",
        ]
        shown = {k: v for k, v in state.duckdb_tables.items()
                 if k in key_tables}
        for tbl, info in shown.items():
            parts.append(
                f"[green]{tbl:<22}[/green]  {info['rows']:>10} rows  "
                f"{info['vars']:>3} vars"
            )
        if state.unified_rows:
            parts.append(
                f"[green]{'unified_panel':<22}[/green]  "
                f"{state.unified_rows:>10} rows  {state.unified_vars:>3} vars"
            )

    if state.optimizer_results:
        parts.append("")
        parts.append("[bold]Optimizer ingest[/bold]")
        parts.append("─" * 34)
        for r in state.optimizer_results:
            parts.append(
                f"[magenta]{r['source']:<20}[/magenta]  "
                f"{r['factors']:>3} factors  {r['returns']} ret-rows"
            )

    return "\n".join(parts) if parts else "[dim]Waiting for data…[/dim]"


def render_errors(state: RunState) -> str:
    if not state.errors:
        return "[dim green]None[/dim green]"
    lines = []
    seen: set = set()
    for step, msg in state.errors:
        key = (step[:30], msg[:40])
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"[bold red]{step[:28]}[/bold red]\n  [red]{msg[:65]}[/red]")
    return "\n\n".join(lines[-4:])   # show last 4 unique errors


def render_output(state: RunState) -> str:
    lines = []

    # Feature progress bar
    if state.feature_progress:
        cur, total_f = state.feature_progress
        filled = int(cur / total_f * 36) if total_f else 0
        bar = "█" * filled + "░" * (36 - filled)
        pct = 100 * cur // total_f if total_f else 0
        step_name = state.current.name[:38] if state.current else ""
        lines.append(f"[cyan]{step_name}[/cyan]")
        lines.append(f"  [{bar}]  {cur:,}/{total_f:,}  ({pct}%)")
        lines.append("")

    for raw in list(state.last_lines)[-12:]:
        lines.append(raw[:110])

    return "\n".join(lines) if lines else "[dim]Waiting for output…[/dim]"


def build_display(state: RunState, elapsed_total: float) -> Layout:
    done    = sum(1 for s in state.steps if s.status == "OK")
    failed  = sum(1 for s in state.steps if s.status == "FAILED")
    skipped = sum(1 for s in state.steps if s.status == "SKIPPED")
    running = sum(1 for s in state.steps if s.status == "running")
    total   = len(state.steps)

    now = datetime.now().strftime("%H:%M:%S")
    m, s = divmod(int(elapsed_total), 60)
    elapsed_str = f"{m}m {s:02d}s"

    cur_name = (state.current.name[:42] if state.current and
                state.current.status == "running" else "—")

    header_str = (
        f"[bold cyan]ASADO MONTHLY UPDATE[/bold cyan]   "
        f"{now}   elapsed [bold]{elapsed_str}[/bold]\n"
        f"[green]{done} OK[/green]  "
        f"[red]{failed} FAIL[/red]  "
        f"[yellow]{skipped} SKIP[/yellow]  "
        f"[cyan]{running} running[/cyan]  /  {total} steps total\n"
        f"[dim]Current: {cur_name}[/dim]"
    )

    layout = Layout()
    layout.split_column(
        Layout(Panel(header_str, border_style="bold blue", padding=(0, 1)),
               name="header", size=6),
        Layout(name="body", ratio=4),
        Layout(
            Panel(render_output(state),
                  title=f"Live output — {cur_name[:40]}",
                  border_style="cyan", padding=(0, 1)),
            name="footer", size=17,
        ),
    )
    layout["body"].split_row(
        Layout(
            Panel(render_steps(state), title="Pipeline",
                  border_style="blue", padding=(0, 0)),
            name="steps", ratio=3,
        ),
        Layout(name="right", ratio=2),
    )
    layout["right"].split_column(
        Layout(
            Panel(render_metrics(state), title="Data Metrics",
                  border_style="green", padding=(0, 1)),
            name="metrics", ratio=3,
        ),
        Layout(
            Panel(render_errors(state),
                  title=f"Errors ({len(state.errors)})" if state.errors else "Errors",
                  border_style="red" if state.errors else "dim",
                  padding=(0, 1)),
            name="errors", ratio=2,
        ),
    )
    return layout


# ── Log file tailer ───────────────────────────────────────────────────────────

def tail_and_parse(log_path: Path, state: RunState):
    """Read all content from log_path, yielding after each chunk."""
    pos = 0
    while True:
        if log_path.exists():
            with open(log_path, "r", errors="replace") as f:
                f.seek(pos)
                for line in f:
                    state.feed(line)
                pos = f.tell()
        yield


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Determine log file to monitor
    if len(sys.argv) > 1:
        log_file = Path(sys.argv[1])
        if not log_file.is_absolute():
            log_file = BASE_DIR / log_file
    else:
        # Auto-discover: wait up to 10s for a new run_*.log
        deadline = time.time() + 10
        log_file = None
        while time.time() < deadline:
            logs = sorted(LOG_DIR.glob("run_*.log"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
            if logs:
                log_file = logs[0]
                break
            time.sleep(0.5)
        if not log_file:
            print("No run log found in Data/logs/. Start a run first, or pass the log path.")
            sys.exit(1)

    print(f"Monitoring: {log_file.name}")
    time.sleep(0.3)

    console = Console()
    state   = RunState()
    tailer  = tail_and_parse(log_file, state)
    start_t = time.time()

    with Live(console=console, refresh_per_second=2, screen=True) as live:
        while True:
            next(tailer)
            elapsed = time.time() - start_t
            live.update(build_display(state, elapsed))
            time.sleep(0.5)

            # Detect run completion: last known step has a terminal status
            # and no step is still running
            any_running = any(s.status == "running" for s in state.steps)
            any_done    = len(state.steps) > 0
            if any_done and not any_running:
                # Drain any remaining log writes
                time.sleep(2)
                next(tailer)
                elapsed = time.time() - start_t
                live.update(build_display(state, elapsed))
                break

    # Hold the final display until the user closes the window (run by osascript)
    console.print(build_display(state, time.time() - start_t))
    done   = sum(1 for s in state.steps if s.status == "OK")
    failed = sum(1 for s in state.steps if s.status == "FAILED")
    if failed:
        console.print(f"\n[bold red]{failed} step(s) FAILED.[/bold red]")
    else:
        console.print(f"\n[bold green]All {done} steps completed successfully.[/bold green]")


if __name__ == "__main__":
    main()
