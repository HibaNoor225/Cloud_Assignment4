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

total=0; ok=0; failed=0

summary() {
  echo | tee -a "$OUT"
  echo "SUMMARY: total=$total ok=$ok failed=$failed" | tee -a "$OUT"
  exit 0
}
trap summary INT TERM

while true; do
  total=$((total + 1))
  resp=$(curl -s -m 5 -w '\n%{http_code}' -X POST "$URL/api/emi" \
    -H 'Content-Type: application/json' \
    -d '{"principal":500000,"rate":12,"months":24}')
  code=$(echo "$resp" | tail -n1)
  body=$(echo "$resp" | sed '$d')
  pod=$(echo "$body" | sed -n 's/.*"servedBy":"\([^"]*\)".*/\1/p')
  ver=$(echo "$body" | sed -n 's/.*"version":"\([^"]*\)".*/\1/p')
  if [ "$code" = "200" ]; then ok=$((ok + 1)); status=OK; else failed=$((failed + 1)); status=FAIL; fi
  echo "$(date '+%T') #$total $status http=$code version=${ver:--} pod=${pod:--}" | tee -a "$OUT"
  sleep "$INTERVAL"
done
