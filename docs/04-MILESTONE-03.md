# Milestone 03 — Ingress, Load Balancing and Self-Healing

All commands: **Mac Terminal**, inside `~/assignment4`. Docker Desktop and the `emi` cluster must be running (`minikube start -p emi` if you restarted the Mac).

## What the PDF asks

| # | Task | In short |
|---|---|---|
| 1 | **Ingress** with `ingressClassName: nginx`, host `emi.local`, `/` → Service `emi-web`. On macOS with the Docker driver: run `minikube tunnel` and map `emi.local` to `127.0.0.1`. Open `http://emi.local` | `k8s/07-ingress.yaml` |
| 2 | **Load distribution**: 30 × `POST /api/emi` through the Ingress, count `servedBy` per pod | `scripts/load_distribution.sh` |
| 3 | **Scaling by hand**: `kubectl scale ... --replicas=5`, repeat 30 requests, show new pods get traffic **only after they are Ready** | watch + script |
| 4 | **Self-healing**: delete a web pod (app keeps answering), then delete the MongoDB **PRIMARY** (new PRIMARY elected, app still saves) | watch + `scripts/request_loop.sh` |
| 5 | **Rolling update + rollback**: change the footer, build `emi-web:1.1`, `kubectl set image` with a request loop running (zero failures), then `kubectl rollout undo` | `scripts/request_loop.sh` |

## Deliverables for Milestone 03

| Deliverable | Saved as |
|---|---|
| Ingress manifest + screenshot of the app at `http://emi.local` | `k8s/07-ingress.yaml`, `results/screenshots/m03_emi_local.png` |
| Table of requests per pod, 3 replicas and 5 replicas | `results/m03/distribution_3_replicas.txt`, `results/m03/distribution_5_replicas.txt` |
| `kubectl get pods -n emi -w` during both self-healing tests | `results/m03/selfheal_web_watch.txt`, `results/m03/selfheal_mongo_watch.txt` |
| `kubectl rollout status` + `kubectl rollout history` + request-loop log with zero failures | `results/m03/rollout.txt`, `results/m03/rolling_update_loop.log` |

## Terminal windows in this milestone

- **Window T (tunnel):** runs `minikube tunnel` the whole time. Don't close it.
- **Windows A, B, C:** for watching pods, sending requests and running commands at the same time. Open each with **Cmd + N** and start with `cd ~/assignment4`.

Paste this helper into **each** of windows A, B and C once. It puts the time in front of every line, so you can compare when things happened:

```bash
ts() { while IFS= read -r line; do echo "$(date +%T) $line"; done; }
```

---

## Step 3.1 — Create the Ingress

**Window A:**

```bash
cd ~/assignment4
mkdir -p results/m03
cat k8s/07-ingress.yaml
kubectl apply -f k8s/07-ingress.yaml
kubectl get ingress -n emi
```

- **Ingress**: an HTTP routing rule: "requests for host `emi.local`, path `/`, go to Service `emi-web` port 80".
- The **NGINX Ingress controller** (enabled in Milestone 02) applies that rule. It sends each request directly to one of the Ready pods behind the Service, taking turns (round-robin).
- Wait until the `ADDRESS` column shows an IP (up to a minute).

## Step 3.2 — Make emi.local reachable from your Mac

**1. Map the name** (asks for your Mac password):

```bash
echo "127.0.0.1 emi.local" | sudo tee -a /etc/hosts
grep emi.local /etc/hosts
```

- **Why:** there's no real DNS for `emi.local`. The hosts file tells your Mac "emi.local means this computer (127.0.0.1)".

**2. Start the tunnel in its own window (window T):** press **Cmd + N**, then:

```bash
minikube tunnel -p emi
```

- It may ask for your Mac password (it needs to open port 80). Then it prints status lines and **keeps running**.
- **Why:** with the Docker driver on macOS the Minikube node sits inside Docker Desktop and its IP isn't reachable from the Mac. `minikube tunnel` connects `127.0.0.1:80` on your Mac to the Ingress controller.
- **Leave window T open for the rest of Milestones 03 and 04.** If you close it, `http://emi.local` stops working; just run it again.

**3. Test** in window A:

```bash
curl -s http://emi.local/health
curl -s -X POST http://emi.local/api/emi -H 'Content-Type: application/json' -d '{"principal":500000,"rate":12,"months":24}' | jq
```

`/health` returns `{"status":"ok"...}` and the POST returns an EMI result.

**4. Check the speed** (important on macOS):

```bash
time curl -s -o /dev/null -w 'HTTP %{http_code}\n' http://emi.local/health
```

`real` must be well under 1 second. If it's about **5 seconds**, macOS is first looking up the `.local` name on the local network (Bonjour) before reading the hosts file. That makes the request loop and the load tests time out. Fix it once:

```bash
echo "::1 emi.local" | sudo tee -a /etc/hosts
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder
time curl -s -o /dev/null -w 'HTTP %{http_code}\n' http://emi.local/health
```

If it prints `HTTP 000`, the tunnel in window T isn't running; start `minikube tunnel -p emi` again.

## Step 3.3 — Screenshot at http://emi.local (deliverable)

1. In the browser, open **http://emi.local**.
2. Make a calculation and check the history table.
3. Click **Calculate EMI** a few times. "Served by pod" changes between pods, because the Ingress spreads requests.
4. Screenshot with the **address bar visible** (**Cmd + Shift + 4**, **Space**, click the browser):

```bash
mv ~/Desktop/Screenshot*.png ~/assignment4/results/screenshots/m03_emi_local.png
```

## Step 3.4 — Load distribution with 3 replicas (deliverable table)

**Window A:**

```bash
kubectl get pods -n emi -l app=emi-web            # 3 pods, all 1/1
cat scripts/load_distribution.sh
scripts/load_distribution.sh 30 results/m03/distribution_3_replicas.txt
```

- **What:** 30 POST requests with random valid inputs to `http://emi.local/api/emi`. It reads `servedBy` from each response and counts per pod.
- **Expected:** about 10 per pod, for example:

```text
POD                                      REQUESTS
emi-web-7c9d8f6b5-abcde                  10
emi-web-7c9d8f6b5-fghij                  10
emi-web-7c9d8f6b5-klmno                  10
```

## Step 3.5 — Scale to 5 by hand, show new pods get traffic only when Ready

**Window A** (watch the web pods, with times):

```bash
kubectl get pods -n emi -l app=emi-web -w | ts | tee results/m03/scale_watch.txt
```

**Window B** (scale, then immediately send requests):

```bash
kubectl scale deployment emi-web --replicas=5 -n emi
scripts/load_distribution.sh 30 results/m03/distribution_5_replicas_during_scaleup.txt
```

Wait until window A shows all 5 pods `1/1 Running`, then in **window B**:

```bash
kubectl get pods -n emi -l app=emi-web
scripts/load_distribution.sh 30 results/m03/distribution_5_replicas.txt
```

Stop window A with **Ctrl + C**.

**How to read it for the report:**

- In `scale_watch.txt`, each new pod first shows `0/1 ContainerCreating` / `0/1 Running`, and later `1/1 Running` at some time **T**.
- In `distribution_5_replicas_during_scaleup.txt`, every request has a time. The new pod names only appear on requests **after their T**.
- **Why:** the Service only lists a pod as an endpoint once its **readiness probe** (`/health`) passes, and the Ingress only sends traffic to endpoints.
- `distribution_5_replicas.txt` (all 5 Ready) shows about 6 requests per pod.

Go back to 3 replicas:

```bash
kubectl scale deployment emi-web --replicas=3 -n emi
```

## Step 3.6 — Self-healing: delete a web pod

**Window A** (watch all pods):

```bash
kubectl get pods -n emi -w | ts | tee results/m03/selfheal_web_watch.txt
```

**Window B** (request loop, one request every 0.2 s through the Ingress):

```bash
scripts/request_loop.sh results/m03/selfheal_web_loop.log
```

**Window C** (delete one web pod):

```bash
kubectl get pods -n emi -l app=emi-web
POD=$(kubectl get pods -n emi -l app=emi-web -o jsonpath='{.items[0].metadata.name}')
echo "Deleting $POD"
kubectl delete pod "$POD" -n emi
```

(The second line picks the first web pod's name automatically, so you don't type it.)

In window A, the deleted pod goes `Terminating` and a **new** pod (new random suffix) appears and becomes `1/1 Running`. The Deployment keeps 3 replicas.

After about 20 seconds, press **Ctrl + C** in window B. It prints `SUMMARY: total=... ok=... failed=0`. Then press **Ctrl + C** in window A.

- **Why the app keeps answering:** the other 2 pods keep serving, and the deleted pod is taken out of the endpoints first (`preStop: sleep 5` gives the Ingress time to notice).

## Step 3.7 — Self-healing: delete the MongoDB PRIMARY

**Window C** (find the PRIMARY):

```bash
scripts/mongo_primary.sh | tee results/m03/mongo_before.txt
scripts/count_documents.sh | tee -a results/m03/mongo_before.txt
```

**Window A** (watch MongoDB pods):

```bash
kubectl get pods -n emi -l app=mongo -w | ts | tee results/m03/selfheal_mongo_watch.txt
```

**Window B** (request loop):

```bash
scripts/request_loop.sh results/m03/selfheal_mongo_loop.log
```

**Window C** (delete the PRIMARY; the first line reads its pod name from `mongo_primary.sh`):

```bash
PRIMARY=$(scripts/mongo_primary.sh | awk '/PRIMARY pod:/{print $3}')
echo "Deleting PRIMARY $PRIMARY"
kubectl delete pod "$PRIMARY" -n emi
sleep 30
scripts/mongo_primary.sh | tee results/m03/mongo_after.txt
scripts/count_documents.sh | tee -a results/m03/mongo_after.txt
```

Stop windows B and A with **Ctrl + C**.

**What to show in the report:**

- `mongo_before.txt`: the PRIMARY was, for example, `mongo-0`.
- `selfheal_mongo_watch.txt`: `mongo-0` Terminating, then recreated with the same name and Running.
- `mongo_after.txt`: a **different** member is now PRIMARY (e.g. `mongo-2`), `mongo-0` came back as SECONDARY, and the document count is **higher** than before, so the app kept saving.
- `selfheal_mongo_loop.log`: you may see a few `FAIL http=503` lines for some seconds. That's the **election window**: no PRIMARY exists until the remaining two members vote (about 10 seconds). Then requests are `OK` again. Explain this in the report; it's expected, not a bug.

## Step 3.8 — Rolling update to 1.1 and rollback

### 3.8.1 Build version 1.1

The page footer shows the image version, so building with `APP_VERSION=1.1` changes the footer. To make the change more visible you can also edit the `<title>` line in `app/public/index.html` (e.g. `Loan EMI Calculator v1.1`).

**Window C:**

```bash
docker build --build-arg APP_VERSION=1.1 -t emi-web:1.1 app/
minikube image load emi-web:1.1
minikube image ls | grep emi-web          # both 1.0 and 1.1
```

### 3.8.2 Update while a request loop runs

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

- `web` is the container's name inside the Deployment.
- **What happens:** with `maxSurge: 1, maxUnavailable: 0`, Kubernetes starts one 1.1 pod, waits until it's **Ready**, removes one 1.0 pod, and repeats. At least 3 Ready pods exist at all times.
- In window B, `version=1.0` switches to `version=1.1` with no `FAIL` lines.

When `rollout status` says `successfully rolled out`, press **Ctrl + C** in window B. The last line must be **`failed=0`**.

Optional screenshot: reload `http://emi.local`; the footer shows **version 1.1**. Save it as `results/screenshots/m03_version_1_1.png`.

```bash
kubectl rollout history deployment/emi-web -n emi | tee -a results/m03/rollout.txt
```

### 3.8.3 Roll back to 1.0

**Window B** (loop again):

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

If you changed the `<title>` in `index.html`, change it back (the cluster runs 1.0 again):

```bash
git checkout app/public/index.html
```

## Step 3.9 — Commit

```bash
git add results/
git commit -m "Milestone 03: ingress, load distribution, self-healing, rolling update"
git push
```

### Milestone 03 done when
- [ ] `results/screenshots/m03_emi_local.png` (address bar shows `emi.local`)
- [ ] `distribution_3_replicas.txt` and `distribution_5_replicas.txt`, plus `distribution_5_replicas_during_scaleup.txt` and `scale_watch.txt` for the "only after Ready" point
- [ ] `selfheal_web_watch.txt` and `selfheal_mongo_watch.txt`, with `mongo_before.txt` / `mongo_after.txt` showing a new PRIMARY
- [ ] `rollout.txt` (status + history) and `rolling_update_loop.log` ending in `failed=0`
- [ ] The Deployment is back on `emi-web:1.0` with 3 replicas
- [ ] Window T (`minikube tunnel`) still running for Milestone 04

Next: [05-MILESTONE-04.md](05-MILESTONE-04.md)
