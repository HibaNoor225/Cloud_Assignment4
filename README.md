# Cloud Computing Assignment 4 - Loan EMI Calculator on Kubernetes

D

This project is a Loan EMI calculator that saves every calculation in MongoDB. It is deployed on a single-node Minikube cluster. The web app runs as a Deployment behind a Service and an NGINX Ingress, MongoDB runs as a 3-member replica set in a StatefulSet, and a Horizontal Pod Autoscaler scales the web pods under load.

I did everything on a MacBook (Apple Silicon) with Docker Desktop and Minikube using the Docker driver.

## Folder structure

```
app/       Node.js/Express server, frontend (HTML, Bootstrap, jQuery), Dockerfile
k8s/       Kubernetes YAML files (applied with kubectl apply -f k8s/)
k8s/hpa/   HPA file, applied separately in Milestone 04
scripts/   Scripts for testing, load tests, monitoring, graphs and the report
results/   Outputs, screenshots and graphs from all milestones
docs/      My step-by-step notes for each milestone
```

## Tools needed

- Docker Desktop
- Minikube and kubectl
- Node.js 20 (only to run the app locally)
- httperf (load testing)
- Python 3 with matplotlib and psutil (monitoring and graphs)

On macOS:

```bash
brew install minikube kubectl node httperf
python3 -m venv .venv
source .venv/bin/activate
pip install matplotlib psutil
```

## Running the whole system on a fresh Minikube cluster

Run these from the root of the repo:

```bash
# start the cluster and enable ingress + metrics-server
minikube start -p emi --driver=docker --cpus=4 --memory=6144
minikube profile emi
minikube addons enable ingress
minikube addons enable metrics-server

# build the app image and load it into minikube
docker build -t emi-web:1.0 app/
minikube image load emi-web:1.0

# create everything
kubectl apply -f k8s/

# wait for it
kubectl wait --for=condition=complete job/mongo-init -n emi --timeout=300s
kubectl rollout status deployment/emi-web -n emi
kubectl get all,pvc,configmap -n emi -o wide
```

The files in `k8s/` are numbered (00 to 07) so they are created in the right order: namespace, MongoDB, ConfigMap, web app, Ingress.

To open the app through the Ingress on macOS, keep `minikube tunnel` running in a separate terminal and add `emi.local` to the hosts file:

```bash
echo "127.0.0.1 emi.local" | sudo tee -a /etc/hosts
minikube tunnel -p emi
```

Then open http://emi.local in the browser. On Linux, use `minikube ip` instead of 127.0.0.1, and the tunnel is not needed.

---

## Milestone 01 - EMI calculator with MongoDB

The backend is Node.js with Express (`app/server.js`). The frontend is a single page made with HTML, Bootstrap 5 and jQuery (`app/public/`).

The EMI is calculated on the server (`app/emi.js`) with:

```
EMI = P * r * (1 + r)^n / ((1 + r)^n - 1)
r = annual rate / 12 / 100
```

The form has three fields: loan amount, annual interest rate and tenure in months. They are checked in the browser (required, positive values) and again on the server. If a value is missing, zero or negative, the server returns HTTP 400 with an error message.

The form is submitted with jQuery AJAX, so the page never reloads. Only the result box and the history table are updated.

API endpoints:

- `POST /api/emi` - takes principal, rate and months. Returns the EMI, total payment, total interest, the pod name (from the `HOSTNAME` env variable) and the pod IP. It also saves the calculation in MongoDB.
- `GET /api/history` - last 10 calculations, newest first.
- `GET /health` - returns 200 only if MongoDB can be reached, otherwise 503. Kubernetes uses it for the readiness probe.
- `GET /api/version` - app version, shown in the footer (used in Milestone 03).

Each calculation is saved in the `calculations` collection with `principal`, `rate`, `months`, `emi`, `servedBy` and `createdAt`.

The MongoDB connection string comes only from the `MONGO_URL` environment variable. There are no hostnames or passwords in the code.

To run it locally with a MongoDB container:

```bash
docker run -d --name emi-mongo -p 27017:27017 mongo:7.0
cd app
npm install
npm test
MONGO_URL="mongodb://localhost:27017/emidb" node server.js
```

Then open http://localhost:3000. For P = 500000, rate = 12% and n = 24 the EMI is 23,536.74.

Screenshot: `results/screenshots/m01_ui_500000_12_24.png`

---

## Milestone 02 - Deploying MongoDB and the app on Minikube

**Docker image.** `app/Dockerfile` uses `node:20-alpine` and installs only the production dependencies. The app runs as the `node` user, not root. `app/.dockerignore` keeps `node_modules`, tests and git files out of the image. I built it as `emi-web:1.0` and loaded it with `minikube image load emi-web:1.0`. The Deployment uses `imagePullPolicy: IfNotPresent`, so Kubernetes uses the loaded image and doesn't try to download it.

**MongoDB.**
- `k8s/01-mongo-service.yaml` - headless Service `mongo` (`clusterIP: None`). It gives each pod a fixed DNS name like `mongo-0.mongo`.
- `k8s/02-mongo-statefulset.yaml` - StatefulSet `mongo` with 3 replicas of `mongo:7.0`, started with `--replSet rs0 --bind_ip_all`. `volumeClaimTemplates` gives each pod its own 1Gi PVC (`data-mongo-0`, `data-mongo-1`, `data-mongo-2`) from the `standard` storage class.
- `k8s/03-mongo-init-job.yaml` - Job `mongo-init`. It waits until all three pods are up, then runs `rs.initiate()` on `mongo-0.mongo` with the three members and prints `rs.status()`. The result is one PRIMARY and two SECONDARY members.

**Config.** `k8s/04-configmap.yaml` stores the connection string:

```
mongodb://mongo-0.mongo:27017,mongo-1.mongo:27017,mongo-2.mongo:27017/emidb?replicaSet=rs0
```

It is passed to the web pods as `MONGO_URL`. I used a ConfigMap because there is no password in it.

**Web app.** `k8s/05-web-deployment.yaml` is the Deployment `emi-web` with 3 replicas. Each pod has:
- readiness and liveness probes on `/health`
- requests of 100m CPU / 128Mi memory and limits of 250m CPU / 256Mi memory

`k8s/06-web-service.yaml` is the ClusterIP Service `emi-web` (port 80 to container port 3000).

**Checking it.**

```bash
kubectl get all,pvc,configmap -n emi -o wide
kubectl logs job/mongo-init -n emi
kubectl port-forward svc/emi-web 8080:80 -n emi    # open http://localhost:8080
```

**Persistence test.** `scripts/persistence_test.sh` deletes `mongo-1`. The StatefulSet creates it again with the same name and attaches the same PVC (`data-mongo-1`). The document count is the same before and after, so no data was lost.

```bash
scripts/persistence_test.sh results/m02/persistence_test.txt
```

Outputs are in `results/m02/`.

---

## Milestone 03 - Ingress, load balancing and self-healing

**Ingress.** `k8s/07-ingress.yaml` uses `ingressClassName: nginx` and sends host `emi.local`, path `/`, to the `emi-web` Service. On macOS I used `minikube tunnel` with `127.0.0.1 emi.local` in `/etc/hosts`.

**Load distribution.** `scripts/load_distribution.sh` sends 30 POST requests through the Ingress and counts how many each pod served (from `servedBy`). I ran it with 3 replicas, then scaled to 5 and ran it again:

```bash
scripts/load_distribution.sh 30 results/m03/distribution_3_replicas.txt
kubectl scale deployment emi-web --replicas=5 -n emi
scripts/load_distribution.sh 30 results/m03/distribution_5_replicas.txt
```

While scaling, I watched the pods with `kubectl get pods -w`. The new pods only started getting requests after they became Ready (1/1), because the Service only sends traffic to pods that pass the readiness probe.

**Self-healing.** I kept `scripts/request_loop.sh` running (one request every 0.2 s) while deleting pods:
- First I deleted one web pod. The Deployment created a new one, and the app kept answering.
- Then I found the MongoDB PRIMARY with `scripts/mongo_primary.sh` and deleted that pod. The other two members elected a new PRIMARY, the deleted pod came back as a SECONDARY, and the app kept saving calculations.

**Rolling update and rollback.** I changed the footer version, built `emi-web:1.1` and updated the Deployment while the request loop was running:

```bash
docker build --build-arg APP_VERSION=1.1 -t emi-web:1.1 app/
minikube image load emi-web:1.1
kubectl set image deployment/emi-web web=emi-web:1.1 -n emi
kubectl rollout status deployment/emi-web -n emi
kubectl rollout history deployment/emi-web -n emi
kubectl rollout undo deployment/emi-web -n emi
```

The Deployment uses `maxSurge: 1` and `maxUnavailable: 0`, so a new pod has to be Ready before an old one is removed. The pods also have a short `preStop` sleep, so traffic stops before a pod shuts down. Because of this, the request loop showed zero failed requests during the update. `kubectl rollout undo` took it back to 1.0.

Outputs are in `results/m03/`.

---

## Milestone 04 - Load testing, profiling and autoscaling

**Workload.** I used httperf, sending traffic only to http://emi.local/. Every request is a `POST /api/emi` with random valid values (`scripts/gen_wsesslog.py`), so every request also writes to MongoDB.

**Fixed replicas.** `scripts/run_fixed_experiments.sh` runs 10, 25, 50, 100 and 200 requests per second, 60 seconds each. It does this with the Deployment fixed at 1, 2 and 3 replicas, so 15 runs in total. The average response time and error count of each run go into `results/m04/fixed/summary.csv`.

On macOS, opening a new connection for every request at high rates was too much for `minikube tunnel`. So httperf sends 10 requests per connection. The request rate stays the same; only the number of new connections is lower.

**Profiling.** `scripts/monitor.py` runs during every test and saves:
- `pods.csv` - `kubectl top pods -n emi` every 15 seconds (CPU and memory per pod)
- `host_cpu.csv` - the Mac's total CPU every second

Both files have a timestamp column.

**Autoscaling.** `k8s/hpa/emi-web-hpa.yaml` is an `autoscaling/v2` HPA for `emi-web` with `minReplicas: 1`, `maxReplicas: 5` and a 50% average CPU target. It is kept outside `k8s/` so it doesn't interfere with the manual scaling in the earlier tests. `scripts/run_autoscale_test.sh` applies it and runs a 10-minute test: 2 minutes at 10 req/s, 5 minutes at 100 req/s, then 3 minutes at 10 req/s. It records `kubectl get hpa emi-web -n emi` every 15 seconds in `results/m04/autoscale/hpa.csv`.

```bash
ulimit -n 4096
scripts/run_fixed_experiments.sh 2>&1 | tee results/m04/fixed_runs_console.log
scripts/run_autoscale_test.sh 2>&1 | tee results/m04/autoscale_console.log
python3 scripts/make_graphs.py
```

**Graphs** (in `results/graphs/`):
1. `graph1_response_time_vs_rate.png` - average response time vs request rate for 1, 2 and 3 replicas
2. `graph2_pod_cpu_100rps_3replicas.png` - CPU of each pod during the 100 req/s run with 3 replicas
3. `graph3_autoscaling.png` - request rate, average CPU and number of replicas during the autoscaling test

CPU in the graphs is shown as a percentage of the pod's CPU request (100m), the same way the HPA measures it.

---

## Report

The PDF report is generated from the files in `results/`:

```bash
python3 scripts/build_report.py --name "Hiba Noor" --roll "ROLL NO"
```

It creates `report/Assignment4_Report.pdf` (and an HTML version).

## Cleaning up

```bash
kubectl delete -f k8s/hpa/ --ignore-not-found
kubectl delete -f k8s/
kubectl delete pvc -n emi --all
minikube delete -p emi
```
