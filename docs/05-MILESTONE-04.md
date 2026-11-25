# Milestone 04 — Load Testing, Profiling and Autoscaling (25 marks)

All commands: **Mac Terminal**, inside `~/assignment4`, with the Python environment active:

```bash
cd ~/assignment4 && source .venv/bin/activate
```

Keep running the whole time: **Docker Desktop**, the `emi` cluster, and **window T with `minikube tunnel -p emi`** (from Milestone 03).

## What the PDF asks

| # | Task | How we do it |
|---|---|---|
| 1 | **Workload**: every request is `POST /api/emi` with **random valid inputs** (so each also writes to MongoDB), sent only to `http://emi.local/` | `scripts/gen_wsesslog.py` makes random bodies for **httperf** |
| 2 | **Fixed replicas**: 10, 25, 50, 100, 200 req/s, 60 s each, at 1, 2 and 3 replicas = **15 runs**. Record average response time and error count | `scripts/run_fixed_experiments.sh` → `results/m04/fixed/summary.csv` |
| 3 | **Profiling**: during each run, `kubectl top pods -n emi` every **15 s** and the host's CPU every **1 s**, saved to CSV with a timestamp column, by your own script | `scripts/monitor.py` → `pods.csv`, `host_cpu.csv` |
| 4 | **Autoscaling**: HPA (`autoscaling/v2`), min 1, max 5, 50% CPU. 10-minute test: 2 min @ 10 req/s, 5 min @ 100 req/s, 3 min @ 10 req/s. Record replicas every 15 s with `kubectl get hpa emi-web -n emi` | `k8s/hpa/emi-web-hpa.yaml` + `scripts/run_autoscale_test.sh` → `hpa.csv` |
| 5 | **Results**: all raw outputs in `results/` | everything below writes there |

Here **the host is your Mac**: httperf runs on the Mac, and "host CPU" is the Mac's CPU.

## Deliverables for Milestone 04 (graphs)

| Graph | Content | File |
|---|---|---|
| **Graph 1** | Average response time (ms) vs request rate, one line each for 1, 2, 3 replicas | `results/graphs/graph1_response_time_vs_rate.png` |
| **Graph 2** | CPU utilization (%) over time per pod, 100 req/s run with 3 replicas | `results/graphs/graph2_pod_cpu_100rps_3replicas.png` |
| **Graph 3** | Autoscaling test: request rate, average CPU and replica count over the 10 minutes, shared time axis | `results/graphs/graph3_autoscaling.png` |

Also put the **15-run table** (`summary.csv`: replicas, rate, average response time, errors) in the report. It's the data behind Graph 1 and the error counts the PDF asks for.

---

## Why httperf (and not ab)

The PDF allows httperf or ApacheBench. **ab** sends the *same* body every time, so it can't do "random valid inputs". **httperf**'s `--wsesslog` mode reads a list of requests from a file, and we generate that file with a different random loan for every request. httperf also sends at a **fixed rate** (`--rate`), which is exactly "10, 25, 50, 100, 200 requests per second".

One run (`scripts/httperf_run.sh RATE SECONDS OUTFILE`) does:

```bash
python3 scripts/gen_wsesslog.py 1000 sessions.txt 10    # up to 1000 sessions x 10 random POSTs
httperf --hog --server emi.local --port 80 --wsesslog=SESSIONS,0.1,sessions.txt --rate RATE/10 --timeout 5 \
        --add-header='Content-Type: application/x-www-form-urlencoded\n'
```

httperf's **session mode**: each session opens one persistent connection and sends 10 requests on it, 0.1 s apart. Sessions start at RATE/10 per second, so the request rate is RATE (httperf reports it as `Request rate`) while new connections are 10 times fewer. Opening a new connection for every request made httperf crash or stall on macOS at 200 req/s, because every connection goes through `minikube tunnel`. Every request is still a valid random loan and writes a new document to MongoDB. Mention this method in the report.

httperf's output contains the numbers we need:

```text
Reply time [ms]: response 12.3 transfer 0.0      -> average response time = 12.3 ms
Errors: total 0 client-timo 0 ...                -> error count
Reply status: 1xx=0 2xx=600 3xx=0 4xx=0 5xx=0    -> 4xx/5xx are counted as errors too
```

## Before you start

- **Close heavy apps** (other browsers' tabs, video calls, IDEs), because the Mac is the host whose CPU you measure.
- **Plug in the charger.** On battery, macOS slows the CPU down.
- **Keep the Mac awake:** run long scripts with `caffeinate -i ...` (shown below). It stops sleep until the script ends.
- Allow httperf more open connections in each window you use (harmless):

```bash
ulimit -n 4096
```

## Step 4.1 — Pre-flight checks

```bash
cd ~/assignment4 && source .venv/bin/activate
mkdir -p results/m04
kubectl top pods -n emi                        # metrics-server works (numbers, not an error)
kubectl get deploy emi-web -n emi -o wide      # image emi-web:1.0, 3/3 ready
curl -s http://emi.local/health                # tunnel + Ingress work
which httperf
scripts/httperf_run.sh 10 5 /tmp/smoke.txt     # 5-second test at 10 req/s
```

The smoke test must print `2xx=50` and `Errors: total 0`.

| Problem | Fix |
|---|---|
| `kubectl top`: `Metrics API not available` | `minikube addons enable metrics-server`, wait 1–2 minutes |
| `curl emi.local` hangs or is refused | window T (`minikube tunnel -p emi`) isn't running; start it again |
| `python3: No module named matplotlib/psutil` | run `source .venv/bin/activate` in this window |

## Step 4.2 — The profiling script (task 3)

Read `scripts/monitor.py`. This is the "small script that saves both to CSV files with a timestamp column":

- **Every 15 s:** runs `kubectl top pods -n emi` and appends `timestamp,pod,cpu_millicores,memory_mib` to `pods.csv`.
- **Every 1 s:** reads the Mac's overall CPU % with `psutil` and appends `timestamp,cpu_percent` to `host_cpu.csv`.
- **Every 15 s, with `--hpa`:** runs `kubectl get hpa emi-web -n emi` and appends replicas and CPU % to `hpa.csv`.

Try it for 20 seconds:

```bash
python3 scripts/monitor.py --out-dir /tmp/montest --duration 20
head /tmp/montest/pods.csv /tmp/montest/host_cpu.csv
```

You don't run it by hand for the experiments; the experiment scripts start and stop it around each run.

## Step 4.3 — The 15 fixed-replica runs (tasks 1–3)

About **25 minutes**, fully automatic. Leave the Mac alone while it runs.

```bash
cat scripts/run_fixed_experiments.sh
caffeinate -i scripts/run_fixed_experiments.sh 2>&1 | tee results/m04/fixed_runs_console.log
```

For each replica count (1, then 2, then 3) it:

1. Deletes any HPA, so nothing changes the replica count behind your back.
2. Runs `kubectl scale deployment emi-web --replicas=N`, waits for the rollout, then waits 15 s.
3. For each rate (10, 25, 50, 100, 200 req/s):
   - starts `monitor.py` (pods every 15 s, Mac CPU every 1 s),
   - runs httperf for 60 s with random POST bodies,
   - stops the monitor,
   - writes one line to `results/m04/fixed/summary.csv`,
   - rests 15 s.

Output:

```text
results/m04/fixed/
  summary.csv                    replicas,rate,avg_response_ms,errors,replies_2xx,run_dir
  r1_rate10/   httperf.txt  pods.csv  host_cpu.csv  pods_before.txt
  r1_rate25/   ...
  ...
  r3_rate200/  ...
```

At the end it prints the summary table. Look at it again anytime with:

```bash
column -s, -t results/m04/fixed/summary.csv
```

**What to expect (and discuss in the report):**

- At low rates every replica count is fast.
- With **1 replica** the single pod is capped at **250m CPU** (its limit). As the rate grows it saturates: response time climbs sharply, and at 100–200 req/s there will probably be errors (timeouts / 5xx).
- With **2 and 3 replicas** the load is shared, so response time stays low for longer.
- Every request also writes to MongoDB, and everything runs inside one Minikube node in Docker Desktop on your Mac, so at the highest rates the database and the Mac's CPU (`host_cpu.csv`) can become the bottleneck too.

To redo a single run (e.g. one was disturbed), delete its line from `summary.csv` and run:

```bash
REPLICAS="3" RATES="100" caffeinate -i scripts/run_fixed_experiments.sh
```

## Step 4.4 — Autoscaling test (task 4)

```bash
cat k8s/hpa/emi-web-hpa.yaml
```

- `scaleTargetRef`: the `emi-web` Deployment.
- `minReplicas: 1`, `maxReplicas: 5`.
- `averageUtilization: 50`: target 50% of the **CPU request** (100m), i.e. about 50m per pod on average. Above it the HPA adds pods; below it, it removes them.
- `behavior.scaleDown.stabilizationWindowSeconds: 60`: by default the HPA waits **5 minutes** before scaling down. With 60 s the scale-down shows inside the 3-minute cool-down phase. Mention this in the report.
- It's in `k8s/hpa/` (not `k8s/`) so it doesn't fight the manual `kubectl scale` commands of Milestones 02–03 and step 4.3.

Run the test (about **12 minutes**, including a 1-minute warm-up):

```bash
cat scripts/run_autoscale_test.sh
caffeinate -i scripts/run_autoscale_test.sh 2>&1 | tee results/m04/autoscale_console.log
```

What it does:

1. `kubectl apply -f k8s/hpa/`, scales to 1 replica, waits 60 s for the first metrics.
2. Starts `monitor.py --hpa`, which records `kubectl get hpa emi-web -n emi` every 15 s, plus pod and Mac CPU.
3. Phase 1: **10 req/s for 2 min**. Phase 2: **100 req/s for 5 min**. Phase 3: **10 req/s for 3 min**.
4. Writes `phases.csv` (start/end time of each phase), `hpa.csv`, `hpa_final.txt`, `hpa_describe.txt`.

Optional: watch it live in another window (**Cmd + N**):

```bash
kubectl get hpa emi-web -n emi -w
```

`TARGETS` climbs above `50%` early in phase 2 and `REPLICAS` goes 1 → 2 → … (up to 5), then falls during phase 3.

`results/m04/autoscale/hpa_describe.txt` has the HPA's **Events** (e.g. "New size: 3; reason: cpu resource utilization (percentage of request) above target"), which make good evidence for the report.

## Step 4.5 — Draw the graphs

```bash
python3 scripts/make_graphs.py
open results/graphs
```

`open` shows the folder in Finder, so you can look at the PNGs.

| Graph | Built from |
|---|---|
| Graph 1 | `results/m04/fixed/summary.csv` |
| Graph 2 | `results/m04/fixed/r3_rate100/pods.csv` (emi-web pods only). CPU % = millicores ÷ 100m request × 100, the same definition the HPA uses; it can go above 100% (up to 250%, the limit) |
| Graph 3 | `results/m04/autoscale/phases.csv` (rate) and `hpa.csv` (average CPU % and replicas) |

## Step 4.6 — Commit all raw results (task 5)

```bash
git add results/
git commit -m "Milestone 04: load tests, profiling CSVs, autoscaling test, graphs"
git push
```

### Milestone 04 done when
- [ ] `results/m04/fixed/summary.csv` has 15 rows
- [ ] Each `results/m04/fixed/r*_rate*/` has `httperf.txt`, `pods.csv`, `host_cpu.csv`
- [ ] `results/m04/autoscale/hpa.csv` shows replicas rising during the 100 req/s phase and falling afterwards
- [ ] `results/graphs/` has graph1, graph2, graph3
- [ ] Everything pushed

Next: [06-REPORT-AND-SUBMISSION.md](06-REPORT-AND-SUBMISSION.md)
