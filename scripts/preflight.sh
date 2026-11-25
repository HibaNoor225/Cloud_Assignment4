#!/usr/bin/env bash
# Checks everything Milestone 04 needs before a long test starts, so it fails in
# seconds instead of producing incomplete results.
set -uo pipefail
NS="${NS:-emi}"
HOST="${HOST:-emi.local}"
fail=0

check() {
  if eval "$2" >/dev/null 2>&1; then echo "  ok    $1"; else echo "  FAIL  $1 -> $3"; fail=1; fi
}

echo "Pre-flight checks:"
check "python has psutil + matplotlib" "python3 -c 'import psutil, matplotlib'" \
  "run: cd ~/assignment4 && source .venv/bin/activate   (create it first if missing: python3 -m venv .venv && source .venv/bin/activate && pip install matplotlib psutil)"
check "httperf installed" "command -v httperf" "run: brew install httperf"
check "kubectl top works (metrics-server)" "kubectl top pods -n $NS" "run: minikube addons enable metrics-server, wait 1-2 min"
check "http://$HOST/health answers" "curl -s -f -m 10 http://$HOST/health" \
  "start 'minikube tunnel -p emi' in its own window (macOS) and check /etc/hosts has $HOST"

if [ "$fail" -ne 0 ]; then
  echo "Fix the FAIL lines above, then run the script again."
  exit 1
fi
echo
