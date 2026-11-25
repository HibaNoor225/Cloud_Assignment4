#!/usr/bin/env python3
"""Builds the Assignment 4 report from everything in results/.

Writes report/Assignment4_Report.html (self-contained: images embedded) and, when
Google Chrome / Chromium / Edge is installed, report/Assignment4_Report.pdf.
Anything that is still missing shows up as a red box in the report and is listed
in report/MISSING.txt, so you can add it and simply run the script again.

Usage: python3 scripts/build_report.py --name "Your Name" --roll "Roll No"
"""
import argparse
import base64
import csv
import glob
import html
import os
import re
import shutil
import statistics
import subprocess
from collections import defaultdict
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
OUT_DIR = os.path.join(ROOT, "report")
REPO_URL = "https://github.com/HibaNoor225/Cloud_Assignment4"
REPLICAS = [1, 2, 3]
RATES = [10, 25, 50, 100, 200]
CPU_REQUEST_M = 100
CPU_LIMIT_M = 250

missing = []
used_images = set()


# ---------------------------------------------------------------- helpers

def path(rel):
    return os.path.join(ROOT, rel)


def read(rel):
    p = path(rel)
    if not os.path.isfile(p):
        return None
    with open(p, errors="replace") as f:
        return f.read()


def read_csv(rel):
    p = path(rel)
    if not os.path.isfile(p):
        return None
    with open(p, newline="", errors="replace") as f:
        return list(csv.DictReader(f))


def esc(s):
    return html.escape(str(s))


def fnum(value, digits=1):
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "–"


def miss(what, rel):
    missing.append(f"{what}  ->  {rel}")
    return (f'<div class="missing"><b>MISSING:</b> {esc(what)}<br>'
            f'Add <code>{esc(rel)}</code> and run <code>python3 scripts/build_report.py</code> again.</div>')


def trim(text, max_lines):
    lines = text.rstrip("\n").splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines)
    head = max_lines * 2 // 3
    tail = max_lines - head
    cut = len(lines) - head - tail
    return "\n".join(lines[:head] + [f"... ({cut} lines trimmed, full file in the repository) ..."] + lines[-tail:])


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def pre(text, max_lines=60):
    return f"<pre>{esc(trim(strip_ansi(text), max_lines))}</pre>"


def file_block(rel, what, max_lines=60, transform=None):
    text = read(rel)
    if text is None or not text.strip():
        return miss(what, rel)
    if transform:
        text = transform(text)
    return f'<p class="src">{esc(what)} (<code>{esc(rel)}</code>)</p>' + pre(text, max_lines)


def code_file(rel, max_lines=400):
    text = read(rel)
    if text is None:
        return miss(rel, rel)
    return f'<p class="src"><code>{esc(rel)}</code></p>' + pre(text, max_lines)


def find_image(candidates, keywords=()):
    for rel in candidates:
        if os.path.isfile(path(rel)):
            return rel
    shots = sorted(glob.glob(os.path.join(RES, "screenshots", "*")))
    for kw in keywords:
        for p in shots:
            if kw.lower() in os.path.basename(p).lower() and os.path.relpath(p, ROOT) not in used_images:
                return os.path.relpath(p, ROOT)
    return None


def img(candidates, caption, keywords=()):
    if isinstance(candidates, str):
        candidates = [candidates]
    rel = find_image(candidates, keywords)
    if not rel:
        return miss(caption, candidates[0])
    used_images.add(rel)
    ext = os.path.splitext(rel)[1].lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(ext, "png")
    with open(path(rel), "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return (f'<figure><img src="data:image/{mime};base64,{data}" alt="{esc(caption)}">'
            f"<figcaption>{esc(caption)} (<code>{esc(rel)}</code>)</figcaption></figure>")


def table(headers, rows, cls=""):
    out = [f'<table class="{cls}"><tr>' + "".join(f"<th>{esc(h)}</th>" for h in headers) + "</tr>"]
    for r in rows:
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
    out.append("</table>")
    return "".join(out)


def ts(value):
    return datetime.fromisoformat(value.strip())


# ---------------------------------------------------------------- data

def summary_runs():
    rows = read_csv("results/m04/fixed/summary.csv") or []
    runs = {}
    for r in rows:
        try:
            runs[(int(r["replicas"]), int(r["rate"]))] = r
        except (KeyError, ValueError):
            continue
    return runs


def httperf_stats(rel):
    text = read(rel) or ""
    stats = {}
    m = re.search(r"Request rate: ([0-9.]+) req/s", text)
    if m:
        stats["achieved"] = float(m.group(1))
    m = re.search(r"Reply time \[ms\]: response ([0-9.]+) transfer ([0-9.]+)", text)
    if m:
        stats["avg_ms"] = float(m.group(1)) + float(m.group(2))
    m = re.search(r"Errors: total (\d+) client-timo (\d+) socket-timo (\d+) connrefused (\d+) connreset (\d+)", text)
    if m:
        stats["errors"] = [int(x) for x in m.groups()]
    m = re.search(r"2xx=(\d+) 3xx=(\d+) 4xx=(\d+) 5xx=(\d+)", text)
    if m:
        stats["status"] = [int(x) for x in m.groups()]
    return stats


def profile(run_dir):
    """Average/max web-pod CPU and memory, MongoDB CPU and host CPU for one run."""
    res = {}
    pods = read_csv(os.path.join(run_dir, "pods.csv")) or []
    web = [r for r in pods if r.get("pod", "").startswith("emi-web")]
    if web:
        cpu = [float(r["cpu_millicores"]) for r in web]
        mem = [float(r["memory_mib"]) for r in web]
        res["web_cpu_avg"] = statistics.mean(cpu)
        res["web_cpu_max"] = max(cpu)
        res["web_mem_avg"] = statistics.mean(mem)
        res["web_pods"] = len({r["pod"] for r in web})
    mongo = defaultdict(float)
    for r in pods:
        if r.get("pod", "").startswith("mongo-") and not r["pod"].startswith("mongo-init"):
            mongo[r["timestamp"]] += float(r["cpu_millicores"])
    if mongo:
        res["mongo_cpu_avg"] = statistics.mean(mongo.values())
    host = read_csv(os.path.join(run_dir, "host_cpu.csv")) or []
    vals = [float(r["cpu_percent"]) for r in host if r.get("cpu_percent")]
    if vals:
        res["host_avg"] = statistics.mean(vals)
        res["host_max"] = max(vals)
    return res


def distribution(rel):
    text = read(rel)
    if not text:
        return None
    rows, on = [], False
    for line in text.splitlines():
        if line.startswith("POD"):
            on = True
            continue
        if on:
            if not line.strip():
                break
            parts = line.split()
            if len(parts) >= 2 and parts[-1].isdigit():
                rows.append((parts[0], int(parts[-1])))
    return rows


def loop_summary(rel):
    text = read(rel)
    if not text:
        return None
    m = re.findall(r"SUMMARY: total=(\d+) ok=(\d+) failed=(\d+)", text)
    if m:
        return tuple(int(x) for x in m[-1])
    ok = len(re.findall(r" OK ", text))
    fail = len(re.findall(r" FAIL ", text))
    return (ok + fail, ok, fail) if ok + fail else None


def primary(rel):
    text = read(rel) or ""
    m = re.search(r"PRIMARY pod:\s*(\S+)", text)
    return m.group(1) if m else None


# ---------------------------------------------------------------- sections

def sec_environment():
    return ("<h2>0. Environment</h2>"
            "<p>All parts of the assignment were run on one machine: Docker Desktop provides the container "
            "runtime, Minikube runs a single-node Kubernetes cluster with the Docker driver (profile <code>emi</code>), "
            "and the NGINX Ingress controller and metrics-server are Minikube add-ons. Because the Docker driver on "
            "macOS does not expose the node IP to the host, the Ingress is reached through <code>minikube tunnel</code> "
            "with <code>127.0.0.1 emi.local</code> in <code>/etc/hosts</code>, as the assignment describes for macOS.</p>"
            + file_block("results/environment.txt", "Machine and tool versions", 40))


def sec_m01():
    s = ["<h2>1. Milestone 01: Loan EMI Calculator with MongoDB</h2>",
         "<h3>1.1 Design</h3>",
         "<p>The calculator is a Node.js/Express server (<code>app/server.js</code>) serving a single page built with "
         "HTML, Bootstrap 5 and jQuery (<code>app/public/</code>). The form has three inputs: loan amount <i>P</i>, "
         "annual interest rate (%) and tenure in months <i>n</i>. On submit, jQuery stops the normal form post "
         "(<code>preventDefault</code>) and sends the values with <code>$.ajax</code>. Only the result panel and the "
         "history table are redrawn, so there is no postback.</p>",
         table(["Endpoint", "Behaviour"], [
             ["<code>POST /api/emi</code>", "Validates P, rate, n; returns EMI, total payment, total interest, "
              "<code>servedBy</code> (pod name from <code>HOSTNAME</code>) and <code>podIp</code>; stores the calculation"],
             ["<code>GET /api/history</code>", "Last 10 calculations from MongoDB, newest first "
              "(<code>sort({createdAt:-1}).limit(10)</code>)"],
             ["<code>GET /health</code>", "Pings MongoDB: <b>200</b> when reachable, <b>503</b> otherwise; "
              "used as readiness and liveness probe"],
             ["<code>GET /api/version</code>", "Image version shown in the footer (used for the rolling update)"],
         ]),
         "<h3>1.2 Formula, validation, storage and configuration</h3>",
         "<p class='formula'>EMI = P · r · (1 + r)<sup>n</sup> / ((1 + r)<sup>n</sup> − 1), &nbsp; r = annual rate ÷ 12 ÷ 100</p>",
         "<ul>"
         "<li><b>Validation</b> happens twice. In the browser, HTML5 <code>required</code>/<code>min</code> attributes and "
         "jQuery checks reject empty, zero or negative values before any request is sent. On the server, "
         "<code>validate()</code> in <code>app/emi.js</code> accepts only positive numbers (and whole months) and "
         "otherwise answers <b>HTTP 400</b> with the error messages.</li>"
         "<li><b>Storage:</b> each calculation is inserted into the collection <code>calculations</code> with the fields "
         "<code>principal, rate, months, emi, servedBy, createdAt</code>.</li>"
         "<li><b>Configuration:</b> the connection string is read only from the <code>MONGO_URL</code> environment "
         "variable, and the server refuses to start without it. The source code contains no host names, IP addresses or passwords.</li>"
         "</ul>",
         "<p>Check for the required input: P = 500000, rate = 12%, n = 24 gives r = 0.01, so "
         "EMI = 500000 · 0.01 · 1.01<sup>24</sup> / (1.01<sup>24</sup> − 1) = <b>23,536.74</b>, total payment "
         "564,881.67 and total interest 64,881.67.</p>",
         "<h3>1.3 Screenshot: P = 500000, rate = 12%, n = 24 with the history table</h3>",
         img(["results/screenshots/m01_ui_500000_12_24.png"], "UI with the result for P=500000, 12%, 24 months and the history table",
             ("m01", "500000")),
         file_block("results/m01/api_test.txt", "Local API test", 30),
         file_block("results/m01/mongo_documents.txt", "Documents stored in MongoDB", 30),
         file_block("results/m01/health_check.txt", "/health with MongoDB stopped (expected HTTP 503)", 10),
         "<h3>1.4 Source code</h3>",
         f'<p>Git repository: <a href="{REPO_URL}">{REPO_URL}</a>. The server code is in <code>app/server.js</code> '
         "and <code>app/emi.js</code> (also listed in Appendix C).</p>"]
    return "".join(s)


def sec_m02():
    manifests = [
        ["00-namespace.yaml", "Namespace <code>emi</code>", "Keeps all objects of the assignment together"],
        ["01-mongo-service.yaml", "Service <code>mongo</code> (headless, <code>clusterIP: None</code>)",
         "Stable DNS names <code>mongo-0.mongo</code> … for each member; <code>publishNotReadyAddresses</code> so members find each other before they are Ready"],
        ["02-mongo-statefulset.yaml", "StatefulSet <code>mongo</code>, 3 replicas, <code>mongo:7.0</code>",
         "<code>--replSet rs0 --bind_ip_all</code>; <code>volumeClaimTemplates</code> give each pod its own 1Gi PVC from <code>standard</code>"],
        ["03-mongo-init-job.yaml", "Job <code>mongo-init</code>",
         "Waits for all three members, runs <code>rs.initiate()</code> on <code>mongo-0.mongo</code>, waits for a PRIMARY and prints <code>rs.status()</code>"],
        ["04-configmap.yaml", "ConfigMap <code>emi-config</code>",
         "<code>MONGO_URL</code> for the replica set; no credentials, so a ConfigMap rather than a Secret"],
        ["05-web-deployment.yaml", "Deployment <code>emi-web</code>, 3 replicas",
         "Image <code>emi-web:1.0</code>, <code>IfNotPresent</code>; readiness + liveness on <code>/health</code>; requests 100m/128Mi, limits 250m/256Mi; rolling update with maxSurge 1, maxUnavailable 0"],
        ["06-web-service.yaml", "Service <code>emi-web</code> (ClusterIP)", "Port 80 to container port 3000, spreads traffic over Ready pods"],
        ["07-ingress.yaml", "Ingress <code>emi-web</code>", "<code>ingressClassName: nginx</code>, host <code>emi.local</code>, <code>/</code> to <code>emi-web:80</code>"],
        ["hpa/emi-web-hpa.yaml", "HPA <code>emi-web</code> (autoscaling/v2)", "1–5 replicas at 50% average CPU (Milestone 04)"],
    ]
    s = ["<h2>2. Milestone 02: MongoDB and the Web App on Minikube</h2>",
         "<h3>2.1 Container image</h3>",
         "<p>The image is built from the official <code>node:20-alpine</code> base. Only production dependencies are "
         "installed with <code>npm ci --omit=dev</code>, and the app runs as the unprivileged <code>node</code> user "
         "(uid 1000) that the official image provides. The <code>.dockerignore</code> keeps <code>node_modules</code>, tests "
         "and Git data out of the build context. The image was built as <code>emi-web:1.0</code> and copied into the "
         "cluster with <code>minikube image load emi-web:1.0</code>. Because the Deployment uses "
         "<code>imagePullPolicy: IfNotPresent</code>, Kubernetes uses that local copy instead of pulling from a registry.</p>",
         code_file("app/Dockerfile"), code_file("app/.dockerignore"),
         file_block("results/m02/image.txt", "Image check (image list, whoami = node, image inside Minikube)", 20),
         "<h3>2.2 Manifests</h3>",
         "<p>All manifests are in <code>k8s/</code> and are applied with <code>kubectl apply -f k8s/</code>. The full YAML is in Appendix A.</p>",
         table(["File", "Object", "Purpose"], [[f"<code>{a}</code>", b, c] for a, b, c in manifests]),
         "<h3>2.3 All objects Running and Ready</h3>",
         file_block("results/m02/get_all.txt", "kubectl get all,pvc,configmap -n emi -o wide", 70),
         "<h3>2.4 Replica set initiation</h3>",
         "<p>The Job <code>mongo-init</code> waits until <code>mongo-0.mongo</code>, <code>mongo-1.mongo</code> and "
         "<code>mongo-2.mongo</code> answer a ping, then calls <code>rs.initiate()</code> with the three members. "
         "<code>rs.status()</code> shows one PRIMARY and two SECONDARY members.</p>",
         file_block("results/m02/mongo_init_job.log", "kubectl logs job/mongo-init -n emi", 40),
         file_block("results/m02/rs_status.txt", "rs.status() trimmed to member names and states", 20),
         "<h3>2.5 App through the port-forward</h3>",
         "<p><code>kubectl port-forward svc/emi-web 8080:80 -n emi</code>, then <code>http://localhost:8080</code>. "
         "After a few calculations, the history table shows them, read back from MongoDB.</p>",
         img(["results/screenshots/m02_portforward_app.png"], "App through the port-forward with the history table",
             ("m02", "port")),
         "<h3>2.6 Persistence test</h3>",
         "<p><code>mongo-1</code> was deleted with <code>kubectl delete pod</code>. The StatefulSet re-created it with the "
         "<b>same name</b> (new UID and a young age) and attached the <b>same PVC</b> <code>data-mongo-1</code>, which "
         "stayed <code>Bound</code> the whole time. The number of documents in <code>calculations</code> is the same before and "
         "after, so no data was lost. This works because the data lives on the PersistentVolume, not in the container, and a "
         "StatefulSet always binds pod <i>N</i> to its PVC <code>data-mongo-N</code>.</p>",
         file_block("results/m02/persistence_test.txt", "Persistence test (pods, PVCs, document counts before and after)", 90)]
    return "".join(s)


def sec_m03():
    d3 = distribution("results/m03/distribution_3_replicas.txt")
    d5 = distribution("results/m03/distribution_5_replicas.txt")
    s = ["<h2>3. Milestone 03: Ingress, Load Balancing and Self-Healing</h2>",
         "<h3>3.1 Ingress</h3>",
         "<p>The Ingress uses <code>ingressClassName: nginx</code> and routes host <code>emi.local</code>, path <code>/</code>, "
         "to the <code>emi-web</code> Service. With the Docker driver on macOS, <code>minikube tunnel</code> exposes the "
         "ingress controller on 127.0.0.1, and <code>/etc/hosts</code> maps <code>emi.local</code> to it.</p>",
         code_file("k8s/07-ingress.yaml"),
         img(["results/screenshots/m03_emi_local.png"], "App at http://emi.local", ("m03_emi", "emi_local", "emi.local")),
         "<h3>3.2 Load distribution (30 requests each)</h3>"]
    if d3 or d5:
        def tbl(d, label):
            if not d:
                return miss(f"Requests per pod, {label}", f"results/m03/distribution_{label.split()[0]}_replicas.txt")
            total = sum(n for _, n in d)
            rows = [[f"<code>{esc(p)}</code>", n, f"{100 * n / total:.0f}%"] for p, n in d]
            rows.append(["<b>Total</b>", f"<b>{total}</b>", ""])
            return f"<p><b>{label}</b></p>" + table(["Pod", "Requests", "Share"], rows)
        s.append('<div class="cols"><div>' + tbl(d3, "3 replicas") + "</div><div>" + tbl(d5, "5 replicas") + "</div></div>")
        notes = []
        if d3:
            notes.append(f"With 3 replicas, the 30 requests went to {len(d3)} pods "
                         f"(between {min(n for _, n in d3)} and {max(n for _, n in d3)} each).")
        if d5:
            notes.append(f"With 5 replicas, they went to {len(d5)} pods "
                         f"(between {min(n for _, n in d5)} and {max(n for _, n in d5)} each).")
        s.append("<p>" + " ".join(notes) + " The NGINX Ingress controller balances across the Ready endpoints of the "
                 "Service, so every Ready pod receives traffic. The split is not perfectly equal because 30 requests "
                 "is a small sample, and NGINX keeps upstream connections alive, which affects which pod gets the next request.</p>")
    else:
        s.append(miss("Requests-per-pod tables (3 and 5 replicas)", "results/m03/distribution_3_replicas.txt"))
    s += ["<h3>3.3 Scaling by hand to 5 replicas</h3>",
          "<p><code>kubectl scale deployment emi-web --replicas=5 -n emi</code>. The two new pods appear first as "
          "<code>0/1 Running</code>. The Service adds a pod to its endpoints only after the readiness probe on "
          "<code>/health</code> succeeds, so the new pods receive no requests until they show <code>1/1</code> Ready.</p>",
          file_block("results/m03/scale_watch.txt", "kubectl get pods -w during the scale-up", 40),
          file_block("results/m03/distribution_5_replicas_during_scaleup.txt", "Requests sent while the new pods were starting", 30,
                     lambda t: t.split("Raw log:")[0]),
          "<h3>3.4 Self-healing: deleting a web pod</h3>",
          "<p>One <code>emi-web</code> pod was deleted while a request loop ran through the Ingress. The Deployment's "
          "ReplicaSet saw only 2 of 3 desired pods and created a replacement right away. The Service had already removed the "
          "terminating pod (the <code>preStop</code> sleep gives it time), so the remaining pods kept answering.</p>",
          file_block("results/m03/selfheal_web_watch.txt", "kubectl get pods -n emi -w during the web-pod deletion", 40)]
    lp = loop_summary("results/m03/selfheal_web_loop.log")
    if lp:
        s.append(f"<p>Request loop during the web-pod deletion: <b>total {lp[0]}, ok {lp[1]}, failed {lp[2]}</b>.</p>")
    pb, pa = primary("results/m03/mongo_before.txt"), primary("results/m03/mongo_after.txt")
    s += ["<h3>3.5 Self-healing: deleting the MongoDB PRIMARY</h3>",
          "<p>" + (f"Before the test, <b>{esc(pb)}</b> was PRIMARY. " if pb else "") +
          "Deleting the PRIMARY pod triggers an election among the remaining members. "
          + (f"Afterwards, <b>{esc(pa)}</b> was PRIMARY. " if pa else "") +
          "The StatefulSet re-created the deleted pod with the same name and PVC, and it rejoined as a SECONDARY. The "
          "MongoDB driver in the web pods follows the new PRIMARY automatically through the replica-set connection string. "
          "Requests can fail only during the few seconds of the election; after that, calculations are saved again.</p>",
          file_block("results/m03/mongo_before.txt", "Replica set before", 10),
          file_block("results/m03/selfheal_mongo_watch.txt", "kubectl get pods -w during the PRIMARY deletion", 40),
          file_block("results/m03/mongo_after.txt", "Replica set after (new PRIMARY)", 10)]
    lp = loop_summary("results/m03/selfheal_mongo_loop.log")
    if lp:
        s.append(f"<p>Request loop during the PRIMARY deletion: <b>total {lp[0]}, ok {lp[1]}, failed {lp[2]}</b>"
                 + (" (the failures fall inside the election window)." if lp[2] else ".") + "</p>")
    s += ["<h3>3.6 Rolling update to 1.1 and rollback</h3>",
          "<p>The footer version was changed, <code>emi-web:1.1</code> was built with "
          "<code>--build-arg APP_VERSION=1.1</code> and loaded with <code>minikube image load</code>, and the Deployment was "
          "updated with <code>kubectl set image deployment/emi-web web=emi-web:1.1 -n emi</code> while a request loop "
          "ran. With <code>maxSurge: 1</code> and <code>maxUnavailable: 0</code>, Kubernetes starts one new pod and removes an old "
          "pod only after the new one is Ready. Together with the readiness probe and the <code>preStop</code> delay, the "
          "number of serving pods never drops below 3, so no request fails. <code>kubectl rollout undo</code> then returned "
          "to 1.0 in the same way.</p>",
          img(["results/screenshots/m03_version_1_1.png"], "Footer showing version 1.1 after the update",
              ("1_1", "1.1", "version", "Screenshot_2"))]
    s.append(file_block("results/m03/rollout.txt", "kubectl rollout status and kubectl rollout history", 40))
    for rel, label in (("results/m03/rolling_update_loop.log", "update to 1.1"),
                       ("results/m03/rollback_loop.log", "rollback to 1.0")):
        lp = loop_summary(rel)
        if lp:
            s.append(f"<p>Request loop during the {label}: <b>total {lp[0]}, ok {lp[1]}, failed {lp[2]}</b>.</p>")
        if read(rel) or rel.endswith("rolling_update_loop.log"):
            s.append(file_block(rel, f"Request loop log, {label}", 30))
    return "".join(s)


def sec_m04():
    runs = summary_runs()
    s = ["<h2>4. Milestone 04: Load Testing, Profiling and Autoscaling</h2>",
         "<h3>4.1 Method</h3>",
         "<ul>"
         "<li><b>Load generator:</b> <code>httperf</code> on the host, sending traffic only to <code>http://emi.local/</code>. "
         "Every request is a <code>POST /api/emi</code> with random valid inputs (P from 50,000 to 5,000,000, rate from 1 to 25%, "
         "n from 6 to 360) generated by <code>scripts/gen_wsesslog.py</code>, so every request also writes one document to MongoDB.</li>"
         "<li>httperf runs in session mode: each session sends 10 requests over one persistent connection, and sessions "
         "start at rate ÷ 10 per second. The request rate is exactly the target rate, but <code>minikube tunnel</code> on macOS "
         "has to accept 10× fewer new connections. With one connection per request, the tunnel, not the "
         "application, became the bottleneck. The client timeout is 5 s.</li>"
         "<li><b>Fixed replicas:</b> 10, 25, 50, 100 and 200 req/s, 60 s each, with <code>emi-web</code> fixed at 1, 2 and 3 "
         "replicas (15 runs, <code>scripts/run_fixed_experiments.sh</code>). Any HPA is removed first, so the replica count stays fixed.</li>"
         "<li><b>Profiling:</b> <code>scripts/monitor.py</code> records <code>kubectl top pods -n emi</code> every 15 s "
         "(<code>pods.csv</code>) and the host's overall CPU every 1 s (<code>host_cpu.csv</code>), both with a timestamp column.</li>"
         "<li>CPU utilization is given as a percentage of the pod's CPU request (100m), the same definition the HPA uses, "
         "so a pod at its 250m limit shows 250%.</li>"
         "</ul>",
         "<h3>4.2 Results of the 15 fixed-replica runs</h3>"]
    if not runs:
        s.append(miss("Fixed-replica summary", "results/m04/fixed/summary.csv"))
    else:
        rows = []
        for rep in REPLICAS:
            for rate in RATES:
                r = runs.get((rep, rate))
                run_dir = f"results/m04/fixed/r{rep}_rate{rate}"
                if not r:
                    missing.append(f"Fixed run replicas={rep} rate={rate}  ->  {run_dir}/ (REPLICAS=\"{rep}\" RATES=\"{rate}\" scripts/run_fixed_experiments.sh)")
                    rows.append([rep, rate, '<span class="red">not run</span>', "", "", "", "", ""])
                    continue
                hs = httperf_stats(f"{run_dir}/httperf.txt")
                pr = profile(run_dir)
                expected = rate * 60
                ok = int(r.get("replies_2xx") or 0)
                rows.append([rep, rate, fnum(hs.get("achieved")), f"<b>{fnum(r['avg_response_ms'])}</b>", r["errors"],
                             f"{ok} / {expected}",
                             f"{fnum(pr.get('web_cpu_avg'), 0)} / {fnum(pr.get('web_cpu_max'), 0)}",
                             fnum(pr.get("host_avg"))])
        s.append(table(["Replicas", "Target req/s", "Achieved req/s", "Avg response (ms)", "Errors",
                        "2xx replies / sent", "Web pod CPU avg / max (m)", "Host CPU avg (%)"], rows, "num"))
        s.append("<p class='src'>Average response time = httperf <i>reply time</i> (response + transfer). Errors = httperf "
                 "errors (client timeouts, socket timeouts, refused and reset connections) + HTTP 4xx/5xx. Raw output of each run: "
                 "<code>results/m04/fixed/r&lt;replicas&gt;_rate&lt;rate&gt;/</code>.</p>")
        skipped = read("results/m04/fixed/skipped.txt")
        if skipped:
            s.append("<p class='red'>Runs that httperf could not finish on macOS (they stalled 3 times at that rate): "
                     + esc(", ".join(re.findall(r"replicas=\d+ rate=\d+", skipped))) + ".</p>")
    s += ["<h3>4.3 Graph 1: average response time vs request rate</h3>",
          img("results/graphs/graph1_response_time_vs_rate.png", "Graph 1: average response time vs request rate (1, 2, 3 replicas)"),
          discuss_graph1(runs),
          "<h3>4.4 Graph 2: per-pod CPU, 100 req/s with 3 replicas</h3>",
          img("results/graphs/graph2_pod_cpu_100rps_3replicas.png", "Graph 2: CPU utilization per pod, 100 req/s, 3 replicas"),
          discuss_graph2(),
          "<h3>4.5 Autoscaling</h3>",
          "<p>The HorizontalPodAutoscaler (<code>autoscaling/v2</code>) targets the <code>emi-web</code> Deployment with "
          "<code>minReplicas: 1</code>, <code>maxReplicas: 5</code> and 50% average CPU utilization. It computes "
          "<i>desired = ceil(current × currentUtilization ÷ 50%)</i> from metrics-server data. The scale-down stabilization "
          "window is set to 60 s (default 300 s) so that the scale-down is visible inside the 3-minute cool-down phase. "
          "The test starts from 1 replica and runs 2 min at 10 req/s, 5 min at 100 req/s and 3 min at 10 req/s, "
          "recording <code>kubectl get hpa emi-web -n emi</code> every 15 s.</p>",
          code_file("k8s/hpa/emi-web-hpa.yaml"),
          img("results/graphs/graph3_autoscaling.png", "Graph 3: request rate, average CPU and number of replicas during the autoscaling test"),
          discuss_graph3(),
          file_block("results/m04/autoscale/hpa.csv", "HPA every 15 s (hpa.csv)", 50),
          file_block("results/m04/autoscale/hpa_describe.txt", "kubectl describe hpa (events)", 40,
                     lambda t: t[t.find("Events:"):] if "Events:" in t else t),
          "<h3>4.6 Bottlenecks</h3>", discuss_bottlenecks(runs)]
    return "".join(s)


def series(runs, rep):
    return [(rate, float(runs[(rep, rate)]["avg_response_ms"]), int(runs[(rep, rate)]["errors"] or 0))
            for rate in RATES if (rep, rate) in runs]


def discuss_graph1(runs):
    if not runs:
        return ""
    parts = []
    for rep in REPLICAS:
        pts = series(runs, rep)
        if not pts:
            continue
        low = [ms for rate, ms, _ in pts if rate <= 50]
        last_rate, last_ms, last_err = pts[-1]
        txt = (f"With <b>{rep} replica{'s' if rep > 1 else ''}</b>, the average response time is "
               f"{min(ms for _, ms, _ in pts):.1f}–{max(low) if low else last_ms:.1f} ms up to 50 req/s and "
               f"{last_ms:.1f} ms at {last_rate} req/s")
        txt += f" with {last_err} errors." if last_err else " with no errors."
        prof = profile(f"results/m04/fixed/r{rep}_rate{last_rate}")
        if "web_cpu_max" in prof:
            txt += (f" At that rate, the web pods averaged {prof['web_cpu_avg']:.0f}m CPU (peak {prof['web_cpu_max']:.0f}m, "
                    f"limit {CPU_LIMIT_M}m).")
        parts.append(txt)
    out = "<p>" + " ".join(parts) + "</p>"
    a = {rate: ms for rate, ms, _ in series(runs, 1)}
    b = {rate: ms for rate, ms, _ in series(runs, 3)}
    common = sorted(set(a) & set(b))
    if common:
        rate = common[-1]
        r1, r3 = a[rate], b[rate]
        if r1 > r3 * 1.2:
            out += (f"<p>At {rate} req/s, 3 replicas answer in {r3:.1f} ms instead of {r1:.1f} ms with 1 replica, "
                    f"{r1 / r3:.1f}× faster. With more replicas, each pod handles a smaller share of the requests and "
                    "stays further below its CPU limit.</p>")
        else:
            out += (f"<p>At {rate} req/s, 1 replica ({r1:.1f} ms) and 3 replicas ({r3:.1f} ms) are close. The single pod "
                    "still had CPU headroom at this rate, so adding replicas mainly adds spare capacity; the remaining "
                    "latency comes from the shared path (tunnel, Ingress, MongoDB write to the PRIMARY).</p>")
    out += ("<p>At low rates, every configuration is far from saturation, and the response time (a few milliseconds) is "
            "the cost of the Ingress hop plus one MongoDB insert acknowledged by the PRIMARY. Response time grows when a pod "
            "approaches its 250m CPU limit: the kernel's CFS quota throttles the Node.js process, requests queue up, and "
            "latency rises before errors appear. Spreading the same rate over more pods keeps each one below that point.</p>")
    return out


def discuss_graph2():
    rows = read_csv("results/m04/fixed/r3_rate100/pods.csv")
    if not rows:
        return ""
    per = defaultdict(list)
    for r in rows:
        if r["pod"].startswith("emi-web"):
            per[r["pod"]].append(100 * float(r["cpu_millicores"]) / CPU_REQUEST_M)
    if not per:
        return ""
    means = {p: statistics.mean(v) for p, v in per.items()}
    lo, hi = min(means.values()), max(means.values())
    avg = statistics.mean(means.values())
    even = (hi - lo) <= 0.25 * avg if avg else True
    lst = ", ".join(f"<code>{esc(p)}</code> {m:.0f}%" for p, m in sorted(means.items()))
    return (f"<p>Average CPU per pod during the run: {lst} (overall mean {avg:.0f}% of the 100m request, i.e. about "
            f"{avg * CPU_REQUEST_M / 100:.0f}m per pod). "
            + ("The three curves are close together, so the Service/Ingress spreads the load evenly over the pods. "
               if even else
               "The pods are not loaded equally. With persistent connections, NGINX keeps sending a connection's requests "
               "to the same upstream pod, so the split depends on how connections were assigned. ")
            + ("The pods stay above the HPA's 50% target, which is why the HPA adds pods at this rate in the autoscaling test. "
               if avg > 50 else "")
            + "The first sample can be lower because the load starts between two <code>kubectl top</code> readings, "
            "and metrics-server reports a moving average.</p>")


def discuss_graph3():
    hpa = read_csv("results/m04/autoscale/hpa.csv")
    phases = read_csv("results/m04/autoscale/phases.csv")
    if not hpa or not phases:
        return ""
    t0 = ts(phases[0]["start"])
    pts = []
    for r in hpa:
        try:
            x = (ts(r["timestamp"]) - t0).total_seconds() / 60
            rep = int(r["current_replicas"]) if r["current_replicas"] else None
            cpu = float(r["cpu_utilization_percent"]) if r["cpu_utilization_percent"] else None
        except ValueError:
            continue
        if x >= 0:
            pts.append((x, rep, cpu))
    if not pts:
        return ""
    peak = next((p for p in phases if p["phase"].startswith("2")), None)
    cool = next((p for p in phases if p["phase"].startswith("3")), None)
    reps = [r for _, r, _ in pts if r is not None]
    cpus = [c for _, _, c in pts if c is not None]
    max_rep = max(reps) if reps else None
    out = [f"Before the peak, the deployment ran with {reps[0] if reps else '?'} replica(s)."]
    if peak:
        ps = (ts(peak["start"]) - t0).total_seconds() / 60
        up = next((x for x, r, _ in pts if x >= ps and r and reps and r > reps[0]), None)
        top = next((x for x, r, _ in pts if r == max_rep and x >= ps), None)
        if up is not None:
            out.append(f"The peak (100 req/s) started at minute {ps:.1f}; the first scale-up shows at minute {up:.1f} "
                       f"({(up - ps) * 60:.0f} s later), and the deployment reached its maximum of {max_rep} replicas at "
                       f"minute {top:.1f}.")
        else:
            out.append("The replica count did not rise during the peak.")
    if cpus:
        out.append(f"Average CPU utilization reached {max(cpus):.0f}% of the request at its highest; adding pods brought it "
                   "back towards the 50% target.")
    if cool:
        cs = (ts(cool["start"]) - t0).total_seconds() / 60
        down = next((x for x, r, _ in pts if x >= cs and r is not None and max_rep and r < max_rep), None)
        final = reps[-1] if reps else None
        if down is not None:
            out.append(f"After the load dropped to 10 req/s at minute {cs:.1f}, the first scale-down came at minute "
                       f"{down:.1f}, and the test ended with {final} replica(s).")
        else:
            out.append(f"During the 3-minute cool-down, the count stayed at {final} replica(s).")
    out.append("The delays are expected. metrics-server reports CPU averaged over its scrape window (about 15–60 s), "
               "the HPA checks every 15 s, new pods first have to pass the readiness probe, and scale-down waits for the "
               "stabilization window so that a short dip does not remove pods.")
    return "<p>" + " ".join(out) + "</p>"


def discuss_bottlenecks(runs):
    txt = ["<ul>",
           "<li><b>Web pod CPU limit (250m):</b> each Node.js pod is single-threaded and capped at a quarter of a core. "
           "This is the first limit reached with 1 replica, and the reason extra replicas or the HPA help.</li>",
           "<li><b>MongoDB writes:</b> every request inserts a document, and all writes go to the single PRIMARY "
           "and are replicated to two SECONDARY members on the same node. MongoDB's CPU therefore rises with the request rate, "
           "independent of the number of web replicas."]
    prof = profile("results/m04/fixed/r3_rate200") or profile("results/m04/fixed/r3_rate100")
    if "mongo_cpu_avg" in prof:
        txt.append(f" In the 3-replica high-rate run, the three MongoDB pods used about {prof['mongo_cpu_avg']:.0f}m CPU together.")
    txt.append("</li>")
    hosts = [profile(f"results/m04/fixed/r{rep}_rate{rate}").get("host_max") for rep, rate in runs]
    hosts = [h for h in hosts if h is not None]
    txt.append("<li><b>Single-node host:</b> httperf, <code>minikube tunnel</code>, the Ingress controller, all web pods and "
               "all MongoDB members share the same machine's CPUs, so the load generator competes with the system under test"
               + (f" (host CPU peaked at {max(hosts):.0f}%)." if hosts else ".") + "</li>")
    txt.append("<li><b>macOS tunnel and httperf:</b> with the Docker driver, all traffic passes through "
               "<code>minikube tunnel</code>, a user-space proxy. Opening a new connection per request at 200 req/s exhausted it, "
               "and httperf on macOS is limited to 1024 open sockets (FD_SETSIZE). Persistent connections (session mode) "
               "avoided this. At the highest rate, results also reflect the client side, not only the cluster.</li>")
    txt.append("</ul>")
    return "".join(txt)


def sec_conclusion(runs):
    parts = ["The Loan EMI calculator was deployed on a single-node Minikube cluster as a 3-replica Deployment behind a "
             "ClusterIP Service and an NGINX Ingress, with MongoDB as a 3-member replica set in a StatefulSet with one "
             "persistent volume per member. The whole system comes up with <code>kubectl apply -f k8s/</code>. Kubernetes "
             "recreated deleted web and database pods automatically, and the StatefulSet kept each member's name and PVC, "
             "so no data was lost. When the PRIMARY was deleted, the replica set elected a new one."]
    lp = loop_summary("results/m03/rolling_update_loop.log")
    if lp:
        parts.append("The rolling update to 1.1 (maxUnavailable: 0 plus readiness probes) completed with "
                     f"{lp[2]} failed request{'s' if lp[2] != 1 else ''} out of {lp[0]}.")
    if runs:
        upto = [r for (rep, rate), r in runs.items() if rate <= 100]
        if upto:
            errs = sum(int(r["errors"] or 0) for r in upto)
            worst = max(float(r["avg_response_ms"]) for r in upto)
            parts.append(f"Across all fixed-replica runs up to 100 req/s there were {errs} errors in total, and the "
                         f"average response time was at most {worst:.1f} ms.")
        parts.append("The load tests show that the CPU limit of the web pods is the first bottleneck, and that more "
                     "replicas keep the response time lower as the rate rises.")
    hpa = read_csv("results/m04/autoscale/hpa.csv") or []
    reps = [int(r["current_replicas"]) for r in hpa if (r.get("current_replicas") or "").isdigit()]
    if reps:
        if max(reps) > reps[0]:
            parts.append(f"The HPA scaled the deployment from {reps[0]} to {max(reps)} replicas during the 100 req/s phase "
                         f"and back to {reps[-1]} after the load dropped, with the expected delay from metric "
                         "collection and the stabilization window.")
        else:
            parts.append(f"The HPA kept {reps[0]} replica(s) during the test.")
    return "<h2>5. Conclusion</h2><p>" + " ".join(parts) + "</p>"


def appendix():
    s = ["<h2 class='pb'>Appendix A: Kubernetes manifests</h2>"]
    for f in sorted(glob.glob(os.path.join(ROOT, "k8s", "*.yaml"))) + sorted(glob.glob(os.path.join(ROOT, "k8s", "hpa", "*.yaml"))):
        s.append(code_file(os.path.relpath(f, ROOT)))
    s.append("<h2 class='pb'>Appendix B: Scripts</h2>")
    s.append(table(["Script", "Purpose"], [
        ["<code>scripts/persistence_test.sh</code>", "Deletes mongo-1; shows same name, same PVC, same document count"],
        ["<code>scripts/mongo_primary.sh</code>", "Replica-set member states and current PRIMARY"],
        ["<code>scripts/count_documents.sh</code>", "Number of documents in emidb.calculations"],
        ["<code>scripts/load_distribution.sh</code>", "N POST requests through the Ingress, requests per pod"],
        ["<code>scripts/request_loop.sh</code>", "Request every 0.2 s with ok/failed summary (self-healing, rolling update)"],
        ["<code>scripts/preflight.sh</code>", "Checks tools, metrics-server and the Ingress before load tests"],
        ["<code>scripts/gen_wsesslog.py</code>", "httperf session file with random valid POST bodies"],
        ["<code>scripts/httperf_run.sh</code>", "One httperf run at a given rate and duration"],
        ["<code>scripts/monitor.py</code>", "kubectl top pods every 15 s, host CPU every 1 s, HPA every 15 s, to CSV"],
        ["<code>scripts/run_fixed_experiments.sh</code>", "15 fixed-replica runs with profiling"],
        ["<code>scripts/run_autoscale_test.sh</code>", "10-minute HPA test"],
        ["<code>scripts/make_graphs.py</code>", "Graphs 1–3"],
        ["<code>scripts/build_report.py</code>", "This report"],
    ]))
    s.append("<h2 class='pb'>Appendix C: Server-side source code</h2>")
    s.append(code_file("app/emi.js"))
    s.append(code_file("app/server.js"))
    return "".join(s)


def extra_screenshots():
    others = [p for p in sorted(glob.glob(os.path.join(RES, "screenshots", "*")))
              if os.path.splitext(p)[1].lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp")
              and os.path.relpath(p, ROOT) not in used_images]
    if not others:
        return ""
    s = ["<h2 class='pb'>Appendix D: Additional screenshots</h2>"]
    for p in others:
        s.append(img(os.path.relpath(p, ROOT), os.path.splitext(os.path.basename(p))[0]))
    return "".join(s)


CSS = """
@page { size: A4; margin: 16mm 14mm; }
body { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 10.5pt; line-height: 1.45;
       color: #1a1a1a; max-width: 960px; margin: 0 auto; padding: 24px; }
h1 { font-size: 20pt; margin: 0 0 4px; }
h2 { font-size: 15pt; border-bottom: 2px solid #2b5797; padding-bottom: 3px; margin-top: 30px; color: #2b5797; }
h3 { font-size: 12pt; margin: 18px 0 6px; }
.cover { border-bottom: 3px solid #2b5797; padding-bottom: 12px; margin-bottom: 18px; }
.cover p { margin: 2px 0; }
pre { background: #f6f8fa; border: 1px solid #dde1e6; border-radius: 4px; padding: 8px; font-size: 7.8pt;
      line-height: 1.3; white-space: pre-wrap; word-break: break-all; font-family: Menlo, Consolas, monospace; }
code { font-family: Menlo, Consolas, monospace; font-size: 9pt; background: #f1f3f5; padding: 0 3px; border-radius: 3px; }
pre code { background: none; }
table { border-collapse: collapse; margin: 8px 0 12px; font-size: 9pt; width: 100%; }
th, td { border: 1px solid #c9ced6; padding: 4px 6px; text-align: left; vertical-align: top; }
th { background: #e9eef6; }
table.num td { text-align: right; } table.num td:first-child, table.num td:nth-child(2) { text-align: center; }
figure { margin: 10px 0 14px; text-align: center; page-break-inside: avoid; }
figure img { max-width: 100%; max-height: 520px; border: 1px solid #ccc; }
figcaption { font-size: 9pt; color: #555; margin-top: 4px; }
.src { font-size: 9pt; color: #444; margin: 10px 0 2px; }
.missing { border: 2px dashed #d00; background: #fff0f0; color: #a00; padding: 8px 10px; margin: 8px 0; font-size: 9.5pt; }
.red { color: #c00; }
.formula { text-align: center; font-size: 12pt; margin: 10px 0; }
.cols { display: flex; gap: 16px; } .cols > div { flex: 1; }
.pb { page-break-before: always; }
h2, h3 { page-break-after: avoid; }
"""


def chrome():
    for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
              "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"):
        if os.path.exists(p):
            return p
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"):
        if shutil.which(name):
            return shutil.which(name)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="____________________")
    ap.add_argument("--roll", default="____________________")
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args()

    runs = summary_runs()
    body = [
        '<div class="cover">',
        "<p>DS-584: Cloud Computing, Fall 2026 &nbsp;·&nbsp; FCIT, University of the Punjab &nbsp;·&nbsp; Instructor: Dr. Numan Shafi</p>",
        "<h1>Assignment 4: Deploying, Load Balancing and Autoscaling a Web Application with MongoDB on Kubernetes (Minikube)</h1>",
        f"<p><b>Name:</b> {esc(args.name)} &nbsp;&nbsp; <b>Roll No:</b> {esc(args.roll)} &nbsp;&nbsp; <b>Date:</b> {date.today():%d %B %Y}</p>",
        f'<p><b>Git repository:</b> <a href="{REPO_URL}">{REPO_URL}</a></p>',
        "</div>",
        "<p>This report documents the deliverables of all four milestones: a Loan EMI calculator that stores every "
        "calculation in MongoDB; its deployment on Minikube with a 3-member MongoDB replica set; load balancing and "
        "self-healing through the NGINX Ingress; and load testing, profiling and autoscaling. The repository README explains "
        "how to bring up the whole system on a fresh Minikube cluster with <code>kubectl apply -f k8s/</code>.</p>",
        sec_environment(), sec_m01(), sec_m02(), sec_m03(), sec_m04(), sec_conclusion(runs), appendix(),
    ]
    body.append(extra_screenshots())
    doc = (f"<!doctype html><html><head><meta charset='utf-8'><title>Assignment 4 Report</title>"
           f"<style>{CSS}</style></head><body>{''.join(body)}</body></html>")

    os.makedirs(OUT_DIR, exist_ok=True)
    html_path = os.path.join(OUT_DIR, "Assignment4_Report.html")
    with open(html_path, "w") as f:
        f.write(doc)
    print("wrote", html_path)

    pdf_path = os.path.join(OUT_DIR, "Assignment4_Report.pdf")
    browser = None if args.no_pdf else chrome()
    if browser:
        cmd = [browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf-no-header",
               f"--print-to-pdf={pdf_path}", "file://" + html_path]
        try:
            subprocess.run(cmd, capture_output=True, timeout=90)
        except (subprocess.SubprocessError, OSError):
            pass
    if os.path.exists(pdf_path) and os.path.getmtime(pdf_path) >= os.path.getmtime(html_path) - 1:
        print("wrote", pdf_path)
    else:
        print("PDF: open the HTML in Safari or Chrome and use File > Export as PDF (or Print > Save as PDF).")

    with open(os.path.join(OUT_DIR, "MISSING.txt"), "w") as f:
        f.write("\n".join(missing) + ("\n" if missing else "Nothing missing.\n"))
    if missing:
        print(f"\n{len(missing)} item(s) still missing (also in report/MISSING.txt):")
        for m in missing:
            print("  -", m)
    else:
        print("\nAll deliverables found.")


if __name__ == "__main__":
    main()
