#!/bin/bash
set -u

REPO="/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
URL="http://127.0.0.1:8800/cockpit_live.html"
LOG_DIR="$HOME/Library/Logs/ASADO Cockpit"
LOG_FILE="$LOG_DIR/server.log"
PID_FILE="$LOG_DIR/server.pid"
LOCK_DIR="$LOG_DIR/launch.lock"

mkdir -p "$LOG_DIR"

show_error() {
  /usr/bin/osascript -e 'display dialog "ASADO Cockpit could not start.\n\nSee the log for details:\n~/Library/Logs/ASADO Cockpit/server.log" with title "ASADO Cockpit" buttons {"OK"} default button "OK" with icon stop' >/dev/null 2>&1 || true
}

ui_is_ready() {
  /usr/bin/curl --silent --fail --max-time 2 "$URL" >/dev/null 2>&1
}

stop_server() {
  if [ -f "$PID_FILE" ]; then
    SERVER_PID="$(/bin/cat "$PID_FILE" 2>/dev/null || true)"
    if [[ "$SERVER_PID" =~ ^[0-9]+$ ]] && /bin/kill -0 "$SERVER_PID" 2>/dev/null; then
      printf '[%s] Stopping ASADO Cockpit (pid %s)\n' "$(date)" "$SERVER_PID" >>"$LOG_FILE"
      /bin/kill "$SERVER_PID" 2>/dev/null || true
      for _ in {1..20}; do
        /bin/kill -0 "$SERVER_PID" 2>/dev/null || break
        /bin/sleep 0.25
      done
      /bin/kill -9 "$SERVER_PID" 2>/dev/null || true
    fi
    /bin/rm -f "$PID_FILE"
  fi
  # Clean up an older launcher-created server whose pid file was lost.
  for PID in $(/usr/bin/pgrep -f 'uvicorn cos_mockups.cos_chat_service:app.*--port 8800' 2>/dev/null || true); do
    /bin/kill "$PID" 2>/dev/null || true
  done
}

case "${1:-start}" in
  stop)
    stop_server
    exit 0
    ;;
  status)
    ui_is_ready
    exit $?
    ;;
  start) ;;
  *) printf 'Usage: %s {start|stop|status}\n' "$0" >&2; exit 2 ;;
esac

if ui_is_ready; then
  /usr/bin/open "$URL"
  exit 0
fi

# Serialize rapid double-clicks. A launcher exits quickly, so a directory lock is
# enough and avoids relying on flock (not shipped by macOS).
if ! /bin/mkdir "$LOCK_DIR" 2>/dev/null; then
  for _ in {1..60}; do
    if ui_is_ready; then
      /usr/bin/open "$URL"
      exit 0
    fi
    /bin/sleep 0.5
  done
  /bin/rm -rf "$LOCK_DIR"
  show_error
  exit 1
fi
trap '/bin/rm -rf "$LOCK_DIR"' EXIT

if [ ! -x "$REPO/venv/bin/python" ] || [ ! -f "$REPO/scripts/run_discovery_cockpit.sh" ]; then
  printf '[%s] Missing ASADO runtime or cockpit script under %s\n' "$(date)" "$REPO" >>"$LOG_FILE"
  show_error
  exit 1
fi

# Refuse to trample an unrelated service already using the cockpit port.
if /usr/sbin/lsof -nP -iTCP:8800 -sTCP:LISTEN >/dev/null 2>&1; then
  printf '[%s] Port 8800 is occupied, but the cockpit URL did not respond.\n' "$(date)" >>"$LOG_FILE"
  /usr/bin/osascript -e 'display dialog "Port 8800 is already being used by another process. ASADO Cockpit was not started.\n\nSee ~/Library/Logs/ASADO Cockpit/server.log" with title "ASADO Cockpit" buttons {"OK"} default button "OK" with icon caution' >/dev/null 2>&1 || true
  exit 1
fi

printf '\n[%s] Starting ASADO Cockpit in serve-only mode\n' "$(date)" >>"$LOG_FILE"
cd "$REPO" || exit 1
/usr/bin/nohup /bin/bash "$REPO/scripts/run_discovery_cockpit.sh" --serve-only >>"$LOG_FILE" 2>&1 </dev/null &
SERVER_PID=$!
printf '%s\n' "$SERVER_PID" >"$PID_FILE"

for _ in {1..120}; do
  if ui_is_ready; then
    printf '[%s] Cockpit ready (pid %s)\n' "$(date)" "$SERVER_PID" >>"$LOG_FILE"
    /usr/bin/open "$URL"
    exit 0
  fi
  if ! /bin/kill -0 "$SERVER_PID" 2>/dev/null; then
    printf '[%s] Cockpit process exited before becoming ready.\n' "$(date)" >>"$LOG_FILE"
    show_error
    exit 1
  fi
  /bin/sleep 0.5
done

printf '[%s] Timed out waiting for cockpit startup.\n' "$(date)" >>"$LOG_FILE"
show_error
exit 1
