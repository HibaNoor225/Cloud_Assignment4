# Loan EMI Calculator with MongoDB on Kubernetes (Minikube)

**DS-584 Cloud Computing, Fall 2026, Assignment 4:** *Deploying, Load Balancing and Autoscaling a Web Application with MongoDB on Kubernetes (Minikube).*
FCIT, University of the Punjab. Instructor: Dr. Numan Shafi.

This repository contains a Loan EMI (Equated Monthly Instalment) calculator and everything needed to run it on a single-node Minikube cluster:

- a **Node.js/Express** server with an **HTML + Bootstrap 5 + jQuery (AJAX)** front end, which stores every calculation in **MongoDB**;
- a **3-member MongoDB replica set** (`rs0`) in a StatefulSet, each member with its own 1 Gi PersistentVolumeClaim;
- a **3-replica web Deployment** behind a ClusterIP Service and an **NGINX Ingress** at `http://emi.local`;
- a **HorizontalPodAutoscaler** (1–5 pods at 50% CPU);
- load-test, profiling and graph scripts, with all raw results in `results/`.

The whole system comes up on a fresh Minikube cluster with **`kubectl apply -f k8s/`** (see [Bring up the whole system](#bring-up-the-whole-system-on-a-fresh-minikube-cluster)).

---

## Architecture

```text
 Host (macOS / Linux / Windows)
 ┌──────────────────────────────┐
 │ browser, curl, httperf       │
 │        http://emi.local      │
 └──────────────┬───────────────┘
                │ HTTP  (minikube tunnel -> 127.0.0.1 on macOS/Windows, minikube ip on Linux)
 ┌──────────────▼──────────────────────────────────────────────────────────────┐
 │ Minikube node · namespace emi                                               │
 │                                                                             │
 │   Ingress (NGINX controller, host emi.local, path /)                        │
 │                │                                                            │
 │   Service emi-web (ClusterIP, port 80 -> 3000)                              │
 │       ┌────────┼────────┐                  HPA emi-web                      │
 │   emi-web   emi-web   emi-web   <─scales── 1–5 pods, target 50% CPU         │
 │   pod 1     pod 2     pod 3     (Deployment emi-web)                        │
 │       └────────┼────────┘                                                   │
 │                │ MONGO_URL (ConfigMap emi-config): reads and writes         │
 │   ┌────────────┼──────────────────┐                                         │
 │   mongo-0      mongo-1      mongo-2      StatefulSet mongo                  │
 │   PRIMARY      SECONDARY    SECONDARY    headless Service mongo             │
 │   PVC data-0   PVC data-1   PVC data-2   replica set rs0                    │
 └─────────────────────────────────────────────────────────────────────────────┘
```

Only the Ingress is reachable from the host. The Service spreads requests over the **Ready** web pods. Each web pod connects to the whole replica set, and the MongoDB driver sends writes to whichever member is currently PRIMARY.

---

## How each requirement is met

### Milestone 01: EMI calculator with MongoDB

| Requirement | Implementation |
|---|---|
| HTML, jQuery, Bootstrap + server framework | `app/public/index.html`, `app/public/app.js` (jQuery), Bootstrap 5; server is Node.js/Express (`app/server.js`) |
| `EMI = P·r·(1+r)^n / ((1+r)^n − 1)`, `r = rate/12/100` | `calculateEmi()` in `app/emi.js` |
| Form with loan amount, annual rate (%), tenure (months); validation on client **and** server, positive numbers only | Client: HTML5 constraints + jQuery checks in `app/public/app.js`. Server: `validate()` in `app/emi.js`, which returns HTTP 400 with error messages |
| `POST /api/emi` returns EMI, total payment, total interest, pod name and pod IP | `app/server.js`. `servedBy` comes from `HOSTNAME` and `podIp` from `POD_IP` (Downward API) |
| `GET /api/history`: last 10, newest first | `find().sort({createdAt:-1}).limit(10)` |
| `GET /health`: 200 only if MongoDB is reachable | Runs `ping` against MongoDB and returns `200`, or `503` if MongoDB can't be reached |
| Collection `calculations` with `principal, rate, months, emi, servedBy, createdAt` | `insertOne` in `POST /api/emi` |
| Connection string from `MONGO_URL`; nothing hard-coded | The server exits if `MONGO_URL` is missing. No hosts, IPs or passwords in source |
| No postback; AJAX updates only the result panel and history table | `$.ajax` in `app/public/app.js` with `event.preventDefault()` |

### Milestone 02: MongoDB and the web app on Minikube

| Requirement | Implementation |
|---|---|
| Dockerfile, slim/alpine base, `.dockerignore`, non-root user | `app/Dockerfile` (`node:20-alpine`, `USER node`), `app/.dockerignore` |
| Image `emi-web:1.0`, loaded with `minikube image load`, `imagePullPolicy: IfNotPresent` | See bring-up step 2; `k8s/05-web-deployment.yaml` |
| Headless Service `mongo` (`clusterIP: None`) | `k8s/01-mongo-service.yaml` |
| StatefulSet `mongo`, 3 replicas, `--replSet rs0 --bind_ip_all`, 1 Gi PVC each from `standard` | `k8s/02-mongo-statefulset.yaml` (`volumeClaimTemplates` named `data`) |
| Job `mongo-init` runs `rs.initiate()` with the three members | `k8s/03-mongo-init-job.yaml` (waits for all three members, is idempotent, then prints `rs.status()`) |
| Connection string in a ConfigMap, injected as `MONGO_URL` | `k8s/04-configmap.yaml` (no credentials, so a ConfigMap rather than a Secret) |
| Deployment `emi-web`, 3 replicas, readiness + liveness on `/health`, requests 100m/128Mi, limits 250m/256Mi | `k8s/05-web-deployment.yaml` |
| ClusterIP Service `emi-web` | `k8s/06-web-service.yaml` |
| Port-forward check | `kubectl port-forward svc/emi-web 8080:80 -n emi` |
| Persistence test (delete `mongo-1`: same name, same PVC, no data lost) | `scripts/persistence_test.sh` |

### Milestone 03: Ingress, load balancing and self-healing

| Requirement | Implementation |
|---|---|
| Ingress, `ingressClassName: nginx`, host `emi.local`, `/` routed to `emi-web` | `k8s/07-ingress.yaml` |
| 30 requests, count `servedBy` per pod (3 and 5 replicas) | `scripts/load_distribution.sh 30 <file>` |
| New pods get traffic only after they are Ready | readinessProbe on `/health`; `scale_watch.txt` compared with `distribution_5_replicas_during_scaleup.txt` |
| Self-healing: web pod and MongoDB PRIMARY deletion | `scripts/request_loop.sh` + `kubectl get pods -w`; `scripts/mongo_primary.sh` before/after |
| Rolling update to `1.1` with zero failed requests, then `rollout undo` | `maxSurge: 1`, `maxUnavailable: 0`, readiness probe, `preStop: sleep 5`; `scripts/request_loop.sh` logs `failed=0` |

### Milestone 04: Load testing, profiling and autoscaling

| Requirement | Implementation |
|---|---|
| Load generator against `http://emi.local/` only | `httperf` (`scripts/httperf_run.sh`) |
| Each request is `POST /api/emi` with random valid inputs (so it writes to MongoDB) | `scripts/gen_wsesslog.py` generates the httperf `--wsesslog` file |
| 15 fixed-replica runs: 1/2/3 replicas × 10/25/50/100/200 req/s × 60 s; avg response time + errors | `scripts/run_fixed_experiments.sh` writes `results/m04/fixed/summary.csv` |
| Profiling: `kubectl top pods` every 15 s, host CPU every 1 s, CSV with timestamps | `scripts/monitor.py` writes `pods.csv` and `host_cpu.csv` |
| HPA `autoscaling/v2`, min 1, max 5, 50% CPU | `k8s/hpa/emi-web-hpa.yaml` |
| 10-minute test: 2 min at 10 req/s, 5 min at 100 req/s, 3 min at 10 req/s; replicas every 15 s | `scripts/run_autoscale_test.sh` writes `results/m04/autoscale/hpa.csv` |
| Raw outputs in `results/` | `results/m04/**` |
| Graphs 1–3 | `scripts/make_graphs.py` writes `results/graphs/*.png` |

---

## Repository layout

```text
app/                 Web application
  server.js          Express server: /api/emi, /api/history, /health, /api/version
  emi.js             EMI formula and server-side validation
  public/            index.html (Bootstrap 5), app.js (jQuery AJAX), style.css
  test/              Unit tests for the formula and validation (npm test)
  Dockerfile         node:20-alpine, runs as the non-root "node" user
  .dockerignore
k8s/                 Manifests applied with: kubectl apply -f k8s/
  00-namespace.yaml          Namespace emi
  01-mongo-service.yaml      Headless Service mongo (clusterIP: None)
  02-mongo-statefulset.yaml  StatefulSet mongo, 3 replicas, 1 Gi PVC each
  03-mongo-init-job.yaml     Job mongo-init: rs.initiate() for rs0
  04-configmap.yaml          ConfigMap emi-config: MONGO_URL
  05-web-deployment.yaml     Deployment emi-web, 3 replicas, probes, resources
  06-web-service.yaml        Service emi-web (ClusterIP 80 -> 3000)
  07-ingress.yaml            Ingress emi.local -> emi-web:80
  hpa/emi-web-hpa.yaml       HPA (applied only for the autoscaling test)
scripts/             Experiment, profiling, graph and report scripts (table below)
results/             Raw outputs of every milestone, graphs and screenshots
docs/                Step-by-step guides per milestone (macOS)
report/              Generated report (scripts/build_report.py)
README.md
```

Files are numbered so that `kubectl apply -f k8s/` creates them in a working order: namespace first, then MongoDB, then the web tier. The HPA lives in `k8s/hpa/` on purpose. Milestones 02–03 and the fixed-replica runs of Milestone 04 scale `emi-web` by hand, and an active HPA would override that.

---

## API

| Method | Path | Request | Response |
|---|---|---|---|
| `POST` | `/api/emi` | `principal`, `rate` (annual %), `months` as JSON or form data | `200` with `{principal, rate, months, emi, totalPayment, totalInterest, servedBy, podIp, version}`; `400` with `{errors: [...]}` for invalid input; `503` if MongoDB is unavailable |
| `GET` | `/api/history` | – | Last 10 calculations, newest first |
| `GET` | `/health` | – | `200 {"status":"ok"}` when MongoDB answers a ping, otherwise `503` |
| `GET` | `/api/version` | – | `{version, servedBy, podIp}` (shown in the page footer) |

Example for the Milestone 01 screenshot: `P = 500000`, `rate = 12`, `n = 24` gives **EMI = 23,536.74**, total payment 564,881.67 and total interest 64,881.67.

```bash
curl -s -X POST http://emi.local/api/emi -H 'Content-Type: application/json' \
  -d '{"principal":500000,"rate":12,"months":24}'
```

Environment variables: `MONGO_URL` (required), `PORT` (default `3000`), `APP_VERSION` (set at build time, default `1.0`), `POD_IP` (injected by Kubernetes).

---

## Prerequisites

| Tool | macOS (Homebrew) | Purpose |
|---|---|---|
| Docker Desktop | [docker.com](https://www.docker.com/products/docker-desktop/) (give it at least 6 GB of memory) | Container runtime and Minikube driver |
| Minikube, kubectl | `brew install minikube kubectl` | Cluster and CLI |
| Node.js 20 | `brew install node` | Running the app locally (Milestone 01) |
| httperf | `brew install httperf` | Load generator (Milestone 04) |
| Python 3 + matplotlib, psutil | `python3 -m venv .venv && source .venv/bin/activate && pip install matplotlib psutil` | Profiling, graphs, report |

On Linux, install the same tools with your package manager (`apt install httperf`, etc.).

---

## Run locally (Milestone 01)

```bash
docker run -d --name emi-mongo -p 27017:27017 mongo:7.0
cd app
npm install
npm test                                              # formula + validation tests
MONGO_URL="mongodb://localhost:27017/emidb" node server.js
# open http://localhost:3000
```

---

## Bring up the whole system on a fresh Minikube cluster

Run these commands from the repository root.

```bash
# 1. Start a fresh cluster and enable the Ingress controller and metrics-server
minikube start -p emi --driver=docker --cpus=4 --memory=6144   # 8 GB Mac: --cpus=2 --memory=4096
minikube profile emi
minikube addons enable ingress
minikube addons enable metrics-server

# 2. Build the application image and load it into the cluster
docker build -t emi-web:1.0 app/
minikube image load emi-web:1.0
#    (alternative: eval $(minikube docker-env) && docker build -t emi-web:1.0 app/)

# 3. Create everything: namespace, MongoDB headless Service + StatefulSet,
#    replica-set init Job, ConfigMap, web Deployment + Service, Ingress
kubectl apply -f k8s/

# 4. Wait until it is ready
kubectl wait --for=condition=complete job/mongo-init -n emi --timeout=300s
kubectl rollout status statefulset/mongo -n emi
kubectl rollout status deployment/emi-web -n emi
kubectl get all,pvc,configmap -n emi -o wide
```

Expected result: `mongo-0/1/2` and three `emi-web-*` pods are `Running` and `1/1` Ready, `job/mongo-init` is `Complete`, and three PVCs `data-mongo-0/1/2` are `Bound` (1Gi, `standard`).

Check the replica set (one PRIMARY, two SECONDARY):

```bash
kubectl logs job/mongo-init -n emi
kubectl exec -n emi mongo-0 -- mongosh --quiet --eval \
  'rs.status().members.forEach(m => print(m.name + "  " + m.stateStr))'
```

### Open the app

Through a port-forward (Milestone 02):

```bash
kubectl port-forward svc/emi-web 8080:80 -n emi      # http://localhost:8080
```

Through the Ingress (Milestone 03):

```bash
# macOS / Windows with the Docker driver: map emi.local to 127.0.0.1 and keep a tunnel open
echo "127.0.0.1 emi.local" | sudo tee -a /etc/hosts
minikube tunnel -p emi                                # separate terminal; leave it running

# Linux instead:
echo "$(minikube ip) emi.local" | sudo tee -a /etc/hosts

curl http://emi.local/health
# browser: http://emi.local
```

---

## Reproducing the experiments

All scripts write into `results/`. Run them from the repository root, with the tunnel open and the Python venv active.

| Script | Purpose | Output |
|---|---|---|
| `scripts/persistence_test.sh` | Deletes `mongo-1`; shows same name, same PVC, same document count | `results/m02/persistence_test.txt` |
| `scripts/mongo_primary.sh` | Replica-set member states and current PRIMARY | stdout |
| `scripts/count_documents.sh` | Number of documents in `emidb.calculations` | stdout |
| `scripts/load_distribution.sh N FILE` | N `POST /api/emi` requests through the Ingress; requests per pod | `results/m03/distribution_*.txt` |
| `scripts/request_loop.sh FILE` | One request every 0.2 s until Ctrl+C; `SUMMARY: total ok failed` | `results/m03/*_loop.log` |
| `scripts/preflight.sh` | Checks httperf, Python modules, metrics-server and the Ingress before a load test | stdout |
| `scripts/httperf_run.sh RATE SECS FILE` | One httperf run with random POST bodies | `httperf.txt` |
| `scripts/gen_wsesslog.py` | Generates the httperf session file with random valid loan inputs | temp file |
| `scripts/monitor.py` | `kubectl top pods` every 15 s, host CPU every 1 s, HPA every 15 s (`--hpa`) | `pods.csv`, `host_cpu.csv`, `hpa.csv` |
| `scripts/run_fixed_experiments.sh` | 15 runs: 1/2/3 replicas × 10/25/50/100/200 req/s × 60 s | `results/m04/fixed/` |
| `scripts/run_autoscale_test.sh` | HPA test: 2 min × 10, 5 min × 100, 3 min × 10 req/s | `results/m04/autoscale/` |
| `scripts/make_graphs.py` | Graphs 1–3 | `results/graphs/` |
| `scripts/build_report.py` | Builds the PDF/HTML report from everything in `results/` | `report/` |

### Milestone 02: persistence test

```bash
scripts/persistence_test.sh results/m02/persistence_test.txt
```

### Milestone 03: load balancing, scaling, self-healing, rolling update

```bash
scripts/load_distribution.sh 30 results/m03/distribution_3_replicas.txt
kubectl scale deployment emi-web --replicas=5 -n emi
scripts/load_distribution.sh 30 results/m03/distribution_5_replicas.txt

# Self-healing (keep a request loop running in another terminal)
scripts/request_loop.sh results/m03/selfheal_web_loop.log
kubectl delete pod -n emi "$(kubectl get pods -n emi -l app=emi-web -o jsonpath='{.items[0].metadata.name}')"
scripts/mongo_primary.sh                      # find the PRIMARY, then delete that pod
kubectl delete pod -n emi mongo-0             # use the PRIMARY reported above

# Rolling update to 1.1 and rollback
docker build --build-arg APP_VERSION=1.1 -t emi-web:1.1 app/
minikube image load emi-web:1.1
kubectl set image deployment/emi-web web=emi-web:1.1 -n emi
kubectl rollout status deployment/emi-web -n emi
kubectl rollout history deployment/emi-web -n emi
kubectl rollout undo deployment/emi-web -n emi
```

### Milestone 04: load tests, profiling, autoscaling, graphs

```bash
ulimit -n 4096
caffeinate -i scripts/run_fixed_experiments.sh 2>&1 | tee results/m04/fixed_runs_console.log
caffeinate -i scripts/run_autoscale_test.sh   2>&1 | tee results/m04/autoscale_console.log
python3 scripts/make_graphs.py
```

(`caffeinate -i` keeps a Mac awake. On Linux, leave it out.)

The fixed-replica script removes any HPA first, so the replica count stays fixed. To run a single combination, use `REPLICAS="3" RATES="100" scripts/run_fixed_experiments.sh`. httperf uses session mode: 10 requests per persistent connection, with sessions started at `rate/10` per second. The request rate stays the same, but `minikube tunnel` on macOS has to accept 10× fewer new connections.

### Report

```bash
python3 scripts/build_report.py --name "Your Name" --roll "Roll No"
```

This writes `report/Assignment4_Report.html` with every deliverable filled in from `results/`. If Google Chrome is installed, it also writes `report/Assignment4_Report.pdf`. Otherwise, open the HTML in Safari and use **File > Export as PDF**. The script also lists any deliverable that is still missing.

---

## Results

| Folder | Contents |
|---|---|
| `results/environment.txt` | Machine and tool versions |
| `results/m01/` | Local API test, stored documents, `/health` without MongoDB |
| `results/m02/` | `image.txt`, `get_all.txt`, `rs_status.txt`, `mongo_init_job.log`, `persistence_test.txt` |
| `results/m03/` | Requests-per-pod tables, scale-up watch, self-healing watches and loops, `rollout.txt`, rolling-update loop logs |
| `results/m04/fixed/` | `summary.csv` + one folder per run (`r<replicas>_rate<rps>/httperf.txt`, `pods.csv`, `host_cpu.csv`) |
| `results/m04/autoscale/` | `hpa.csv`, `phases.csv`, `pods.csv`, `host_cpu.csv`, `httperf_*.txt`, `hpa_describe.txt` |
| `results/graphs/` | `graph1_response_time_vs_rate.png`, `graph2_pod_cpu_100rps_3replicas.png`, `graph3_autoscaling.png` |
| `results/screenshots/` | Browser screenshots used in the report |

CPU utilization in the graphs is a percentage of the pod's CPU **request** (100m), which is the same definition the HPA uses. A pod at its 250m limit therefore shows 250%.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `http://emi.local` does not open on macOS | `minikube tunnel -p emi` must be running in its own terminal, and `/etc/hosts` must contain `127.0.0.1 emi.local` |
| Each request to `emi.local` takes about 5 s on macOS | Bonjour resolves `.local` names first. Also add `::1 emi.local` to `/etc/hosts`. The scripts resolve the name once |
| `emi-web` pods are `0/1` Ready | `/health` fails until the replica set has a PRIMARY. Check `kubectl logs job/mongo-init -n emi` |
| `kubectl top` reports `metrics not available` | `minikube addons enable metrics-server`, then wait 1–2 minutes |
| `ErrImageNeverPull` / `ImagePullBackOff` for `emi-web` | `minikube image load emi-web:1.0` (the image must exist inside Minikube) |
| httperf stalls or crashes at 200 req/s on macOS | `ulimit -n 4096`; the fixed-run script retries a stalled run up to 3 times |

---

## Tear down

```bash
kubectl delete -f k8s/hpa/ --ignore-not-found
kubectl delete -f k8s/
kubectl delete pvc -n emi --all        # PVCs created by volumeClaimTemplates are kept otherwise
minikube delete -p emi
```

---

## References

1. Minikube: Get started. https://minikube.sigs.k8s.io/docs/start/
2. Minikube: Pushing images into the cluster. https://minikube.sigs.k8s.io/docs/handbook/pushing/
3. Kubernetes: StatefulSets. https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/
4. Kubernetes: Horizontal Pod Autoscaling. https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/
5. MongoDB: Deploy a self-managed replica set. https://www.mongodb.com/docs/manual/tutorial/deploy-replica-set/
6. httperf. https://github.com/httperf/httperf
