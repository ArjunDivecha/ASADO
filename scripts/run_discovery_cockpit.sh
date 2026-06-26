#!/usr/bin/env bash
# =============================================================================
# run_discovery_cockpit.sh — run the Discovery Triage pipeline and serve the cockpit.
#
# WHAT IT DOES:
#   1. (unless --serve-only) runs the live Discovery Lab docket (real Anthropic spend)
#   2. runs forward tracking
#   3. rebuilds the cockpit payload (incl. the Research Desk) and the live HTML
#   4. serves the cockpit at http://localhost:8800/cockpit_live.html
#
# USAGE:
#   bash scripts/run_discovery_cockpit.sh                       # all 5 searches, live
#   bash scripts/run_discovery_cockpit.sh cross_surface_contradiction   # one search, live
#   bash scripts/run_discovery_cockpit.sh --serve-only         # NO spend: rebuild from
#                                                              # existing journal + serve
#
# ENV:
#   ASADO_DATA_ROOT  default: the main ASADO checkout's Data (holds the loop DB)
#   PORT             default: 8800
# =============================================================================
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
export ASADO_DATA_ROOT="${ASADO_DATA_ROOT:-/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data}"
PY="${ASADO_PY:-/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python}"
PORT="${PORT:-8800}"

SERVE_ONLY=0
SEARCHES=()
for a in "$@"; do
  if [ "$a" = "--serve-only" ]; then SERVE_ONLY=1; else SEARCHES+=("--search" "$a"); fi
done

if [ "$SERVE_ONLY" -eq 0 ]; then
  echo "[1/3] Discovery docket (LIVE Anthropic — costs tokens)..."
  "$PY" -m scripts.discovery_triage.daily_docket "${SEARCHES[@]}"
  echo "[2/3] forward tracking..."
  "$PY" -m scripts.discovery_triage.forward_track || true
else
  echo "[serve-only] skipping the live Lab; rebuilding the cockpit from the existing journal."
fi

echo "[3/3] building cockpit data + live HTML..."
"$PY" cos_mockups/build_cockpit_data.py >/dev/null
"$PY" cos_mockups/make_live_cockpit.py >/dev/null

echo ""
echo "  Cockpit ready →  http://localhost:${PORT}/cockpit_live.html"
echo "  (open it, then click the 'Discovery Lab' tab in the focus panel)"
echo "  Ctrl-C to stop the server."
cd "$REPO/cos_mockups"
exec "$PY" -m http.server "$PORT"
