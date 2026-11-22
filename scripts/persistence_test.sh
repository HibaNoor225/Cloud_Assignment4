#!/usr/bin/env bash
# Milestone 02 persistence test: delete mongo-1 and prove it comes back with the
# same name, the same PVC, and that no documents were lost.
# Usage: scripts/persistence_test.sh results/m02/persistence_test.txt
set -euo pipefail
NS="${NS:-emi}"
OUT="${1:-results/m02/persistence_test.txt}"
DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$(dirname "$OUT")"

{
  echo "=== Persistence test $(date '+%F %T') ==="
  echo
  echo "--- BEFORE: pods ---"
  kubectl get pods -n "$NS" -l app=mongo -o wide
  echo
  echo "--- BEFORE: PVCs ---"
  kubectl get pvc -n "$NS"
  echo
  echo "--- BEFORE: mongo-1 PVC and UID ---"
  kubectl get pod mongo-1 -n "$NS" -o jsonpath='pod uid={.metadata.uid}  pvc={.spec.volumes[?(@.name=="data")].persistentVolumeClaim.claimName}{"\n"}'
  echo
  echo "--- BEFORE: documents in calculations ---"
  "$DIR/count_documents.sh"
  echo
  echo "--- kubectl delete pod mongo-1 ---"
  kubectl delete pod mongo-1 -n "$NS"
  echo
  echo "--- Waiting for mongo-1 to be Ready again ---"
  sleep 3
  kubectl wait --for=condition=Ready pod/mongo-1 -n "$NS" --timeout=180s
  echo
  echo "--- AFTER: pods (note the young AGE of mongo-1) ---"
  kubectl get pods -n "$NS" -l app=mongo -o wide
  echo
  echo "--- AFTER: PVCs (same names, still Bound) ---"
  kubectl get pvc -n "$NS"
  echo
  echo "--- AFTER: mongo-1 PVC and UID (new UID, same PVC) ---"
  kubectl get pod mongo-1 -n "$NS" -o jsonpath='pod uid={.metadata.uid}  pvc={.spec.volumes[?(@.name=="data")].persistentVolumeClaim.claimName}{"\n"}'
  echo
  echo "--- AFTER: documents in calculations ---"
  sleep 5
  "$DIR/count_documents.sh"
  echo
  echo "--- Replica set after recovery ---"
  "$DIR/mongo_primary.sh"
} 2>&1 | tee "$OUT"
