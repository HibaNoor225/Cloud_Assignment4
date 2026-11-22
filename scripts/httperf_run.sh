#!/usr/bin/env bash
# Runs one httperf test of POST /api/emi (random inputs) at RATE req/s for SECONDS.
# Usage: scripts/httperf_run.sh RATE SECONDS OUTPUT_FILE
set -euo pipefail

RATE="$1"; SECONDS_="$2"; OUT="$3"
HOST="${HOST:-emi.local}"
DIR="$(cd "$(dirname "$0")" && pwd)"
TOTAL=$(( RATE * SECONDS_ ))
SESS="$(mktemp)"

python3 "$DIR/gen_wsesslog.py" "$TOTAL" "$SESS"
mkdir -p "$(dirname "$OUT")"

echo ">>> httperf: $RATE req/s for ${SECONDS_}s ($TOTAL requests) -> $OUT"
httperf --hog --server "$HOST" --port "${PORT:-80}" \
  --wsesslog="$TOTAL,0,$SESS" --rate "$RATE" --timeout 5 \
  --add-header='Content-Type: application/x-www-form-urlencoded\n' \
  > "$OUT" 2>&1 || true

rm -f "$SESS"
grep -E 'Reply time|Errors: total|Reply status' "$OUT" || tail -n 5 "$OUT"
