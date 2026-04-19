#!/usr/bin/env python3
"""
update_server.py — ASADO Monthly Update Backend Server
=======================================================
Runs alongside the Streamlit app and exposes:

  POST /run          — start a new monthly update run
  GET  /stream/{id}  — SSE stream of run events
  GET  /status/{id}  — current run status (JSON)
  GET  /history      — last 10 run summaries (JSON)
  POST /cancel/{id}  — cancel a running job (SIGTERM)

Usage:
  python update_server.py                  # default port 7821
  python update_server.py --port 7821

Then open Monthly Update.html — it will auto-connect to this server.

Dependencies (add to requirements.txt):
  fastapi
  uvicorn
  sse-starlette
"""

import argparse
import asyncio
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
PYTHON = sys.executable

app = FastAPI(title="ASADO Update Server", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory run store ────────────────────────────────────────────

runs: Dict[str, dict] = {}          # run_id → run state
event_queues: Dict[str, asyncio.Queue] = {}   # run_id → queue of SSE events


class RunOptions(BaseModel):
    skip_neo4j: bool = False
    skip_bloomberg: bool = False
    collectors_only: bool = False
    db_only: bool = False
    dry_run: bool = False


# ── Helpers ────────────────────────────────────────────────────────

def _make_event(kind: str, **payload) -> dict:
    return {"kind": kind, "ts": datetime.now().isoformat(), **payload}


def _stage_from_line(line: str) -> Optional[str]:
    """Detect which stage a log line belongs to by scanning for STEP: markers."""
    m = re.search(r"STEP:\s*(.+?)(?:\s*\(|$)", line)
    return m.group(1).strip() if m else None


SCRIPT_TO_STAGE = {
    "collect_external.py": "external",
    "collect_extended.py": "extended",
    "collect_imf.py":      "imf",
    "collect_bilateral.py":"bilateral",
    "collect_bloomberg.py":"bloomberg",
    "setup_duckdb.py":     "duckdb",
    "setup_neo4j.py":      "neo4j",
    "build_embeddings.py": "embeddings",
}

STATUS_PREFLIGHT = "preflight"
STATUS_VALIDATION = "validation"


PIPELINE_ORDER = [
    "preflight", "external", "extended", "imf",
    "bilateral", "bloomberg", "duckdb", "neo4j", "embeddings", "validation"
]

async def _stream_run(run_id: str, proc: subprocess.Popen, q: asyncio.Queue):
    """Read subprocess stdout/stderr line by line and push SSE events.
    
    FAIL IS FAIL: if any stage fails, all remaining stages are immediately
    marked as skipped and the run is terminated.
    """
    loop = asyncio.get_event_loop()
    current_stage = STATUS_PREFLIGHT
    stage_start = time.time()
    failed_stage = None           # set as soon as any stage fails
    completed_stages: set = set()

    def _readline():
        return proc.stdout.readline()

    await q.put(_make_event("stage_started", stage=current_stage))

    while True:
        line = await loop.run_in_executor(None, _readline)
        if not line:
            break
        line = line.rstrip("\n")
        if not line:
            continue

        # If a failure was already recorded, drain output silently
        if failed_stage:
            continue

        # Detect stage transitions from CMD/STEP markers
        for script, stage_id in SCRIPT_TO_STAGE.items():
            if script in line and ("CMD:" in line or "STEP:" in line):
                if stage_id != current_stage:
                    await q.put(_make_event("stage_started", stage=stage_id))
                    stage_start = time.time()
                    current_stage = stage_id
                break

        # Detect stage outcome lines written by monthly_update.py
        if "STATUS: OK" in line:
            dur = round(time.time() - stage_start, 1)
            completed_stages.add(current_stage)
            await q.put(_make_event("stage_completed",
                                    stage=current_stage, duration=dur))

        elif "STATUS: FAILED" in line:
            dur = round(time.time() - stage_start, 1)
            failed_stage = current_stage

            # Extract the error text that follows on the same line or next lines
            error_msg = line.replace("STATUS: FAILED", "").strip()
            if not error_msg:
                error_msg = f"Stage '{current_stage}' exited with non-zero status."

            await q.put(_make_event("stage_failed",
                                    stage=current_stage,
                                    duration=dur,
                                    error=error_msg))

            # Immediately skip all downstream stages
            idx = PIPELINE_ORDER.index(current_stage) if current_stage in PIPELINE_ORDER else -1
            for downstream in PIPELINE_ORDER[idx + 1:]:
                await q.put(_make_event("stage_skipped",
                                        stage=downstream,
                                        reason=f"Skipped — upstream stage '{current_stage}' failed"))

            # Kill the subprocess — no point continuing
            try:
                proc.terminate()
            except Exception:
                pass
            break  # stop reading output

        else:
            # Classify log level
            level = "info"
            low = line.lower()
            if any(w in low for w in ["warning", "warn"]):
                level = "warning"
            elif any(w in low for w in ["error", "failed", "exception", "traceback"]):
                level = "error"
            elif any(w in low for w in ["ok", "success", "complete", "written",
                                         "rebuilt", "created", "ready", "passed"]):
                level = "success"

            await q.put(_make_event("log", stage=current_stage, msg=line, level=level))

    # Process finished
    proc.wait()
    rc = proc.returncode if proc.returncode is not None else (1 if failed_stage else 0)
    runs[run_id]["returncode"] = rc
    runs[run_id]["finished_at"] = datetime.now().isoformat()
    runs[run_id]["status"] = "failed" if failed_stage else ("success" if rc == 0 else "failed")

    await q.put(_make_event("run_completed",
                            status=runs[run_id]["status"],
                            failed_stage=failed_stage,
                            returncode=rc))
    await q.put(None)  # sentinel → close stream


# ── Routes ─────────────────────────────────────────────────────────

@app.post("/run")
async def start_run(opts: RunOptions):
    """Start the monthly update pipeline."""
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]

    cmd = [PYTHON, str(SCRIPTS_DIR / "monthly_update.py")]
    if opts.skip_neo4j:      cmd.append("--skip-neo4j")
    if opts.skip_bloomberg:  cmd.append("--skip-bloomberg")
    if opts.collectors_only: cmd.append("--collectors-only")
    if opts.db_only:         cmd.append("--db-only")
    if opts.dry_run:         cmd.append("--dry-run")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(BASE_DIR),
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    q: asyncio.Queue = asyncio.Queue()
    event_queues[run_id] = q
    runs[run_id] = {
        "run_id": run_id,
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "finished_at": None,
        "returncode": None,
        "cmd": " ".join(cmd),
        "pid": proc.pid,
    }

    # Background task to read output
    asyncio.create_task(_stream_run(run_id, proc, q))

    return {"run_id": run_id, "pid": proc.pid}


@app.get("/stream/{run_id}")
async def stream_events(run_id: str):
    """SSE stream of events for a given run."""
    if run_id not in event_queues:
        raise HTTPException(status_code=404, detail="Run not found")

    q = event_queues[run_id]

    async def generator():
        # Send current run state immediately
        yield {"data": json.dumps(_make_event("run_started", run=runs.get(run_id, {})))}
        while True:
            event = await q.get()
            if event is None:
                # Run complete — clean up queue
                event_queues.pop(run_id, None)
                yield {"data": json.dumps(_make_event("stream_closed"))}
                break
            yield {"data": json.dumps(event)}

    return EventSourceResponse(generator())


@app.get("/status/{run_id}")
async def get_status(run_id: str):
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")
    return runs[run_id]


@app.get("/history")
async def get_history():
    """Return recent runs, newest first."""
    sorted_runs = sorted(runs.values(),
                         key=lambda r: r.get("started_at", ""), reverse=True)
    return sorted_runs[:10]


@app.post("/cancel/{run_id}")
async def cancel_run(run_id: str):
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")
    pid = runs[run_id].get("pid")
    if not pid:
        raise HTTPException(status_code=400, detail="No PID for this run")
    try:
        os.kill(pid, signal.SIGTERM)
        runs[run_id]["status"] = "canceled"
        return {"ok": True}
    except ProcessLookupError:
        raise HTTPException(status_code=400, detail="Process already finished")


@app.get("/health")
async def health():
    return {"ok": True, "time": datetime.now().isoformat()}


# ── Entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7821)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    print(f"ASADO Update Server starting on http://{args.host}:{args.port}")
    print(f"Base dir: {BASE_DIR}")
    print("Open Monthly Update.html — it will connect automatically.\n")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
