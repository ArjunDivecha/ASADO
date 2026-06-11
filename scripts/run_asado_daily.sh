#!/bin/bash
# =============================================================================
# SCRIPT NAME: run_asado_daily.sh
# =============================================================================
#
# DESCRIPTION:
# Unattended morning runner for the ASADO daily pipeline. Called by launchd
# (com.arjundivecha.asado-daily) weekdays at 07:30. Replaces the manual
# morning `python scripts/daily_update.py` ritual that failed ~20% of the
# time because Bloomberg Terminal wasn't up in the Parallels VM.
#
# Flow:
#   1. BLOOMBERG PREFLIGHT: ensure the "Windows 11" Parallels VM is running
#      (auto-start it if not), then run a real bloomberg_setup() data-path
#      test in the OpusBloomberg conda env (starts bbcomm + port forwarding
#      itself). If Bloomberg isn't ready, send ONE iMessage telling Arjun to
#      open/log into Bloomberg Terminal, then keep retrying every 20 minutes
#      until the 11:00 deadline. The moment Bloomberg comes up, the pipeline
#      proceeds automatically — no rerun needed.
#   2. RUN daily_update.py --resume (resume = stages already completed today
#      are skipped, so retries never redo finished work).
#   3. If the pipeline fails, retry once with --resume after 10 minutes
#      (transient failures recover; completed stages are skipped). If it
#      still fails, send an iMessage with the failing stage + log path.
#
# FAIL IS FAIL: every failure path ends in a loud iMessage + non-zero exit;
# nothing is silently skipped or substituted.
#
# INPUT FILES:
# - /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/scripts/daily_update.py
#     The pipeline this script supervises.
# - /Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv
#     Conda env with blpapi + bbg.py used for the Bloomberg preflight.
#
# OUTPUT FILES:
# - /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/logs/asado_daily_runner.log
#     This wrapper's own decision log (append-only).
# - Everything daily_update.py writes (run logs, progress checkpoint, data).
# - iMessage alerts to +15104212111 on Bloomberg-not-ready and pipeline failure.
#
# VERSION: 1.0  |  LAST UPDATED: 2026-06-10  |  AUTHOR: Claude Code for Arjun
#
# USAGE: invoked by launchd weekdays 07:30; safe to run manually any time
#        (resume semantics make double-runs harmless).
# =============================================================================

set -uo pipefail

ASADO="/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
BBG_ENV="/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv"
PY="$ASADO/venv/bin/python"
RUNNER_LOG="$ASADO/Data/logs/asado_daily_runner.log"
RECIPIENT="+15104212111"
DEADLINE_HOUR=11           # stop waiting for Bloomberg at 11:00
RETRY_WAIT=1200            # 20 min between Bloomberg retries
PIPELINE_RETRY_WAIT=1500   # 25 min before the one pipeline retry — must exceed
                           # GDELT's 15-min per-IP cooldown (which RESETS on
                           # every request, so a 10-min retry was guaranteed to
                           # re-fail the evidence-packs step; seen 2026-06-11)

export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

mkdir -p "$ASADO/Data/logs"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$RUNNER_LOG"; }

send_imessage() {
    local text="$1"
    local safe_text="${text//\\/\\\\}"
    safe_text="${safe_text//\"/\\\"}"
    osascript -e "tell application \"Messages\"
  set targetService to first service whose service type = iMessage
  set targetBuddy to buddy \"$RECIPIENT\" of targetService
  send \"$safe_text\" to targetBuddy
end tell" >/dev/null 2>&1 &
}

log "=== ASADO daily runner starting ==="

# Don't double-run if a daily_update is already in flight (e.g. manual run).
if pgrep -f "daily_update.py" >/dev/null 2>&1; then
    log "daily_update.py already running — exiting (no double-run)."
    exit 0
fi

# ---------------------------------------------------------------------------
# 1. Bloomberg preflight loop (until ready or DEADLINE_HOUR)
# ---------------------------------------------------------------------------
ALERTED=0
BLOOMBERG_READY=0
while true; do
    # Ensure the Parallels VM is up (auto-heal: start it if stopped).
    if ! prlctl list 2>/dev/null | grep -q "running.*Windows 11"; then
        log "Parallels 'Windows 11' VM not running — starting it..."
        prlctl start "Windows 11" >>"$RUNNER_LOG" 2>&1
        sleep 90
    fi

    # Real data-path test: bloomberg_setup() starts bbcomm + port forwarding
    # and runs a live pull test. This is the same gate collect_t2_bloomberg
    # uses, so passing here means the pipeline's stage 1 will not die.
    if conda run -p "$BBG_ENV" python -c "
import sys
sys.path.insert(0, '/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg')
from bbg import bloomberg_setup
bloomberg_setup()
" >>"$RUNNER_LOG" 2>&1; then
        log "Bloomberg preflight: READY."
        BLOOMBERG_READY=1
        break
    fi

    NOW_H=$(date +%H)
    if [ "$NOW_H" -ge "$DEADLINE_HOUR" ]; then
        log "Bloomberg still not ready at deadline (${DEADLINE_HOUR}:00)."
        break
    fi

    if [ "$ALERTED" -eq 0 ]; then
        send_imessage "🌅 ASADO: Bloomberg not ready (Terminal not running/logged in on Parallels?). I'll retry every 20 min until ${DEADLINE_HOUR}:00 and run automatically once it's up."
        ALERTED=1
        log "Bloomberg preflight failed — alerted Arjun, retrying every $((RETRY_WAIT / 60)) min."
    else
        log "Bloomberg preflight failed — retrying in $((RETRY_WAIT / 60)) min."
    fi
    sleep "$RETRY_WAIT"
done

EXTRA_FLAGS=()
if [ "$BLOOMBERG_READY" -ne 1 ]; then
    # FAIL IS FAIL: we do NOT silently run --skip-bloomberg (that would build
    # today's factors from stale prices). We alert and stop; rerun manually or
    # rely on tomorrow's run.
    send_imessage "❌ ASADO daily DID NOT RUN: Bloomberg never came up by ${DEADLINE_HOUR}:00. Start Bloomberg Terminal and run: python scripts/daily_update.py --resume"
    log "Aborting: Bloomberg unavailable through deadline. Pipeline NOT run."
    exit 1
fi

# ---------------------------------------------------------------------------
# 2. Run the pipeline (resume-aware), with one retry
# ---------------------------------------------------------------------------
cd "$ASADO"
log "Starting daily_update.py --resume (attempt 1)..."
"$PY" scripts/daily_update.py --resume >>"$RUNNER_LOG" 2>&1
RC=$?

if [ "$RC" -ne 0 ]; then
    log "daily_update failed (exit $RC). Retrying with --resume in $((PIPELINE_RETRY_WAIT / 60)) min..."
    sleep "$PIPELINE_RETRY_WAIT"
    log "Starting daily_update.py --resume (attempt 2)..."
    "$PY" scripts/daily_update.py --resume >>"$RUNNER_LOG" 2>&1
    RC=$?
fi

if [ "$RC" -ne 0 ]; then
    LATEST_LOG=$(ls -t "$ASADO/Data/logs"/daily_update_2*.log 2>/dev/null | head -1)
    FAILED_STAGE=$(grep -h "ABORTED at" "$LATEST_LOG" 2>/dev/null | tail -1)
    send_imessage "❌ ASADO daily FAILED after retry. ${FAILED_STAGE:-See log.} Log: ${LATEST_LOG:-unknown}. Fix then: python scripts/daily_update.py --resume"
    log "daily_update failed after retry (exit $RC). Alert sent."
    exit "$RC"
fi

log "ASADO daily pipeline completed OK."
exit 0
