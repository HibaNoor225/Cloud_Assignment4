# Loan EMI Calculator on Kubernetes (Minikube)

DS-584 Cloud Computing, Fall 2026, Assignment 4: *Deploying, Load Balancing and Autoscaling a Web Application with MongoDB on Kubernetes.*

A Loan EMI calculator (Node.js/Express, HTML, Bootstrap, jQuery) that stores every calculation in MongoDB. It runs on a single-node Minikube cluster as a 3-replica Deployment behind a ClusterIP Service and an NGINX Ingress (`http://emi.local`), with MongoDB as a 3-member replica set (StatefulSet with persistent volumes) and a HorizontalPodAutoscaler (1–5 pods at 50% CPU).

> **Step-by-step guides from zero (setup on macOS, each milestone, deliverables):** start at [docs/00-MASTER-PLAN.md](docs/00-MASTER-PLAN.md).

## Repository layout

```text
app/        Web application (Express server, static UI, Dockerfile, .dockerignore)
k8s/        Kubernetes manifests, applied with kubectl apply -f k8s/
k8s/hpa/    HorizontalPodAutoscaler (applied separately for the autoscaling test)
scripts/    Load distribution, request loop, persistence test, load tests, profiling, graphs
results/    Raw outputs of every experiment, and graphs
docs/       Detailed guides per milestone + report template
```

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/emi` | Body `principal`, `rate` (annual %), `months` as JSON or form data. Returns `emi`, `totalPayment`, `totalInterest`, `servedBy` (pod name from `HOSTNAME`), `podIp`. Saves the calculation. |
| `GET` | `/api/history` | Last 10 calculations, newest first |
| `GET` | `/health` | `200` only when MongoDB is reachable (readiness/liveness probe), otherwise `503` |
| `GET` | `/api/version` | Image version (shown in the footer) |

`EMI = P·r·(1+r)^n / ((1+r)^n − 1)` with `r = rate / 12 / 100`. Configuration: `MONGO_URL` (required), `PORT` (default 3000).

## Run locally (Milestone 01)

```bash
docker run -d --name emi-mongo -p 27017:27017 mongo:7.0
cd app
npm install
npm test
MONGO_URL="mongodb://localhost:27017/emidb" node server.js
# open http://localhost:3000
```

## Bring up the whole system on a fresh Minikube cluster

Prerequisites: Docker, Minikube, kubectl.

```bash
# 1. Cluster and add-ons
minikube start -p emi --driver=docker --cpus=4 --memory=6144
minikube profile emi
minikube addons enable ingress
minikube addons enable metrics-server

# 2. Application image
docker build -t emi-web:1.0 app/
minikube image load emi-web:1.0

# 3. Everything else: namespace, MongoDB replica set + init Job, ConfigMap,
#    web Deployment + Service, Ingress
kubectl apply -f k8s/

# 4. Wait until it is ready
kubectl wait --for=condition=complete job/mongo-init -n emi --timeout=300s
kubectl rollout status deployment/emi-web -n emi
kubectl get all,pvc,configmap -n emi -o wide

# 5. Reach it through the Ingress
# macOS / Windows (Docker driver): map emi.local to 127.0.0.1 and keep a tunnel running
echo "127.0.0.1 emi.local" | sudo tee -a /etc/hosts
minikube tunnel -p emi          # in a separate terminal, leave it open
# Linux instead: echo "$(minikube ip) emi.local" | sudo tee -a /etc/hosts
curl http://emi.local/health
# browser: http://emi.local

# Quick check without Ingress
kubectl port-forward svc/emi-web 8080:80 -n emi     # http://localhost:8080
```

Autoscaling (applied only for the Milestone 04 HPA test, so it doesn't override manual scaling):

```bash
kubectl apply -f k8s/hpa/
kubectl get hpa emi-web -n emi
```

## Experiments

| Script | Purpose |
|---|---|
| `scripts/persistence_test.sh` | Delete `mongo-1`, show same name, same PVC, same document count |
| `scripts/load_distribution.sh N OUT` | N requests through the Ingress, count per pod |
| `scripts/request_loop.sh OUT` | Request every 0.2 s until Ctrl+C, prints ok/failed summary |
| `scripts/mongo_primary.sh` | Replica-set member states and current PRIMARY |
| `scripts/count_documents.sh` | Documents in `emidb.calculations` |
| `scripts/run_fixed_experiments.sh` | 15 httperf runs (1/2/3 replicas × 10–200 req/s) with profiling |
| `scripts/run_autoscale_test.sh` | 10-minute HPA test (10 → 100 → 10 req/s) |
| `scripts/monitor.py` | `kubectl top pods` every 15 s, host CPU every 1 s, optional HPA every 15 s, to CSV |
| `scripts/make_graphs.py` | Graphs 1–3 into `results/graphs/` |

Load-test tools (macOS): `brew install httperf`, then `python3 -m venv .venv && source .venv/bin/activate && pip install matplotlib psutil`.

## Tear down

```bash
kubectl delete -f k8s/hpa/ --ignore-not-found
kubectl delete -f k8s/          # PVCs from volumeClaimTemplates remain; delete with:
kubectl delete pvc -n emi --all
minikube delete -p emi
```
