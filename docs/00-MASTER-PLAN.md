# Assignment 4 — Master Plan

DS-584 Cloud Computing, Fall 2026 — *Deploying, Load Balancing and Autoscaling a Web Application with MongoDB on Kubernetes (Minikube)*

**Deadline:** November 25, 2026, 11:59 pm (Google Classroom): one PDF report plus the Git repository link.

Read this page first. It explains what the assignment asks, how the work is split, and which guide to open for each step.

---

## 1. What the assignment is asking, in plain words

You build a small website, a **Loan EMI Calculator**. A user enters a loan amount, an interest rate and a number of months. The server calculates the monthly instalment (EMI) and saves every calculation in **MongoDB**.

You then run that website on **Kubernetes** (with Minikube) like a real production system:

- The website runs as **several copies (pods)**, so the load is shared between them (**load balancing**).
- MongoDB runs as **3 copies** (a *replica set*). If one copy dies, the data is still there and another copy takes over.
- Traffic from outside comes in through **NGINX Ingress**, at the address `http://emi.local`.
- When traffic grows, Kubernetes **adds pods automatically** and removes them when traffic drops (**autoscaling with the HPA**).
- You **load-test** the system, measure response time and CPU, and draw **3 graphs**.

## 2. The final architecture (Figure 1 of the PDF)

```text
 Your Ubuntu server (the "host")
 ┌────────────────────────────────────────────────────────────────────┐
 │  httperf (load generator) ──HTTP──► http://emi.local                │
 │                                         │                          │
 │  Minikube node, namespace "emi"         ▼                          │
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

## 3. Choose your setup: Mac only, or PC + Ubuntu server

- **Mac only (simplest):** everything runs on the Mac with Docker Desktop + Minikube. Follow [01-SETUP-MAC.md](01-SETUP-MAC.md) instead of the Ubuntu setup guide, and read the **On a Mac** box at the top of each milestone guide. You can skip the rest of this section.
- **PC + Ubuntu server over SSH:** follow [01-SETUP-FROM-ZERO.md](01-SETUP-FROM-ZERO.md) and the table below.

### The two machines in the Ubuntu setup

| Machine | What it is | What you do on it |
|---|---|---|
| **YOUR PC** (Windows / Mac / Linux laptop) | Where you sit | Open a terminal, `ssh` into the server, open the **browser**, take **screenshots**, write the **report** |
| **UBUNTU SERVER** | Where everything runs | Docker, Minikube, kubectl, the app, MongoDB, load tests. You control it through **SSH** |

Every command block in these guides is labelled **Run on: YOUR PC** or **Run on: UBUNTU SERVER (inside SSH)**.

> The browser runs on your PC but the app runs on the server. We connect the two with an **SSH tunnel** (`ssh -L ...`). Each guide shows the exact tunnel command.

## 4. Separate from Assignments 1–3

Assignment 4 uses its **own Minikube cluster** (profile name `emi`) and its own namespace `emi`. Your old cluster from earlier assignments is not touched or deleted. Because the cluster starts empty, anything that works in it was created by this assignment.

## 5. The repository (what is already built for you)

```text
app/                      Milestone 01 – the web application
  server.js               Express server: POST /api/emi, GET /api/history, GET /health
  emi.js                  EMI formula + input validation
  public/                 index.html (Bootstrap), app.js (jQuery AJAX), style.css
  test/emi.test.js        Unit test: P=500000, 12%, 24 months -> EMI 23,536.74
  Dockerfile              Milestone 02 – node:20-alpine, non-root user
  .dockerignore
k8s/                      Milestone 02/03 – all manifests, applied with kubectl apply -f k8s/
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
results/                  Where every output file and screenshot is saved
docs/                     These guides
README.md                 How to bring up the system on a fresh Minikube cluster
```

## 6. Order of work (follow exactly)

| Step | Guide | What you finish | Deliverables collected |
|---|---|---|---|
| 0 | [01-SETUP-MAC.md](01-SETUP-MAC.md) **or** [01-SETUP-FROM-ZERO.md](01-SETUP-FROM-ZERO.md) | Install tools, create your Git repo, clone it | Nothing graded (keep notes) |
| 1 | [02-MILESTONE-01.md](02-MILESTONE-01.md) | App + MongoDB running locally (Docker container) | UI screenshot (500000 / 12% / 24) + Git link |
| 2 | [03-MILESTONE-02.md](03-MILESTONE-02.md) | Image, Minikube, MongoDB replica set, web app, persistence test | Dockerfile + YAML, `kubectl get all...`, `rs.status()`, job logs, screenshots, persistence proof |
| 3 | [04-MILESTONE-03.md](04-MILESTONE-03.md) | Ingress, load distribution, scaling, self-healing, rolling update | Ingress screenshot, per-pod tables, watch outputs, rollout outputs + loop log |
| 4 | [05-MILESTONE-04.md](05-MILESTONE-04.md) | 15 fixed-replica load tests, profiling CSVs, HPA test, graphs | Graphs 1–3, raw `results/` |
| 5 | [06-REPORT-AND-SUBMISSION.md](06-REPORT-AND-SUBMISSION.md) | PDF report, push repo, submit | Final checklist + report template |

**Rule:** don't start the next milestone until every "Milestone done when" box of the current one is ticked.

## 7. Where each deliverable is saved

Save everything under `results/` on the server as you go, then `git push`. At the end, `results/` holds every piece of evidence for the report.

```text
results/
  screenshots/   PNGs you take on your PC (copy them in, or keep them on the PC for the report)
  m01/           Milestone 01 outputs
  m02/           Milestone 02 outputs
  m03/           Milestone 03 outputs
  m04/fixed/     15 runs (httperf.txt, pods.csv, host_cpu.csv each) + summary.csv
  m04/autoscale/ HPA test (hpa.csv, pods.csv, host_cpu.csv, phases.csv, httperf_*.txt)
  graphs/        graph1/2/3 PNGs
```

## 8. Rough effort per milestone

- **Setup**: mostly installing tools. Longest part is the first `minikube start` (downloads images).
- **Milestone 01**: short, because the app is already written. You run it and take one screenshot.
- **Milestone 02**: several commands, plus waiting for MongoDB pods and the init Job.
- **Milestone 03**: many small experiments; needs 2–3 SSH windows open at the same time.
- **Milestone 04**: mostly waiting. The 15 fixed runs take about 25 minutes of automated testing and the HPA test 12 minutes.
