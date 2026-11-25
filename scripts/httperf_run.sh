#!/usr/bin/env bash
# Runs one httperf test of POST /api/emi (random inputs) at RATE req/s for SECONDS.
# Usage: scripts/httperf_run.sh RATE SECONDS OUTPUT_FILE
#
# httperf session mode: each session opens ONE persistent connection and sends
# BURSTS requests on it, THINK seconds apart. Sessions start at RATE/BURSTS per
# second, so the request rate is RATE while new connections are 10x fewer. Opening
# a new connection for every request overloads `minikube tunnel` on macOS at high rates.
set -euo pipefail

RATE="$1"; SECONDS_="$2"; OUT="$3"
HOST="${HOST:-emi.local}"
DIR="$(cd "$(dirname "$0")" && pwd)"
BURSTS="${BURSTS:-10}"
THINK="${THINK:-0.1}"
mkdir -p "$(dirname "$OUT")"

TOTAL=$(( RATE * SECONDS_ ))
SESSIONS=$(( (TOTAL + BURSTS - 1) / BURSTS ))
SESSION_RATE=$(awk -v r="$RATE" -v b="$BURSTS" 'BEGIN { printf "%.3f", r / b }')
# httperf accepts at most 1000 session templates and cycles through them.
TEMPLATES=$(( SESSIONS < 1000 ? SESSIONS : 1000 ))
SESS="$(mktemp)"
python3 "$DIR/gen_wsesslog.py" "$TEMPLATES" "$SESS" "$BURSTS"

echo ">>> httperf: $RATE req/s for ${SECONDS_}s ($TOTAL requests = $SESSIONS sessions x $BURSTS requests, $SESSION_RATE sessions/s) -> $OUT"
httperf --hog --server "$HOST" --port "${PORT:-80}" \
  --wsesslog="$SESSIONS,$THINK,$SESS" --rate "$SESSION_RATE" --timeout 5 \
  --add-header='Content-Type: application/x-www-form-urlencoded\n' \
  > "$OUT" 2>&1 &
hp=$!

# Safety net: stop httperf if it runs far past its planned time. SIGINT makes it print
# its statistics; SIGKILL follows if it doesn't react.
LIMIT=$(( SECONDS_ + 45 ))
( sleep "$LIMIT"
  if kill -0 "$hp" 2>/dev/null; then
    echo "!!! httperf still running after ${LIMIT}s, stopping it" >&2
    kill -INT "$hp" 2>/dev/null; sleep 10; kill -KILL "$hp" 2>/dev/null
  fi ) &
wd=$!
wait "$hp" || true
kill "$wd" 2>/dev/null || true
wait "$wd" 2>/dev/null || true
rm -f "$SESS"

if ! grep -q 'Reply status' "$OUT"; then
  echo "!!! httperf produced no results. Its output:" >&2
  cat "$OUT" >&2
  exit 1
fi
grep -E 'Request rate|Reply time|Errors: total|Reply status' "$OUT"
