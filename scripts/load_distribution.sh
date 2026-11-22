#!/usr/bin/env bash
# Sends N POST /api/emi requests through the Ingress and counts how many each pod served.
# Usage: scripts/load_distribution.sh [N] [output-file]
#   scripts/load_distribution.sh 30 results/m03/distribution_3_replicas.txt
set -euo pipefail

N="${1:-30}"
OUT="${2:-/dev/stdout}"
URL="${URL:-http://emi.local}"

mkdir -p "$(dirname "$OUT")" 2>/dev/null || true
tmp="$(mktemp)"

for i in $(seq 1 "$N"); do
  p=$(( (RANDOM % 900 + 100) * 1000 ))
  r=$(( RANDOM % 20 + 1 ))
  m=$(( RANDOM % 60 + 6 ))
  body=$(curl -s -m 10 -X POST "$URL/api/emi" \
    -H 'Content-Type: application/json' \
    -d "{\"principal\":$p,\"rate\":$r,\"months\":$m}")
  pod=$(echo "$body" | sed -n 's/.*"servedBy":"\([^"]*\)".*/\1/p')
  echo "$(date '+%T') request $i -> ${pod:-FAILED}" | tee -a "$tmp" >&2
done

{
  echo "Requests per pod ($N requests to $URL/api/emi at $(date '+%F %T')):"
  echo
  printf '%-40s %s\n' "POD" "REQUESTS"
  sed 's/.*-> //' "$tmp" | sort | uniq -c | sort -rn | awk '{printf "%-40s %s\n", $2, $1}'
  echo
  echo "Raw log:"
  cat "$tmp"
} > "$OUT"

[ "$OUT" != "/dev/stdout" ] && head -n 12 "$OUT"
rm -f "$tmp"
