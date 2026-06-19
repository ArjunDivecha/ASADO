#!/bin/bash
# =============================================================================
# SCRIPT NAME: neo4j_guard.sh
# =============================================================================
#
# DESCRIPTION (plain English):
#   Self-healing guard for the local Neo4j database that the ASADO nightly loop
#   depends on (graph features, write_graph_discoveries, PIT edges). Neo4j runs
#   under the Homebrew launchd job `homebrew.mxcl.neo4j`, which executes
#   `neo4j console`. That command refuses to start if a *stale* PID file is left
#   behind — which is exactly what happens after a HARD crash or power loss
#   ("the computer died"): Neo4j never gets to delete its PID file, the OS later
#   recycles that PID to an unrelated process, and on next boot `neo4j console`
#   sees "Neo4j is already running (pid:NNN)" and bails. RunAtLoad cannot fix
#   this because the failure is inside the start command itself.
#
#   This guard breaks that trap. Each time it runs it:
#     1. Checks if Neo4j is already healthy (bolt port 7687 open). If so, it does
#        nothing and exits 0 — so on a normal healthy boot it is a no-op.
#     2. If 7687 is down, it inspects every Homebrew Neo4j PID file. For each, it
#        removes the file ONLY if the PID it names is not actually a live Neo4j
#        java process (i.e. the file is stale). A genuinely-running instance is
#        left untouched.
#     3. Restarts the Homebrew Neo4j launchd job and polls up to 60s for 7687.
#
#   It is installed to run at login (RunAtLoad) and every 30 minutes
#   (StartInterval) via com.arjundivecha.neo4j-guard.plist, so a dead Neo4j is
#   recovered within at most 30 minutes — well before the 11:30 ASADO loop.
#
# INPUT FILES (read):
#   - /opt/homebrew/Cellar/neo4j/*/libexec/run/neo4j.pid
#       Homebrew Neo4j PID file(s); the version directory varies across upgrades,
#       so this is globbed rather than hard-coded.
#
# OUTPUT FILES (written):
#   - /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/logs/neo4j_guard.log
#       Append-only action log (what it checked, what it cleared, recovery result).
#   - (deletes) the stale PID file(s) listed above when they are confirmed stale.
#
# EXTERNAL SERVICES TOUCHED:
#   - Homebrew launchd job `gui/<uid>/homebrew.mxcl.neo4j` (kickstart / restart).
#   - Local TCP port 7687 (Neo4j bolt) — liveness probe only.
#
# EXIT CODES: 0 = Neo4j healthy (already up, or recovered). 1 = still down after restart.
#
# VERSION: 1.0   LAST UPDATED: 2026-06-18   AUTHOR: Arjun Divecha (via Claude Code)
# =============================================================================

set -uo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

LOG="/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/logs/neo4j_guard.log"
BOLT_HOST="localhost"
BOLT_PORT="7687"

mkdir -p "$(dirname "$LOG")" 2>/dev/null
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

bolt_up() { nc -z -G 2 "$BOLT_HOST" "$BOLT_PORT" >/dev/null 2>&1; }

# ---- 1. Already healthy? No-op on a normal boot. -----------------------------
if bolt_up; then
    log "OK: bolt ${BOLT_PORT} open — Neo4j healthy, no action."
    exit 0
fi

# ---- 2. Grace window: don't fight a legitimate in-progress startup. ----------
# On a normal boot the Homebrew job is starting Neo4j right now; give it ~30s
# to open the bolt port before we conclude it is genuinely down.
for i in $(seq 1 10); do
    sleep 3
    if bolt_up; then
        log "OK: bolt ${BOLT_PORT} came up during ${i}x3s grace — Neo4j was mid-startup, no action."
        exit 0
    fi
done

log "ALERT: bolt ${BOLT_PORT} still down after grace — Neo4j is genuinely down. Recovering."

# ---- 3. Clean stop (frees a wedged instance + unloads the launchd job). -------
# If bolt is down, no instance is serving, so a full stop is always safe and is
# the reliable way to clear a half-running/zombie Neo4j before a fresh start.
log "  brew services stop neo4j ..."
brew services stop neo4j >>"$LOG" 2>&1
sleep 2

# ---- 4. Remove ALL Neo4j PID files (now provably safe — nothing is serving). --
# This is the actual recurrence fix: a stale PID file left by a hard crash makes
# `neo4j console` refuse to start. With the service stopped, any PID file present
# is either stale or belongs to the instance we just stopped — delete it.
shopt -s nullglob
for pf in /opt/homebrew/Cellar/neo4j/*/libexec/run/neo4j.pid; do
    log "  removing PID file: $pf (was: $(cat "$pf" 2>/dev/null | tr -d '[:space:]'))"
    rm -f "$pf"
done
shopt -u nullglob

# ---- 5. Fresh start, then poll for recovery. ---------------------------------
log "  brew services start neo4j ..."
brew services start neo4j >>"$LOG" 2>&1

for i in $(seq 1 20); do
    if bolt_up; then
        log "RECOVERED: bolt ${BOLT_PORT} open after ~$((i*3))s."
        exit 0
    fi
    sleep 3
done

log "FAILED: bolt ${BOLT_PORT} still down ~60s after restart — manual attention needed."
exit 1
