# Milestone 04 — Load Testing, Profiling and Autoscaling (25 marks)

## What the PDF asks

| # | Task | How we do it |
|---|---|---|
| 1 | **Workload**: every request is `POST /api/emi` with **random valid inputs** (so every request writes to MongoDB), sent only to `http://emi.local/` | `scripts/gen_wsesslog.py` creates random bodies for **httperf** |
| 2 | **Fixed replicas**: rates 10, 25, 50, 100, 200 req/s, 60 s each, at 1, 2 and 3 replicas = **15 runs**. Record average response time and error count | `scripts/run_fixed_experiments.sh` → `results/m04/fixed/summary.csv` |
| 3 | **Profiling**: during each run, `kubectl top pods -n emi` every **15 s** and host CPU every **1 s**, saved to CSV with a timestamp column, by a script you write | `scripts/monitor.py` → `pods.csv`, `host_cpu.csv` |
| 4 | **Autoscaling**: HPA (`autoscaling/v2`), min 1, max 5, 50% CPU. 10-minute test: 2 min @ 10 req/s, 5 min @ 100 req/s, 3 min @ 10 req/s. Record replicas every 15 s with `kubectl get hpa emi-web -n emi` | `k8s/hpa/emi-web-hpa.yaml` + `scripts/run_autoscale_test.sh` → `hpa.csv` |
| 5 | **Results**: all raw outputs in `results/` | everything below writes there |

> **On a Mac:** keep Docker Desktop and the `minikube tunnel` window (from Milestone 03) running the whole time. In every Terminal where you run these scripts, first run `cd ~/assignment4 && source .venv/bin/activate`. Stop the Mac from sleeping during long tests by prefixing them with `caffeinate -i`, e.g. `caffeinate -i scripts/run_fixed_experiments.sh 2>&1 | tee results/m04/fixed_runs_console.log`. tmux is optional. Host CPU is read with `psutil` instead of `/proc/stat`. Close other heavy apps during the tests, because the Mac itself is the host whose CPU you measure.

## Deliverables for Milestone 04 (graphs)

| Graph | Content | File |
|---|---|---|
| **Graph 1** | Average response time (ms) vs request rate, one line each for 1, 2, 3 replicas | `results/graphs/graph1_response_time_vs_rate.png` |
| **Graph 2** | CPU utilization (%) over time for each pod, 100 req/s run with 3 replicas | `results/graphs/graph2_pod_cpu_100rps_3replicas.png` |
| **Graph 3** | Autoscaling test: request rate, average CPU and number of replicas over the 10 minutes, shared time axis | `results/graphs/graph3_autoscaling.png` |

Also put the `summary.csv` table (15 rows: replicas, rate, avg response time, errors) in the report. It's the data behind Graph 1 and shows the error counts the PDF asks you to record.

---

## Why httperf (and not ab)

The PDF allows httperf or ApacheBench. **ab** sends the *same* request body every time, so it can't satisfy "random valid inputs". **httperf**'s `--wsesslog` mode reads a file of requests, and we generate that file with a different random loan for every request. httperf also sends at a **fixed rate** (`--rate`), which is exactly what "10, 25, 50, 100, 200 requests per second" means.

What one run does (`scripts/httperf_run.sh RATE SECONDS OUTFILE`):

```bash
python3 scripts/gen_wsesslog.py $((RATE*SECONDS)) sessions.txt    # one random POST per line
httperf --hog --server emi.local --port 80 --wsesslog=TOTAL,0,sessions.txt --rate RATE --timeout 5 \
        --add-header='Content-Type: application/x-www-form-urlencoded\n'
```

httperf's output contains the two numbers we need:

```text
Reply time [ms]: response 12.3 transfer 0.0      -> average response time = 12.3 ms
Errors: total 0 client-timo 0 ...                -> error count
Reply status: 1xx=0 2xx=600 3xx=0 4xx=0 5xx=0    -> 4xx/5xx are counted as errors too
```

## Before you start: use tmux so tests survive an SSH disconnect

The fixed runs take about **25 minutes** and the HPA test about **12 minutes**. If your SSH connection drops, a normal command would be killed. `tmux` keeps it running on the server.

**Run on: UBUNTU SERVER (inside SSH)**

```bash
sudo apt install -y tmux        # if not installed
tmux new -s m04                 # start a session named m04
```

- Detach (leave it running): press **Ctrl+B**, then **D**.
- Re-attach later (also after reconnecting SSH): `tmux attach -t m04`.

## Step 4.1 — Pre-flight checks

```bash
cd ~/assignment4
mkdir -p results/m04
kubectl top pods -n emi                        # metrics-server works (numbers, not an error)
kubectl get deploy emi-web -n emi              # image 1.0, 3/3 ready
curl -s http://emi.local/health                # Ingress reachable from the server
which httperf
scripts/httperf_run.sh 10 5 /tmp/smoke.txt     # 5-second smoke test at 10 req/s
```

The smoke test should print `2xx=50` and `Errors: total 0`.

If `kubectl top` says `Metrics API not available`, run `minikube addons enable metrics-server` and wait 1–2 minutes.

## Step 4.2 — Profiling script (task 3)

Read `scripts/monitor.py`. This is the "small script that saves both to CSV files with a timestamp column":

- **Thread 1, every 15 s:** runs `kubectl top pods -n emi` and writes `timestamp,pod,cpu_millicores,memory_mib` to `pods.csv`.
- **Thread 2, every 1 s:** reads host CPU (`/proc/stat` on Linux, the same counters `mpstat` uses; `psutil` on macOS) and writes the host's overall `timestamp,cpu_percent` to `host_cpu.csv`.
- **Thread 3 (with `--hpa`), every 15 s:** runs `kubectl get hpa emi-web -n emi` and writes replicas and CPU% to `hpa.csv`.

Try it for 20 seconds:

```bash
python3 scripts/monitor.py --out-dir /tmp/montest --duration 20
head /tmp/montest/pods.csv /tmp/montest/host_cpu.csv
```

You don't run it by hand for the experiments; the experiment scripts start and stop it around every run.

## Step 4.3 — The 15 fixed-replica runs (tasks 1–3)

```bash
cat scripts/run_fixed_experiments.sh
scripts/run_fixed_experiments.sh 2>&1 | tee results/m04/fixed_runs_console.log
```

What it does for each replica count (1, then 2, then 3):

1. Deletes any HPA (so nothing changes the replica count behind your back).
2. `kubectl scale deployment emi-web --replicas=N`, waits for the rollout, waits 15 s.
3. For each rate (10, 25, 50, 100, 200 req/s):
   - starts `monitor.py` (pods every 15 s, host every 1 s),
   - runs httperf for 60 s with random POST bodies,
   - stops the monitor,
   - writes one line to `results/m04/fixed/summary.csv`,
   - rests 15 s so the next run starts from a calm system.

Output layout:

```text
results/m04/fixed/
  summary.csv                    replicas,rate,avg_response_ms,errors,replies_2xx,run_dir
  r1_rate10/   httperf.txt  pods.csv  host_cpu.csv  pods_before.txt
  r1_rate25/   ...
  ...
  r3_rate200/  ...
```

When it finishes it prints the summary table. Look at it:

```bash
column -s, -t results/m04/fixed/summary.csv
```

**What to expect (and discuss in the report):**

- At low rates all replica counts are fast.
- With **1 replica**, one pod is capped at **250m CPU** (its limit). As the rate grows the pod saturates: response time rises sharply and at 100–200 req/s you'll probably see errors (timeouts / 5xx).
- With **2 and 3 replicas** the load is spread, so response time stays lower for longer.
- Every request also writes to MongoDB, so at the highest rates the database and the single Minikube node's CPU (see `host_cpu.csv`) can become the bottleneck too.

To repeat a single run (for example if one was disturbed), delete its line from `summary.csv` and run:

```bash
REPLICAS="3" RATES="100" scripts/run_fixed_experiments.sh
```

## Step 4.4 — Autoscaling test (task 4)

Look at the HPA manifest:

```bash
cat k8s/hpa/emi-web-hpa.yaml
```

- `scaleTargetRef`: the `emi-web` Deployment.
- `minReplicas: 1`, `maxReplicas: 5`.
- `averageUtilization: 50`: target 50% of the **CPU request** (100m), i.e. about 50m per pod on average. Above that the HPA adds pods; below it, it removes them.
- `behavior.scaleDown.stabilizationWindowSeconds: 60`: by default the HPA waits **5 minutes** before scaling down. With 60 s the scale-down is visible inside the 3-minute cool-down phase. Mention this setting in the report.
- It lives in `k8s/hpa/` (not `k8s/`) so it doesn't fight the manual `kubectl scale` commands in Milestones 02–03 and step 4.3.

Run the 10-minute test (inside tmux):

```bash
cat scripts/run_autoscale_test.sh
scripts/run_autoscale_test.sh 2>&1 | tee results/m04/autoscale_console.log
```

What it does:

1. `kubectl apply -f k8s/hpa/`, scales to 1 replica, waits 60 s for the first metrics.
2. Starts `monitor.py --hpa`, which records `kubectl get hpa emi-web -n emi` every 15 s (and pod/host CPU).
3. Phase 1: **10 req/s for 2 min**. Phase 2: **100 req/s for 5 min**. Phase 3: **10 req/s for 3 min**.
4. Writes `phases.csv` (exact start/end time of each phase), `hpa.csv`, `hpa_final.txt`, `hpa_describe.txt`.

Optional: watch it live from a **second SSH window**:

```bash
kubectl get hpa emi-web -n emi -w
```

You'll see `TARGETS` climb above `50%` early in phase 2, `REPLICAS` go 1 → 2 → … (up to 5), then fall back during phase 3.

`hpa_describe.txt` contains the HPA's **Events** ("New size: 3; reason: cpu resource utilization above target"), which are good evidence for the report.

## Step 4.5 — Draw the graphs

```bash
python3 scripts/make_graphs.py
ls results/graphs/
```

| Graph | Built from |
|---|---|
| Graph 1 | `results/m04/fixed/summary.csv` |
| Graph 2 | `results/m04/fixed/r3_rate100/pods.csv` (emi-web pods only). CPU % = millicores ÷ 100m request × 100, the same definition the HPA uses. Values above 100% are possible (up to 250%, the limit) |
| Graph 3 | `results/m04/autoscale/phases.csv` (rate), `hpa.csv` (average CPU % and replicas) |

To see the PNGs on your PC, copy them from the server.

**Run on: YOUR PC**

```bash
scp -r SERVER_USER@SERVER_IP:~/assignment4/results/graphs ./graphs
```

(or open them from the Git repository after you push).

## Step 4.6 — Commit all raw results (task 5)

```bash
git add results/
git commit -m "Milestone 04: load tests, profiling CSVs, autoscaling test, graphs"
git push
```

### Milestone 04 done when
- [ ] `results/m04/fixed/summary.csv` has 15 rows
- [ ] Each `results/m04/fixed/r*_rate*/` has `httperf.txt`, `pods.csv`, `host_cpu.csv`
- [ ] `results/m04/autoscale/hpa.csv` shows replicas going up during the 100 req/s phase and down afterwards
- [ ] `results/graphs/` has graph1, graph2, graph3
- [ ] Everything pushed

Next: [06-REPORT-AND-SUBMISSION.md](06-REPORT-AND-SUBMISSION.md)
