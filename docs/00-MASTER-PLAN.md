# Assignment 4 — Master Plan (macOS)

DS-584 Cloud Computing, Fall 2026 — *Deploying, Load Balancing and Autoscaling a Web Application with MongoDB on Kubernetes (Minikube)*

**Deadline:** November 25, 2026, 11:59 pm (Google Classroom): one PDF report plus the Git repository link.
**Repository:** https://github.com/HibaNoor225/Cloud_Assignment4
**Machine:** everything runs on your Mac (Docker Desktop + Minikube). No Ubuntu, no SSH.

Read this page first. It explains what the assignment asks, how the work is split, and which guide to open for each step.

---

## 1. What the assignment is asking, in plain words

You build a small website, a **Loan EMI Calculator**. A user enters a loan amount, an interest rate and a number of months. The server calculates the monthly instalment (EMI) and saves every calculation in **MongoDB**.

You then run that website on **Kubernetes** (Minikube on your Mac) like a real production system:

- The website runs as **several copies (pods)**, sharing the traffic (**load balancing**).
- MongoDB runs as **3 copies** (a *replica set*). If one dies, the data is still there and another copy takes over.
- Traffic comes in through **NGINX Ingress** at `http://emi.local`.
- When traffic grows, Kubernetes **adds pods automatically**, and removes them when traffic drops (**autoscaling with the HPA**).
- You **load-test** the system, measure response time and CPU, and draw **3 graphs**.

## 2. The final architecture (Figure 1 of the PDF)

```text
 Your Mac (the "host")
 ┌────────────────────────────────────────────────────────────────────┐
 │  httperf (load generator) ──HTTP──► http://emi.local (127.0.0.1)    │
 │                                         │  minikube tunnel         │
 │  Docker Desktop → Minikube node, namespace "emi"                   │
 │   ┌──────────────────────────────────────────────────────────────┐ │
 │   │  Ingress (NGINX controller)                                   │ │
 │   │        │                                                      │ │
 │   │        ▼                                                      │ │
 │   │  Service emi-web (ClusterIP) ── spreads requests ──┐          │ │
 │   │        │                │                │          │          │ │
 │   │   emi-web pod 1    emi-web pod 2    emi-web pod 3   ◄── HPA    │ │
 │   │        └────────────────┼────────────────┘   (1–5 pods, 50% CPU)│
 │   │                         ▼  MONGO_URL                           │ │
 │   │   mongo-0 (PRIMARY)   mongo-1 (SECONDARY)   mongo-2 (SECONDARY)│ │
 │   │     PVC 1Gi             PVC 1Gi               PVC 1Gi          │ │
 │   │   StatefulSet "mongo" + headless Service "mongo", replica set rs0│
 │   └──────────────────────────────────────────────────────────────┘ │
 └────────────────────────────────────────────────────────────────────┘
```

## 3. The repository

```text
app/                      Milestone 01 – the web application
  server.js               Express server: POST /api/emi, GET /api/history, GET /health
  emi.js                  EMI formula + input validation
  public/                 index.html (Bootstrap), app.js (jQuery AJAX), style.css
  test/emi.test.js        Unit test: P=500000, 12%, 24 months -> EMI 23,536.74
  Dockerfile              Milestone 02 – node:20-alpine, non-root user
  .dockerignore
k8s/                      Milestones 02/03 – all manifests, applied with kubectl apply -f k8s/
  00-namespace.yaml       namespace emi
  01-mongo-service.yaml   headless Service "mongo" (clusterIP: None)
  02-mongo-statefulset.yaml  StatefulSet "mongo", 3 replicas, 1Gi PVC each
  03-mongo-init-job.yaml  Job "mongo-init" -> rs.initiate() with 3 members
  04-configmap.yaml       MONGO_URL
  05-web-deployment.yaml  Deployment "emi-web", 3 replicas, probes, CPU/memory limits
  06-web-service.yaml     ClusterIP Service "emi-web"
  07-ingress.yaml         Ingress, host emi.local
  hpa/emi-web-hpa.yaml    Milestone 04 – HPA (applied separately, see guide 05)
scripts/                  Helper scripts for Milestones 02–04
results/                  Every output file and screenshot
docs/                     These guides
README.md                 How to bring up the system on a fresh Minikube cluster
```

## 4. Order of work (follow exactly)

| Step | Guide | What you finish | Deliverables collected |
|---|---|---|---|
| 0 | [01-SETUP.md](01-SETUP.md) | Homebrew, Docker Desktop, Minikube, kubectl, Node, httperf, your repo, Python env | `results/environment.txt` (for the report) |
| 1 | [02-MILESTONE-01.md](02-MILESTONE-01.md) | App + MongoDB running locally (Docker container) | UI screenshot (500000 / 12% / 24) + Git link |
| 2 | [03-MILESTONE-02.md](03-MILESTONE-02.md) | Image, Minikube cluster, MongoDB replica set, web app, persistence test | Dockerfile + YAML, `kubectl get all...`, `rs.status()`, job log, screenshot, persistence proof |
| 3 | [04-MILESTONE-03.md](04-MILESTONE-03.md) | Ingress + tunnel, load distribution, scaling, self-healing, rolling update | Ingress screenshot, per-pod tables, watch outputs, rollout outputs + loop log |
| 4 | [05-MILESTONE-04.md](05-MILESTONE-04.md) | 15 fixed-replica load tests, profiling CSVs, HPA test, graphs | Graphs 1–3, 15-run table, raw `results/` |
| 5 | [06-REPORT-AND-SUBMISSION.md](06-REPORT-AND-SUBMISSION.md) | PDF report, final push, submit | Final checklist + report outline |

**Rule:** don't start the next milestone until every "done when" box of the current one is ticked. After each milestone: `git add results/ && git commit -m "..." && git push`.

## 5. Where each deliverable is saved

```text
results/
  environment.txt  Mac + tool versions
  screenshots/     browser screenshots (moved from the Desktop after Cmd+Shift+4)
  m01/             Milestone 01 outputs
  m02/             Milestone 02 outputs
  m03/             Milestone 03 outputs
  m04/fixed/       15 runs (httperf.txt, pods.csv, host_cpu.csv each) + summary.csv
  m04/autoscale/   HPA test (hpa.csv, pods.csv, host_cpu.csv, phases.csv, httperf_*.txt)
  graphs/          graph1/2/3 PNGs
```

## 6. Things that must be running

| Milestone | Needs running |
|---|---|
| 01 | Docker Desktop |
| 02 | Docker Desktop, cluster `emi` (`minikube start -p emi`) |
| 03–04 | Docker Desktop, cluster `emi`, **and a Terminal window with `minikube tunnel -p emi`** |

## 7. Rough effort per milestone

- **Setup:** mostly installing; the Xcode tools download and the first `minikube start` are the slow parts.
- **Milestone 01:** short; the app is already written, so you run it, test it, take one screenshot.
- **Milestone 02:** about 20 commands plus waiting for MongoDB pods and the init Job.
- **Milestone 03:** many small experiments; needs 3–4 Terminal windows at once.
- **Milestone 04:** mostly waiting: about 25 minutes of automated fixed-rate tests and 12 minutes for the HPA test.
