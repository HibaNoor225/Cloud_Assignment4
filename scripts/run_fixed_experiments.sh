#!/usr/bin/env bash
# Milestone 04, task 2 + 3: 15 runs = replicas {1,2,3} x rates {10,25,50,100,200} req/s, 60 s each.
# For every run it saves the httperf output plus pods.csv / host_cpu.csv from monitor.py,
# and appends a line to results/m04/fixed/summary.csv.
# Usage: scripts/run_fixed_experiments.sh            (all 15 runs)
#        REPLICAS="3" RATES="100" scripts/run_fixed_experiments.sh   (a single run)
set -euo pipefail

NS="${NS:-emi}"
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
OUTROOT="$ROOT/results/m04/fixed"
REPLICAS="${REPLICAS:-1 2 3}"
RATES="${RATES:-10 25 50 100 200}"
DURATION="${DURATION:-60}"

mkdir -p "$OUTROOT"
SUMMARY="$OUTROOT/summary.csv"
[ -f "$SUMMARY" ] || echo "replicas,rate,avg_response_ms,errors,replies_2xx,run_dir" > "$SUMMARY"

echo "Removing any HPA so the replica count stays fixed"
kubectl delete hpa emi-web -n "$NS" --ignore-not-found

for rep in $REPLICAS; do
  echo "=============== $rep replica(s) ==============="
  kubectl scale deployment emi-web -n "$NS" --replicas="$rep"
  kubectl rollout status deployment emi-web -n "$NS" --timeout=180s
  sleep 15

  for rate in $RATES; do
    run="$OUTROOT/r${rep}_rate${rate}"
    mkdir -p "$run"
    kubectl get pods -n "$NS" -o wide > "$run/pods_before.txt"

    python3 "$DIR/monitor.py" --out-dir "$run" &
    mon=$!
    "$DIR/httperf_run.sh" "$rate" "$DURATION" "$run/httperf.txt"
    kill -TERM "$mon"; wait "$mon" || true

    resp=$(sed -n 's/.*Reply time \[ms\]: response \([0-9.]*\) transfer \([0-9.]*\).*/\1 \2/p' "$run/httperf.txt")
    avg=$(echo "${resp:-0 0}" | awk '{printf "%.1f", $1 + $2}')
    errs=$(sed -n 's/.*Errors: total \([0-9]*\).*/\1/p' "$run/httperf.txt")
    ok=$(sed -n 's/.*2xx=\([0-9]*\).*/\1/p' "$run/httperf.txt")
    bad=$(sed -n 's/.*4xx=\([0-9]*\) 5xx=\([0-9]*\).*/\1 \2/p' "$run/httperf.txt" | awk '{print $1 + $2}')
    errors=$(( ${errs:-0} + ${bad:-0} ))
    echo "$rep,$rate,$avg,$errors,${ok:-0},r${rep}_rate${rate}" >> "$SUMMARY"
    echo "    -> replicas=$rep rate=$rate avg=${avg}ms errors=$errors"
    sleep 15
  done
done

echo
echo "Done. Summary:"
column -s, -t "$SUMMARY"
