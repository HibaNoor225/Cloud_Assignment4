# Milestone 03 — Ingress, Load Balancing and Self-Healing

## What the PDF asks

| # | Task | In short |
|---|---|---|
| 1 | **Ingress** with `ingressClassName: nginx`, host `emi.local`, `/` → Service `emi-web`. Map `emi.local` in the hosts file (`minikube ip` on Linux). Open `http://emi.local` | `k8s/07-ingress.yaml` |
| 2 | **Load distribution**: 30 × `POST /api/emi` through the Ingress, count `servedBy` per pod | `scripts/load_distribution.sh` |
| 3 | **Scaling by hand**: `kubectl scale ... --replicas=5`, repeat 30 requests, show new pods get traffic **only after they are Ready** | watch + script |
| 4 | **Self-healing**: delete a web pod (app keeps answering), then delete the MongoDB **PRIMARY** (new PRIMARY elected, app still saves) | watch + `scripts/request_loop.sh` |
| 5 | **Rolling update + rollback**: change footer, build `emi-web:1.1`, `kubectl set image` with a request loop running (zero failures), then `kubectl rollout undo` | `scripts/request_loop.sh` |

> **On a Mac (important, Step 3.1 is different):** with the Docker driver the Minikube IP isn't reachable from macOS. Instead of the `minikube ip` lines in Step 3.1, run:
>
> ```bash
> echo "127.0.0.1 emi.local" | sudo tee -a /etc/hosts
> ```
>
> Then open a **separate Terminal window**, run `minikube tunnel`, type your Mac password if asked, and **leave that window open** for the rest of Milestones 03 and 04 (it's what connects `127.0.0.1:80` to the Ingress). Skip Step 3.2's hosts-file editing and `ssh -L`: just open **http://emi.local** in your Mac browser. "Windows A/B/C" are simply three Mac Terminal windows (Cmd + N), each starting with `cd ~/assignment4`.

## Deliverables for Milestone 03

| Deliverable | Saved as |
|---|---|
| Ingress manifest + screenshot of the app at `http://emi.local` | `k8s/07-ingress.yaml`, `m03_emi_local.png` |
| Table of requests served per pod, 3 replicas and 5 replicas | `results/m03/distribution_3_replicas.txt`, `results/m03/distribution_5_replicas.txt` |
| `kubectl get pods -n emi -w` during both self-healing tests | `results/m03/selfheal_web_watch.txt`, `results/m03/selfheal_mongo_watch.txt` |
| `kubectl rollout status` + `kubectl rollout history` + request-loop log with zero failures | `results/m03/rollout.txt`, `results/m03/rolling_update_loop.log` |

You'll need **3 SSH windows** for parts of this milestone. They're called **A**, **B** and **C** below; each is a separate PowerShell/Terminal window on your PC running `ssh SERVER_USER@SERVER_IP`, then `cd ~/assignment4`.

A helper used throughout, which prefixes each line of a watch with the time so you can compare events:

```bash
ts() { while IFS= read -r line; do echo "$(date +%T) $line"; done; }
```

Paste it into each SSH window once (it only lasts for that session).

---

## Step 3.1 — Create the Ingress

**Run on: UBUNTU SERVER (window A)**

```bash
cd ~/assignment4
mkdir -p results/m03
cat k8s/07-ingress.yaml
kubectl apply -f k8s/07-ingress.yaml
kubectl get ingress -n emi
```

- **Ingress**: an HTTP routing rule. "Requests for host `emi.local`, path `/`, go to Service `emi-web` port 80."
- The **NGINX Ingress controller** (the add-on enabled in Milestone 02) reads that rule and does the routing. It sends each request directly to one of the Ready pod IPs listed in the Service's endpoints, round-robin.
- Wait until the `ADDRESS` column shows an IP (up to a minute).

Map `emi.local` to the cluster **on the server** (the load tests in Milestone 04 also run here):

```bash
minikube ip                                      # e.g. 192.168.49.2
echo "$(minikube ip) emi.local" | sudo tee -a /etc/hosts
cat /etc/hosts | grep emi.local
curl -s http://emi.local/health
curl -s -X POST http://emi.local/api/emi -H 'Content-Type: application/json' -d '{"principal":500000,"rate":12,"months":24}' | jq
```

- **Why the hosts file:** there's no real DNS for `emi.local`. The hosts file tells the server "emi.local = the Minikube node IP", where the Ingress controller listens on port 80.
- `curl` must return `{"status":"ok"...}` and an EMI result.

## Step 3.2 — Open http://emi.local in your PC's browser (deliverable screenshot)

The Minikube IP (`192.168.49.x`) exists only inside the server, so tunnel to it through SSH.

**Run on: YOUR PC — edit the hosts file once**

- **Windows:** press Start, type `Notepad`, right-click > **Run as administrator**. File > Open > `C:\Windows\System32\drivers\etc\hosts` (choose "All files"). Add a line at the end and save:
  ```text
  127.0.0.1   emi.local
  ```
- **Mac/Linux:** `sudo nano /etc/hosts`, add `127.0.0.1   emi.local`, save (Ctrl+O, Enter, Ctrl+X).

**Run on: YOUR PC — open the tunnel** (replace `192.168.49.2` with the output of `minikube ip`)

```bash
ssh -L 80:192.168.49.2:80 SERVER_USER@SERVER_IP
```

Browser: **http://emi.local**

If the tunnel command fails with "Permission denied / cannot listen to port 80" (Linux PCs need root for port 80), use port 8081 instead and open **http://emi.local:8081**:

```bash
ssh -L 8081:192.168.49.2:80 SERVER_USER@SERVER_IP
```

Make a calculation, check the history table, and take the screenshot with the address bar visible → `m03_emi_local.png`. Press Calculate a few times: "Served by pod" changes, because the Ingress spreads requests across pods.

## Step 3.3 — Load distribution with 3 replicas (deliverable table)

**Run on: UBUNTU SERVER (window A)**

```bash
kubectl get pods -n emi -l app=emi-web        # confirm 3 pods Ready
cat scripts/load_distribution.sh
scripts/load_distribution.sh 30 results/m03/distribution_3_replicas.txt
```

- **What:** 30 POST requests with random valid inputs to `http://emi.local/api/emi`, reads `servedBy` from each JSON response, counts per pod.
- **Expected:** about 10 per pod (round-robin). For example:

```text
POD                                      REQUESTS
emi-web-7c9d8f6b5-abcde                  10
emi-web-7c9d8f6b5-fghij                  10
emi-web-7c9d8f6b5-klmno                  10
```

## Step 3.4 — Scale to 5 by hand, show new pods get traffic only when Ready

**Window A** (watch pods, with time on every line):

```bash
kubectl get pods -n emi -l app=emi-web -w | ts | tee results/m03/scale_watch.txt
```

**Window B** (scale, then immediately send requests):

```bash
cd ~/assignment4
ts() { while IFS= read -r line; do echo "$(date +%T) $line"; done; }
kubectl scale deployment emi-web --replicas=5 -n emi
scripts/load_distribution.sh 30 results/m03/distribution_5_replicas_during_scaleup.txt
```

Then wait until window A shows all 5 pods `1/1 Running`, and repeat:

```bash
kubectl get pods -n emi -l app=emi-web
scripts/load_distribution.sh 30 results/m03/distribution_5_replicas.txt
```

Stop window A with **Ctrl+C**.

**How to read it for the report:**

- In `scale_watch.txt`, each new pod first appears as `0/1 ContainerCreating` / `0/1 Running` and later as `1/1 Running` at some time **T**.
- In `distribution_5_replicas_during_scaleup.txt`, each request line has a time. The new pod names only appear on requests **after their T**.
- **Why:** the Service only lists a pod as an endpoint once its **readiness probe** (`/health`) passes, and the Ingress only routes to endpoints.
- `distribution_5_replicas.txt` (after all are Ready) shows about 6 requests per pod.

Go back to 3 replicas for the next steps:

```bash
kubectl scale deployment emi-web --replicas=3 -n emi
```

## Step 3.5 — Self-healing: delete a web pod

**Window A** (watch):

```bash
kubectl get pods -n emi -w | ts | tee results/m03/selfheal_web_watch.txt
```

**Window B** (request loop: one request every 0.2 s through the Ingress):

```bash
scripts/request_loop.sh results/m03/selfheal_web_loop.log
```

**Window C** (delete one web pod):

```bash
cd ~/assignment4
kubectl get pods -n emi -l app=emi-web
kubectl delete pod <one-emi-web-pod-name> -n emi
```

Watch window A: the deleted pod goes `Terminating`, and a **new** pod (new random suffix) appears and becomes `1/1 Running`. The Deployment keeps 3 replicas.

After about 20 seconds, press **Ctrl+C** in window B (prints `SUMMARY: total=... ok=... failed=0`) and in window A.

- **Why the app keeps answering:** the other 2 pods keep serving, and the deleted pod is removed from the endpoints first (`preStop: sleep 5` gives the Ingress time to notice).

## Step 3.6 — Self-healing: delete the MongoDB PRIMARY

**Window C** (find the primary):

```bash
scripts/mongo_primary.sh | tee results/m03/mongo_before.txt
scripts/count_documents.sh | tee -a results/m03/mongo_before.txt
```

**Window A** (watch):

```bash
kubectl get pods -n emi -l app=mongo -w | ts | tee results/m03/selfheal_mongo_watch.txt
```

**Window B** (request loop):

```bash
scripts/request_loop.sh results/m03/selfheal_mongo_loop.log
```

**Window C** (delete the PRIMARY; replace `mongo-0` with the pod name printed above):

```bash
kubectl delete pod mongo-0 -n emi
sleep 30
scripts/mongo_primary.sh | tee results/m03/mongo_after.txt
scripts/count_documents.sh | tee -a results/m03/mongo_after.txt
```

Stop windows B and A with **Ctrl+C**.

**What to show in the report:**

- `mongo_before.txt`: PRIMARY was `mongo-0`.
- `selfheal_mongo_watch.txt`: `mongo-0` Terminating, then recreated with the same name and Running.
- `mongo_after.txt`: a **different** member is PRIMARY now (for example `mongo-2`), and `mongo-0` came back as SECONDARY. The document count is **higher** than before, so the app kept saving.
- `selfheal_mongo_loop.log`: you may see a few `FAIL http=503` lines lasting a few seconds. That's the **election window** (no PRIMARY exists until the remaining members vote, about 10 seconds), after which requests are `OK` again. Explain this in the report; it's expected behaviour, not a bug.

## Step 3.7 — Rolling update to 1.1 and rollback

### 3.7.1 Build version 1.1

The footer shows the image version, so building with `APP_VERSION=1.1` changes the page footer. You may also change the page title in `app/public/index.html` (the `<title>` line) to make the change more visible.

**Window C:**

```bash
docker build --build-arg APP_VERSION=1.1 -t emi-web:1.1 app/
minikube image load emi-web:1.1
minikube image ls | grep emi-web          # both 1.0 and 1.1
```

### 3.7.2 Update while a request loop runs

**Window B** (start the loop first):

```bash
scripts/request_loop.sh results/m03/rolling_update_loop.log
```

**Window C:**

```bash
kubectl annotate deployment emi-web -n emi kubernetes.io/change-cause="initial version emi-web:1.0" --overwrite
kubectl set image deployment/emi-web web=emi-web:1.1 -n emi
kubectl annotate deployment emi-web -n emi kubernetes.io/change-cause="update to emi-web:1.1 (new footer)" --overwrite
kubectl rollout status deployment/emi-web -n emi | tee results/m03/rollout.txt
```

- `web` is the container name inside the Deployment.
- **What happens:** with `maxSurge: 1, maxUnavailable: 0`, Kubernetes starts one new 1.1 pod, waits until it's **Ready**, then removes one 1.0 pod, and repeats. There are always at least 3 Ready pods.
- In window B you'll see `version=1.0` change to `version=1.1`, with no `FAIL` lines.

When `rollout status` says `successfully rolled out`, stop window B with **Ctrl+C**. The last line must say **`failed=0`**.

Take an optional screenshot of `http://emi.local` showing **version 1.1** in the footer (`m03_version_1_1.png`).

```bash
kubectl rollout history deployment/emi-web -n emi | tee -a results/m03/rollout.txt
```

### 3.7.3 Roll back to 1.0

Start the loop again in **window B**:

```bash
scripts/request_loop.sh results/m03/rollback_loop.log
```

**Window C:**

```bash
kubectl rollout undo deployment/emi-web -n emi
kubectl rollout status deployment/emi-web -n emi | tee -a results/m03/rollout.txt
kubectl rollout history deployment/emi-web -n emi | tee -a results/m03/rollout.txt
curl -s http://emi.local/api/version
```

Stop window B (`failed=0` again). `/api/version` prints `"version":"1.0"`.

## Step 3.8 — Commit

```bash
git add results/ app/
git commit -m "Milestone 03: ingress, load distribution, self-healing, rolling update"
git push
```

### Milestone 03 done when
- [ ] Screenshot of `http://emi.local` (`m03_emi_local.png`)
- [ ] `distribution_3_replicas.txt` and `distribution_5_replicas.txt` (plus the during-scale-up file and `scale_watch.txt` to prove the "only after Ready" point)
- [ ] `selfheal_web_watch.txt` and `selfheal_mongo_watch.txt`, with `mongo_before.txt` / `mongo_after.txt` showing a new PRIMARY
- [ ] `rollout.txt` (status + history), `rolling_update_loop.log` ending in `failed=0`
- [ ] Deployment is back on `emi-web:1.0` with 3 replicas

Next: [05-MILESTONE-04.md](05-MILESTONE-04.md)
