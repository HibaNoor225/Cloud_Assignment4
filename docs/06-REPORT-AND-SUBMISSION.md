# Step 5 — Report and Submission

**Due:** November 25, 2026, 11:59 pm on Google Classroom
**Submit:** (1) a PDF report with every deliverable, and (2) the Git repository link.

---

## 5.1 Complete deliverables checklist

Tick each item as you collect it. The "Source" column says where it comes from.

### Milestone 01 — EMI calculator with MongoDB

| ✓ | Deliverable | Source |
|---|---|---|
| [ ] | Screenshot of UI: P=500000, rate=12%, n=24 (EMI 23,536.74) **with history table** | `results/screenshots/m01_ui_500000_12_24.png` |
| [ ] | Git repository link (source code) | `https://github.com/HibaNoor225/Cloud_Assignment4` |

### Milestone 02 — MongoDB + web app on Minikube

| ✓ | Deliverable | Source |
|---|---|---|
| [ ] | Dockerfile, .dockerignore | `app/Dockerfile`, `app/.dockerignore` |
| [ ] | All YAML manifests | `k8s/*.yaml` |
| [ ] | `kubectl get all,pvc,configmap -n emi -o wide`, all pods Running & Ready | `results/m02/get_all.txt` |
| [ ] | `rs.status()` trimmed to names + states (1 PRIMARY, 2 SECONDARY) | `results/m02/rs_status.txt` |
| [ ] | `kubectl logs job/mongo-init -n emi` | `results/m02/mongo_init_job.log` |
| [ ] | Screenshot of app via port-forward with history table | `results/screenshots/m02_portforward_app.png` |
| [ ] | Persistence test: pod age, PVC name, documents before/after | `results/m02/persistence_test.txt` |

### Milestone 03 — Ingress, load balancing, self-healing

| ✓ | Deliverable | Source |
|---|---|---|
| [ ] | Ingress manifest | `k8s/07-ingress.yaml` |
| [ ] | Screenshot of app at `http://emi.local` | `results/screenshots/m03_emi_local.png` |
| [ ] | Requests-per-pod table, 3 replicas | `results/m03/distribution_3_replicas.txt` |
| [ ] | Requests-per-pod table, 5 replicas (+ proof new pods only get traffic once Ready) | `results/m03/distribution_5_replicas.txt`, `distribution_5_replicas_during_scaleup.txt`, `scale_watch.txt` |
| [ ] | `kubectl get pods -w` during web-pod deletion | `results/m03/selfheal_web_watch.txt` (+ `selfheal_web_loop.log`) |
| [ ] | `kubectl get pods -w` during PRIMARY deletion + new PRIMARY | `results/m03/selfheal_mongo_watch.txt`, `mongo_before.txt`, `mongo_after.txt` |
| [ ] | `kubectl rollout status` and `kubectl rollout history` | `results/m03/rollout.txt` |
| [ ] | Request-loop log, zero failed requests during update | `results/m03/rolling_update_loop.log` (last line `failed=0`) |

### Milestone 04 — Load testing, profiling, autoscaling

| ✓ | Deliverable | Source |
|---|---|---|
| [ ] | Graph 1: response time vs rate (1/2/3 replicas) | `results/graphs/graph1_response_time_vs_rate.png` |
| [ ] | Graph 2: per-pod CPU, 100 req/s, 3 replicas | `results/graphs/graph2_pod_cpu_100rps_3replicas.png` |
| [ ] | Graph 3: rate + avg CPU + replicas during HPA test | `results/graphs/graph3_autoscaling.png` |
| [ ] | Table of 15 runs (avg response time, errors) | `results/m04/fixed/summary.csv` |
| [ ] | HPA manifest | `k8s/hpa/emi-web-hpa.yaml` |
| [ ] | Raw outputs in `results/` | `results/m04/**` |

### Repository requirements

| ✓ | Requirement |
|---|---|
| [ ] | Structure `app/`, `k8s/`, `scripts/`, `results/`, `README.md` |
| [ ] | README explains bringing up the system on a fresh Minikube with `kubectl apply -f k8s/` |
| [ ] | Everything committed and pushed (`git status` clean, `git log` shows your commits) |

---

## 5.2 Report template (copy into Word / Google Docs, export as PDF)

Paste terminal outputs as text in a monospace font (Consolas / Courier New, 9 pt). Long outputs can be trimmed, but keep the lines that prove the point.

```text
DS-584 Cloud Computing — Assignment 4
Deploying, Load Balancing and Autoscaling a Web Application with MongoDB on Kubernetes
Name: ____________   Roll No: ____________   Date: ____________
Git repository: https://github.com/HibaNoor225/Cloud_Assignment4

0. Environment
   - Mac model / chip (Apple Silicon or Intel), macOS version, CPU cores, RAM
     (from results/environment.txt)
   - Docker Desktop resources (CPUs / memory); Minikube profile "emi",
     --driver=docker --cpus=_ --memory=_ ; Kubernetes version (kubectl version)
   - Ingress reached through minikube tunnel + /etc/hosts 127.0.0.1 emi.local

1. Milestone 01 — Loan EMI Calculator
   1.1 Design: Node.js/Express + HTML/Bootstrap/jQuery; endpoints table
       (POST /api/emi, GET /api/history, GET /health); MONGO_URL from env;
       servedBy from HOSTNAME
   1.2 Formula and validation (client + server)
   1.3 Screenshot: P=500000, 12%, 24 -> EMI 23,536.74 with history table
   1.4 Source code: <repo link>

2. Milestone 02 — MongoDB and the Web App on Minikube
   2.1 Dockerfile + .dockerignore (paste), explain alpine base + non-root user
   2.2 Manifests overview (table: file -> object -> purpose); full YAML in Appendix A
   2.3 kubectl get all,pvc,configmap -n emi -o wide   (paste get_all.txt)
   2.4 Replica set: mongo-init job log + rs.status() (1 PRIMARY, 2 SECONDARY)
   2.5 Screenshot through port-forward with history table
   2.6 Persistence test: before/after pod age, PVC data-mongo-1, document counts;
       explain why the StatefulSet keeps the data

3. Milestone 03 — Ingress, Load Balancing and Self-Healing
   3.1 Ingress manifest + screenshot at http://emi.local
   3.2 Table: requests per pod (3 replicas) and (5 replicas)
       | Pod | Requests (3 replicas) |   | Pod | Requests (5 replicas) |
   3.3 Scaling: new pods received traffic only after READY 1/1
       (cite times from scale_watch.txt vs distribution_5_replicas_during_scaleup.txt)
   3.4 Self-healing (web pod): watch output, request loop summary
   3.5 Self-healing (MongoDB PRIMARY): before/after primary, watch output,
       document count increased; explain the short election window
   3.6 Rolling update 1.0 -> 1.1 and rollback: rollout status, rollout history,
       loop log summary "failed=0"; explain maxSurge=1 / maxUnavailable=0 + readiness

4. Milestone 04 — Load Testing, Profiling and Autoscaling
   4.1 Method: httperf with random POST bodies (--wsesslog), 60 s per run,
       monitor.py (kubectl top every 15 s, host CPU every 1 s)
   4.2 Table of the 15 runs (summary.csv): replicas, rate, avg ms, errors
   4.3 Graph 1 + discussion (where 1 replica saturates; effect of 2/3 replicas)
   4.4 Graph 2 + discussion (is load even across pods? CPU vs 250m limit)
   4.5 HPA manifest; Graph 3 + discussion (when it scaled up, max replicas reached,
       when it scaled down, stabilization window); hpa_describe events
   4.6 Bottlenecks observed (pod CPU limit, MongoDB writes, single-node host CPU)

5. Conclusion (5–8 lines)

Appendix A — All YAML manifests
Appendix B — Scripts list (scripts/*) with one-line description each
```

## 5.3 Final push and submission

**Mac Terminal:**

```bash
cd ~/assignment4
git status                 # should list only results you haven't added yet
git add -A
git commit -m "Assignment 4: final results"
git push
git log --oneline | head
```

Then:

1. Open [github.com/HibaNoor225/Cloud_Assignment4](https://github.com/HibaNoor225/Cloud_Assignment4) and check that `results/graphs/`, `results/screenshots/` and `README.md` are there. If the repo is private, add your instructor as a collaborator (Settings > Collaborators).
2. Export the report as PDF (File > Download > PDF in Google Docs; File > Save As > PDF in Word; File > Export as PDF in Pages).
3. On Google Classroom, upload the PDF, paste the repository link, and click **Turn in**.

## 5.4 Clean up (after grading only)

```bash
minikube stop -p emi          # stop the cluster (keeps everything)
minikube delete -p emi        # delete it completely (only when you're sure)
```

Stopping Docker Desktop afterwards frees the memory it reserved.
