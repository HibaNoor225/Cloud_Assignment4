#!/usr/bin/env bash
# Sends one POST /api/emi every INTERVAL seconds until Ctrl+C, logging each result.
# Prints a summary (total / ok / failed) when stopped.
# Usage: scripts/request_loop.sh results/m03/rolling_update_loop.log
set -uo pipefail

OUT="${1:-results/request_loop.log}"
URL="${URL:-http://emi.local}"
INTERVAL="${INTERVAL:-0.2}"
mkdir -p "$(dirname "$OUT")"
: > "$OUT"

# Resolve the host once: on macOS every lookup of a *.local name can stall ~5 s on Bonjour,
# which would make each request hit the curl timeout.
HOST=$(echo "$URL" | sed -E 's#^https?://([^/:]+).*#\1#')
IP=$(python3 -c 'import socket, sys; print(socket.gethostbyname(sys.argv[1]))' "$HOST" 2>/dev/null || true)
RESOLVE="${IP:+$HOST:80:$IP}"
echo "Sending to $URL (resolved $HOST -> ${IP:-system DNS})"

total=0; ok=0; failed=0

summary() {
  echo | tee -a "$OUT"
  echo "SUMMARY: total=$total ok=$ok failed=$failed" | tee -a "$OUT"
  exit 0
}
trap summary INT TERM

while true; do
  total=$((total + 1))
  resp=$(curl -s -m 5 ${RESOLVE:+--resolve "$RESOLVE"} -w '\n%{http_code}' -X POST "$URL/api/emi" \
    -H 'Content-Type: application/json' \
    -d '{"principal":500000,"rate":12,"months":24}')
  rc=$?
  code=$(echo "$resp" | tail -n1)
  body=$(echo "$resp" | sed '$d')
  pod=$(echo "$body" | sed -n 's/.*"servedBy":"\([^"]*\)".*/\1/p')
  ver=$(echo "$body" | sed -n 's/.*"version":"\([^"]*\)".*/\1/p')
  if [ "$code" = "200" ]; then
    ok=$((ok + 1)); status=OK; detail=""
  else
    failed=$((failed + 1)); status=FAIL
    # curl exit codes: 7 = connection refused, 28 = timeout
    detail=" curl_exit=$rc body=$(echo "$body" | head -c 120)"
  fi
  echo "$(date '+%T') #$total $status http=$code version=${ver:--} pod=${pod:--}$detail" | tee -a "$OUT"
  sleep "$INTERVAL"
done
