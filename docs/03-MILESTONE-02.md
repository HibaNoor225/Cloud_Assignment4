# Milestone 02 — Deploy MongoDB and the Web App on Minikube

All commands: **Mac Terminal**, inside `~/assignment4`. Docker Desktop must be running.

## What the PDF asks

| # | Task | File in this repo |
|---|---|---|
| 1 | **Dockerfile**: official slim/alpine base, `.dockerignore`, run as **non-root**. Build `emi-web:1.0`, load into Minikube, `imagePullPolicy: IfNotPresent` | `app/Dockerfile`, `app/.dockerignore` |
| 2 | **Headless Service `mongo`** (`clusterIP: None`) + **StatefulSet `mongo`**: 3 replicas, `--replSet rs0 --bind_ip_all`, `volumeClaimTemplates` 1Gi each from the `standard` StorageClass | `k8s/01-mongo-service.yaml`, `k8s/02-mongo-statefulset.yaml` |
| 3 | **Job `mongo-init`**: `mongosh` against `mongo-0.mongo`, `rs.initiate()` with 3 members; confirm 1 PRIMARY + 2 SECONDARY | `k8s/03-mongo-init-job.yaml` |
| 4 | **ConfigMap** with the replica-set connection string, injected as `MONGO_URL` | `k8s/04-configmap.yaml` |
| 5 | **Deployment `emi-web`**: 3 replicas, readiness + liveness on `/health`, requests 100m/128Mi, limits 250m/256Mi | `k8s/05-web-deployment.yaml` |
| 6 | **ClusterIP Service `emi-web`** | `k8s/06-web-service.yaml` |
| 7 | **Verify** with `kubectl port-forward svc/emi-web 8080:80 -n emi` | commands below |
| 8 | **Persistence test**: delete `mongo-1`, show same name, same PVC, no data lost | `scripts/persistence_test.sh` |

## Deliverables for Milestone 02

| Deliverable | Saved as |
|---|---|
| Dockerfile, .dockerignore, all YAML manifests | in the repo (`app/`, `k8s/`); paste them in the report appendix |
| `kubectl get all,pvc,configmap -n emi -o wide` with all pods Running and Ready | `results/m02/get_all.txt` |
| `rs.status()` trimmed to member names and states | `results/m02/rs_status.txt` |
| `kubectl logs job/mongo-init -n emi` | `results/m02/mongo_init_job.log` |
| Screenshot of the app through the port-forward, with the history table | `results/screenshots/m02_portforward_app.png` |
| Persistence test proof (pod age, PVC name, documents before and after) | `results/m02/persistence_test.txt` |

---

## Step 2.1 — Create a dedicated Minikube cluster for Assignment 4

```bash
cd ~/assignment4
minikube profile list
```

- **What:** lists existing Minikube clusters. On a fresh Mac it says there are none.

Start a new cluster called `emi`, using the flags for your Mac's RAM from [01-SETUP.md](01-SETUP.md) (M0.2):

```bash
minikube start -p emi --driver=docker --cpus=4 --memory=6144
minikube profile emi
```

- **What:** `-p emi` creates a cluster named `emi` inside Docker Desktop. `minikube profile emi` makes it the default, so later `minikube ...` commands act on it.
- The first start downloads Kubernetes images, which takes a few minutes.
- If it errors with "Docker Desktop has only X MB memory", raise Docker's memory in Settings > Resources, or lower `--memory`.

Check that `kubectl` talks to it:

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

What the Dockerfile does:

- `FROM node:20-alpine`: official Node image on Alpine Linux (small). Satisfies "official slim or alpine base image".
- `ARG/ENV APP_VERSION`: version shown in the page footer (used for the rolling update in Milestone 03).
- `COPY package.json package-lock.json` + `npm ci --omit=dev`: installs only production dependencies, in a cached layer.
- `COPY --chown=node:node . .`: copies the code, owned by the unprivileged `node` user.
- `USER node`: the container runs as **non-root**.
- `.dockerignore` keeps `node_modules`, tests and `.git` out of the image.

Build and check:

```bash
docker build -t emi-web:1.0 app/
docker images emi-web
docker run --rm emi-web:1.0 whoami          # prints: node  (proves non-root)
```

Load it into the Minikube node (Minikube has its own image store, separate from Docker Desktop's):

```bash
minikube image load emi-web:1.0
minikube image ls | grep emi-web            # docker.io/library/emi-web:1.0
```

- **Why:** with `imagePullPolicy: IfNotPresent`, Kubernetes uses this loaded image instead of trying to download `emi-web` from Docker Hub (where it doesn't exist).

```bash
mkdir -p results/m02
{ docker images emi-web; echo; docker run --rm emi-web:1.0 whoami; echo; minikube image ls | grep emi-web; } | tee results/m02/image.txt
```

## Step 2.3 — Namespace and MongoDB, one file at a time

We apply the files one by one so you see what each creates. (`kubectl apply -f k8s/` does it all at once, as the README shows.)

```bash
kubectl apply -f k8s/00-namespace.yaml
kubectl get ns emi
```

- **Namespace `emi`**: a separate area of the cluster for this assignment. Every other object goes inside it.

```bash
cat k8s/01-mongo-service.yaml
kubectl apply -f k8s/01-mongo-service.yaml
kubectl get svc -n emi
```

- **Headless Service** (`clusterIP: None`): no single load-balanced IP. Each MongoDB pod gets its own DNS name (`mongo-0.mongo`, `mongo-1.mongo`, `mongo-2.mongo`). A replica set needs this, because members talk to *specific* members.

```bash
cat k8s/02-mongo-statefulset.yaml
kubectl apply -f k8s/02-mongo-statefulset.yaml
kubectl get pods -n emi -w
```

- **StatefulSet**: like a Deployment, but pods get **stable names** (`mongo-0/1/2`), start in order, and each keeps **its own disk**.
- **volumeClaimTemplates**: one PVC per pod (`data-mongo-0`, `data-mongo-1`, `data-mongo-2`), 1Gi each, from the `standard` StorageClass.
- **args `--replSet rs0 --bind_ip_all`**: each mongod joins replica set `rs0` and accepts connections from other pods.
- `-w` = watch. Wait until all 3 show `1/1 Running` (the first pull of `mongo:7.0` takes a minute or two), then press **Ctrl + C**.

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
- Ours waits until all 3 members answer, runs `rs.initiate()` with `mongo-0.mongo:27017`, `mongo-1.mongo:27017`, `mongo-2.mongo:27017`, waits for a PRIMARY to be elected, and prints each member's state.
- **Why a Job:** the three mongod processes run but don't know about each other until `rs.initiate()` is called once.

Save the deliverables:

```bash
kubectl logs job/mongo-init -n emi | tee results/m02/mongo_init_job.log
scripts/mongo_primary.sh | tee results/m02/rs_status.txt
```

Expected `rs_status.txt`:

```text
mongo-0.mongo:27017  PRIMARY
mongo-1.mongo:27017  SECONDARY
mongo-2.mongo:27017  SECONDARY

PRIMARY pod: mongo-0
```

(Which pod is PRIMARY may differ; what matters is 1 PRIMARY + 2 SECONDARY.)

The raw `rs.status()` command, if you want to show it too:

```bash
kubectl exec -n emi mongo-0 -- mongosh --quiet --eval 'rs.status().members.map(m => ({name: m.name, state: m.stateStr}))' | tee -a results/m02/rs_status.txt
```

## Step 2.5 — ConfigMap, web Deployment, web Service

```bash
cat k8s/04-configmap.yaml
kubectl apply -f k8s/04-configmap.yaml
```

- **ConfigMap `emi-config`** holds `MONGO_URL = mongodb://mongo-0.mongo:27017,mongo-1.mongo:27017,mongo-2.mongo:27017/emidb?replicaSet=rs0`.
- A ConfigMap (not a Secret) because the string has no password. Listing all three members plus `replicaSet=rs0` lets the MongoDB driver find whichever member is PRIMARY.

```bash
cat k8s/05-web-deployment.yaml
kubectl apply -f k8s/05-web-deployment.yaml
kubectl get pods -n emi -w          # wait for 3 emi-web pods 1/1 Running, then Ctrl + C
```

What's in the Deployment:

- `replicas: 3`, `image: emi-web:1.0`, `imagePullPolicy: IfNotPresent`.
- `MONGO_URL` comes from the ConfigMap (`configMapKeyRef`); `POD_IP` from the pod's own IP (downward API), so `/api/emi` can report it.
- **readinessProbe** on `/health`: a pod only gets traffic once it can reach MongoDB.
- **livenessProbe** on `/health`: a pod that stays unhealthy is restarted.
- **resources**: requests `100m` CPU / `128Mi`, limits `250m` / `256Mi`. The HPA in Milestone 04 measures "CPU %" relative to the 100m request, so the request is mandatory.
- `maxUnavailable: 0`, `maxSurge: 1`, `preStop: sleep 5`: zero-downtime rolling updates (Milestone 03).

```bash
cat k8s/06-web-service.yaml
kubectl apply -f k8s/06-web-service.yaml
kubectl get svc,endpoints -n emi
```

- **ClusterIP Service `emi-web`**: one stable internal address (port 80) forwarding to port 3000 of every **Ready** `emi-web` pod. The `endpoints` line lists the 3 pod IPs.

## Step 2.6 — Main status output (deliverable)

```bash
kubectl get all,pvc,configmap -n emi -o wide | tee results/m02/get_all.txt
```

Every pod must show `READY 1/1` and `STATUS Running`. The `mongo-init-xxxxx` pod shows `Completed`, which is correct for a Job. You can also take a Terminal screenshot of this (**Cmd + Shift + 4**, **Space**, click the Terminal window).

## Step 2.7 — Open the app through port-forward (deliverable screenshot)

**Terminal window 1:**

```bash
kubectl port-forward svc/emi-web 8080:80 -n emi
```

- **What:** opens port 8080 on your Mac and forwards it into the `emi-web` Service. Leave it running.

In the browser, open **http://localhost:8080**.

1. Make 3–4 calculations, including 500000 / 12 / 24.
2. The history table fills up. "Served by pod" now shows a **Kubernetes pod name** like `emi-web-6d9f...`, not your Mac's name.
3. Screenshot (**Cmd + Shift + 4**, **Space**, click the browser) and move it:

```bash
mv ~/Desktop/Screenshot*.png ~/assignment4/results/screenshots/m02_portforward_app.png
```

> `kubectl port-forward` connects to **one** pod behind the Service, so all requests here show the same pod name. That's expected. Load balancing across pods is Milestone 03 (Ingress).

Stop the port-forward with **Ctrl + C** in window 1.

Confirm the calculations are stored in the replica set:

```bash
scripts/count_documents.sh
```

## Step 2.8 — Persistence test (deliverable)

```bash
cat scripts/persistence_test.sh
scripts/persistence_test.sh results/m02/persistence_test.txt
```

What the script does, and what to point out in the report:

1. **Before:** pod list (note `mongo-1`'s AGE), PVC list, `mongo-1`'s UID and PVC name (`data-mongo-1`), number of documents (e.g. `5`).
2. `kubectl delete pod mongo-1`
3. Waits until `mongo-1` is Ready again.
4. **After:** `mongo-1` is back with the **same name** and a **young AGE** (seconds).
5. **After:** same PVC `data-mongo-1`, still `Bound`; **new pod UID, same PVC**.
6. **After:** same document count, so no data was lost.

- **Why it works:** the StatefulSet recreates the pod with the same identity and re-attaches the same PersistentVolumeClaim, so MongoDB's data files survive.

## Step 2.9 — Commit

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
- [ ] `results/screenshots/m02_portforward_app.png` with the history table
- [ ] `results/m02/persistence_test.txt` shows same name, same PVC, same document count

### If you shut down the Mac between milestones

Start Docker Desktop, then:

```bash
minikube start -p emi
kubectl get pods -n emi       # everything comes back; wait until all are Running
```

Next: [04-MILESTONE-03.md](04-MILESTONE-03.md)
