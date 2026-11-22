# Milestone 02 — Deploy MongoDB and the Web App on Minikube

## What the PDF asks

| # | Task | File in this repo |
|---|---|---|
| 1 | **Dockerfile**: official slim/alpine base, `.dockerignore`, run as **non-root**. Build `emi-web:1.0`, load into Minikube, `imagePullPolicy: IfNotPresent` | `app/Dockerfile`, `app/.dockerignore` |
| 2 | **Headless Service `mongo`** (`clusterIP: None`) + **StatefulSet `mongo`**, 3 replicas, `--replSet rs0 --bind_ip_all`, `volumeClaimTemplates` 1Gi each from the `standard` StorageClass | `k8s/01-mongo-service.yaml`, `k8s/02-mongo-statefulset.yaml` |
| 3 | **Job `mongo-init`**: `mongosh` against `mongo-0.mongo`, `rs.initiate()` with 3 members; confirm 1 PRIMARY + 2 SECONDARY | `k8s/03-mongo-init-job.yaml` |
| 4 | **ConfigMap** with the replica-set connection string, injected as `MONGO_URL` | `k8s/04-configmap.yaml` |
| 5 | **Deployment `emi-web`**, 3 replicas, readiness + liveness on `/health`, requests 100m/128Mi, limits 250m/256Mi | `k8s/05-web-deployment.yaml` |
| 6 | **ClusterIP Service `emi-web`** | `k8s/06-web-service.yaml` |
| 7 | **Verify** with `kubectl port-forward svc/emi-web 8080:80 -n emi` | (commands below) |
| 8 | **Persistence test**: delete `mongo-1`, show same name, same PVC, no data lost | `scripts/persistence_test.sh` |

All manifests live in `k8s/` and are applied with `kubectl apply -f`.

> **On a Mac:** run every "UBUNTU SERVER" command in Mac Terminal. In Step 2.1 use the `--cpus/--memory` values from the table in [01-SETUP-MAC.md](01-SETUP-MAC.md). In Step 2.7 skip the `ssh -L` tunnel and open **http://localhost:8080** directly while `kubectl port-forward` runs.

## Deliverables for Milestone 02

| Deliverable | Saved as |
|---|---|
| Dockerfile, .dockerignore, all YAML manifests | already in the repo (`app/`, `k8s/`) — paste them in the report appendix |
| `kubectl get all,pvc,configmap -n emi -o wide` with all pods Running and Ready | `results/m02/get_all.txt` |
| `rs.status()` trimmed to member names and states | `results/m02/rs_status.txt` |
| `kubectl logs job/mongo-init -n emi` | `results/m02/mongo_init_job.log` |
| Screenshots of the app through the port-forward, with the history table | `m02_portforward_app.png` (on your PC) |
| Persistence test proof (pod age, PVC name, documents before and after) | `results/m02/persistence_test.txt` |

---

## Step 2.1 — Create a dedicated Minikube cluster for Assignment 4

**Run on: UBUNTU SERVER (inside SSH)**

```bash
cd ~/assignment4
minikube profile list
```

- **What:** lists existing clusters (your Assignment 3 one is probably called `minikube`). We leave it alone.

Start a new cluster called `emi` (use the CPU/RAM numbers from setup step 0.6: about 2 CPUs and 2 GB less than the machine has, minimum 2 CPUs / 4096 MB):

```bash
minikube start -p emi --driver=docker --cpus=4 --memory=6144
minikube profile emi
```

- **What:** `-p emi` creates a separate cluster. `minikube profile emi` makes it the default, so later `minikube ...` commands act on it without `-p`.
- **Why separate:** a fresh, empty cluster means everything you see in it was created by this assignment.
- The first start downloads the Kubernetes images, so it takes a few minutes.

Check that `kubectl` now talks to the new cluster:

```bash
kubectl config current-context        # must print: emi
kubectl get nodes                     # one node, STATUS Ready
kubectl get storageclass              # "standard (default)" must exist
```

Enable the two add-ons needed later (Ingress for Milestone 03, metrics-server for Milestone 04):

```bash
minikube addons enable ingress
minikube addons enable metrics-server
kubectl get pods -n ingress-nginx     # wait until ingress-nginx-controller is 1/1 Running
```

## Step 2.2 — Build the image and load it into Minikube

```bash
cat app/Dockerfile
cat app/.dockerignore
```

What the Dockerfile does, line by line:

- `FROM node:20-alpine`: official Node image on Alpine Linux (small). Required: "official slim or alpine base image".
- `ARG/ENV APP_VERSION`: version shown in the page footer (used for the rolling update in Milestone 03).
- `COPY package.json package-lock.json` + `npm ci --omit=dev`: installs only production dependencies, in a cached layer.
- `COPY --chown=node:node . .`: copies the code, owned by the unprivileged `node` user.
- `USER node`: the container runs as **non-root** (required).
- `.dockerignore` keeps `node_modules`, tests and `.git` out of the image (required).

Build:

```bash
docker build -t emi-web:1.0 app/
docker images emi-web
docker run --rm emi-web:1.0 whoami          # prints: node  (proves non-root)
```

Load it into the Minikube node (Minikube has its own image store, separate from your server's Docker):

```bash
minikube image load emi-web:1.0
minikube image ls | grep emi-web            # docker.io/library/emi-web:1.0
```

- **Why:** the Deployment uses `imagePullPolicy: IfNotPresent`, so Kubernetes uses this loaded image instead of trying to download `emi-web` from Docker Hub (where it doesn't exist).

```bash
mkdir -p results/m02
{ docker images emi-web; echo; docker run --rm emi-web:1.0 whoami; echo; minikube image ls | grep emi-web; } | tee results/m02/image.txt
```

## Step 2.3 — Namespace and MongoDB (one file at a time)

We apply the files one by one so you can see what each one creates. (`kubectl apply -f k8s/` does the same in one go; that's what the README uses.)

```bash
kubectl apply -f k8s/00-namespace.yaml
kubectl get ns emi
```

- **Namespace `emi`**: a separate area of the cluster for this assignment. Every other object goes in it.

```bash
cat k8s/01-mongo-service.yaml
kubectl apply -f k8s/01-mongo-service.yaml
kubectl get svc -n emi
```

- **Headless Service** (`clusterIP: None`): no single load-balanced IP. Each MongoDB pod gets its own DNS name: `mongo-0.mongo`, `mongo-1.mongo`, `mongo-2.mongo`. A replica set needs this, because members talk to *specific* members, not a random one.

```bash
cat k8s/02-mongo-statefulset.yaml
kubectl apply -f k8s/02-mongo-statefulset.yaml
kubectl get pods -n emi -w
```

- **StatefulSet**: like a Deployment, but pods get **stable names** (`mongo-0`, `mongo-1`, `mongo-2`), start in order, and each keeps **its own disk**.
- **volumeClaimTemplates**: creates one PVC per pod (`data-mongo-0`, `data-mongo-1`, `data-mongo-2`), 1Gi each, from the `standard` StorageClass.
- **args `--replSet rs0 --bind_ip_all`**: each mongod joins replica set `rs0` and accepts connections from other pods.
- `-w` = watch. Wait until all 3 show `1/1 Running` (the first pull of `mongo:7.0` takes a minute or two), then press **Ctrl+C**.

```bash
kubectl get pvc -n emi          # 3 PVCs, STATUS Bound, 1Gi, standard
```

## Step 2.4 — Initiate the replica set with the Job

```bash
cat k8s/03-mongo-init-job.yaml
kubectl apply -f k8s/03-mongo-init-job.yaml
kubectl wait --for=condition=complete job/mongo-init -n emi --timeout=300s
kubectl logs job/mongo-init -n emi
```

- **Job**: a pod that runs a task once and then stops (`Completed`).
- Our Job waits until all 3 members answer, runs `rs.initiate()` with `mongo-0.mongo:27017`, `mongo-1.mongo:27017`, `mongo-2.mongo:27017`, waits until a PRIMARY is elected, then prints each member's state.
- **Why a Job:** the three mongod processes run but don't know about each other until `rs.initiate()` is called once.

Save the deliverables:

```bash
kubectl logs job/mongo-init -n emi | tee results/m02/mongo_init_job.log
scripts/mongo_primary.sh | tee results/m02/rs_status.txt
```

Expected (`rs_status.txt`):

```text
mongo-0.mongo:27017  PRIMARY
mongo-1.mongo:27017  SECONDARY
mongo-2.mongo:27017  SECONDARY

PRIMARY pod: mongo-0
```

(Which pod is PRIMARY may differ; what matters is 1 PRIMARY + 2 SECONDARY.)

If you'd rather show the raw command too:

```bash
kubectl exec -n emi mongo-0 -- mongosh --quiet --eval 'rs.status().members.map(m => ({name: m.name, state: m.stateStr}))'
```

## Step 2.5 — ConfigMap, web Deployment, web Service

```bash
cat k8s/04-configmap.yaml
kubectl apply -f k8s/04-configmap.yaml
```

- **ConfigMap `emi-config`** holds `MONGO_URL = mongodb://mongo-0.mongo:27017,mongo-1.mongo:27017,mongo-2.mongo:27017/emidb?replicaSet=rs0`.
- A ConfigMap (not a Secret) because there's no password in it. Listing all three members plus `replicaSet=rs0` lets the driver find whichever member is PRIMARY.

```bash
cat k8s/05-web-deployment.yaml
kubectl apply -f k8s/05-web-deployment.yaml
kubectl get pods -n emi -w          # wait for 3 emi-web pods at 1/1 Running, then Ctrl+C
```

What's in the Deployment:

- `replicas: 3`, `image: emi-web:1.0`, `imagePullPolicy: IfNotPresent`.
- `MONGO_URL` comes from the ConfigMap (`configMapKeyRef`). `POD_IP` comes from the pod's own IP (downward API) so `/api/emi` can report it.
- **readinessProbe** on `/health`: a pod only receives traffic once it can reach MongoDB.
- **livenessProbe** on `/health`: if a pod stays unhealthy for a long time, Kubernetes restarts it.
- **resources**: requests `100m` CPU / `128Mi`, limits `250m` / `256Mi`. The HPA in Milestone 04 calculates "CPU %" relative to the 100m request, so the request is mandatory.
- `maxUnavailable: 0`, `maxSurge: 1` and `preStop: sleep 5`: zero-downtime rolling updates (Milestone 03).

```bash
cat k8s/06-web-service.yaml
kubectl apply -f k8s/06-web-service.yaml
kubectl get svc,endpoints -n emi
```

- **ClusterIP Service `emi-web`**: one stable internal address (port 80) that forwards to port 3000 of every **Ready** `emi-web` pod. The `endpoints` line lists the 3 pod IPs.

## Step 2.6 — Main status output (deliverable)

```bash
kubectl get all,pvc,configmap -n emi -o wide | tee results/m02/get_all.txt
```

Check that every pod shows `READY 1/1` and `STATUS Running` (the `mongo-init` pod shows `Completed`, which is correct for a Job). Take a terminal screenshot of this as well if you like.

## Step 2.7 — Open the app through port-forward (deliverable screenshot)

**Run on: UBUNTU SERVER (SSH window 1)**

```bash
kubectl port-forward svc/emi-web 8080:80 -n emi
```

- **What:** opens port 8080 on the server's localhost and forwards it into the `emi-web` Service. Leave it running.

**Run on: YOUR PC (new terminal)**

```bash
ssh -L 8080:localhost:8080 SERVER_USER@SERVER_IP
```

Browser on your PC: **http://localhost:8080**

1. Make 3–4 calculations (include 500000 / 12 / 24).
2. The history table fills up, and "Served by pod" shows a name like `emi-web-6d9f...`: a **Kubernetes pod** now, not your server's hostname.
3. Screenshot → `m02_portforward_app.png`.

> `kubectl port-forward` picks **one** pod behind the Service, so all requests here show the same pod. That's expected. Real load balancing across pods is Milestone 03 (Ingress).

Stop the port-forward with **Ctrl+C** in SSH window 1 when done.

Confirm the calculations are stored:

```bash
scripts/count_documents.sh
```

## Step 2.8 — Persistence test (deliverable)

```bash
cat scripts/persistence_test.sh
scripts/persistence_test.sh results/m02/persistence_test.txt
```

What the script does and what to point out in the report:

1. **Before:** pod list (note `mongo-1`'s AGE), PVC list, `mongo-1`'s UID and PVC name (`data-mongo-1`), document count (for example `5`).
2. `kubectl delete pod mongo-1`
3. Waits until `mongo-1` is Ready again.
4. **After:** pod list. `mongo-1` exists again with the **same name** and a **young AGE** (seconds).
5. **After:** same PVC `data-mongo-1`, still `Bound`; new pod UID, **same PVC**.
6. **After:** document count is the **same number**, so no data was lost.

- **Why it works:** the StatefulSet recreates the pod with the same identity and re-attaches the same PersistentVolumeClaim, so MongoDB's data files survive the pod.

## Step 2.9 — Commit the results

```bash
git add results/
git commit -m "Milestone 02: deployment outputs, rs.status, persistence test"
git push
```

### Milestone 02 done when
- [ ] `kubectl config current-context` prints `emi`
- [ ] `results/m02/get_all.txt` shows 3 `mongo-*` and 3 `emi-web-*` pods `1/1 Running`, 3 PVCs `Bound`
- [ ] `results/m02/rs_status.txt` shows 1 PRIMARY + 2 SECONDARY
- [ ] `results/m02/mongo_init_job.log` saved
- [ ] Screenshot `m02_portforward_app.png` with history table
- [ ] `results/m02/persistence_test.txt` shows same name, same PVC, same document count

Next: [04-MILESTONE-03.md](04-MILESTONE-03.md)
