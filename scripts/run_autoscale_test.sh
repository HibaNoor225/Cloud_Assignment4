#!/usr/bin/env bash
# Milestone 04, task 4: 10-minute HPA test.
#   2 min at 10 req/s -> 5 min at 100 req/s -> 3 min at 10 req/s
# Records kubectl get hpa every 15 s (hpa.csv), pod CPU/memory (pods.csv),
# host CPU (host_cpu.csv) and the planned request rate per phase (phases.csv).
set -euo pipefail

NS="${NS:-emi}"
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
OUT="$ROOT/results/m04/autoscale"

"$DIR/preflight.sh"
mkdir -p "$OUT"

echo "Applying HPA and starting from 1 replica"
kubectl apply -f "$ROOT/k8s/hpa/"
kubectl scale deployment emi-web -n "$NS" --replicas=1
kubectl rollout status deployment emi-web -n "$NS" --timeout=180s
echo "Waiting 60 s for the HPA to read its first metrics"
sleep 60
kubectl get hpa emi-web -n "$NS"

echo "phase,rate,start,end" > "$OUT/phases.csv"
python3 "$DIR/monitor.py" --out-dir "$OUT" --hpa &
mon=$!

# Local time without a UTC offset, matching the timestamps monitor.py writes.
now() { date '+%Y-%m-%dT%H:%M:%S'; }

phase() {
  local name="$1" rate="$2" secs="$3"
  local start; start=$(now)
  if ! "$DIR/httperf_run.sh" "$rate" "$secs" "$OUT/httperf_${name}.txt"; then
    kill -TERM "$mon"; wait "$mon" || true
    echo "Stopping: httperf failed in phase $name" >&2
    exit 1
  fi
  echo "$name,$rate,$start,$(now)" >> "$OUT/phases.csv"
}

phase 1_warmup 10 120
phase 2_peak 100 300
phase 3_cooldown 10 180

kill -TERM "$mon"; wait "$mon" || true
kubectl get hpa emi-web -n "$NS" | tee "$OUT/hpa_final.txt"
kubectl describe hpa emi-web -n "$NS" > "$OUT/hpa_describe.txt"
echo "Done. Results in $OUT"
