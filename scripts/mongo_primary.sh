#!/usr/bin/env bash
# Prints the replica-set member states and the pod that is currently PRIMARY.
set -euo pipefail
NS="${NS:-emi}"

for pod in mongo-0 mongo-1 mongo-2; do
  out=$(kubectl exec -n "$NS" "$pod" -- mongosh --quiet --eval \
    'rs.status().members.forEach(m => print(m.name + "  " + m.stateStr))' 2>/dev/null) && {
    echo "$out"
    primary=$(echo "$out" | awk '$2=="PRIMARY"{print $1}' | cut -d. -f1)
    echo
    echo "PRIMARY pod: ${primary:-none}"
    exit 0
  }
done
echo "Could not reach any mongo pod" >&2
exit 1
