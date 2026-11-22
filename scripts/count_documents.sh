#!/usr/bin/env bash
# Prints the number of documents in emidb.calculations (read through the replica set).
set -euo pipefail
NS="${NS:-emi}"
URI="mongodb://mongo-0.mongo:27017,mongo-1.mongo:27017,mongo-2.mongo:27017/emidb?replicaSet=rs0"

for pod in mongo-0 mongo-1 mongo-2; do
  if kubectl exec -n "$NS" "$pod" -- mongosh "$URI" --quiet --eval 'db.calculations.countDocuments()' 2>/dev/null; then
    exit 0
  fi
done
echo "Could not reach the replica set" >&2
exit 1
