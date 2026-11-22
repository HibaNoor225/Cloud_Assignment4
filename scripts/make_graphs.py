#!/usr/bin/env python3
"""Builds the three Milestone 04 graphs from results/m04 into results/graphs/.

Graph 1: average response time vs request rate (one line per replica count)
Graph 2: per-pod CPU utilization over time, 100 req/s run with 3 replicas
Graph 3: autoscaling test - request rate, average CPU and replica count on one time axis

CPU utilization is expressed as a percentage of the pod's CPU request (100m),
which is the same definition the HorizontalPodAutoscaler uses.

Usage: python3 scripts/make_graphs.py
"""
import csv
import os
from collections import defaultdict
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M04 = os.path.join(ROOT, "results", "m04")
OUT = os.path.join(ROOT, "results", "graphs")
CPU_REQUEST_M = 100


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def ts(value):
    return datetime.fromisoformat(value)


def graph1():
    path = os.path.join(M04, "fixed", "summary.csv")
    if not os.path.exists(path):
        print("skip graph 1: no", path)
        return
    data = defaultdict(dict)
    for row in read_csv(path):
        data[int(row["replicas"])][int(row["rate"])] = float(row["avg_response_ms"])
    plt.figure(figsize=(8, 5))
    for rep in sorted(data):
        rates = sorted(data[rep])
        plt.plot(rates, [data[rep][r] for r in rates], marker="o", label=f"{rep} replica{'s' if rep > 1 else ''}")
    plt.xlabel("Request rate (req/s)")
    plt.ylabel("Average response time (ms)")
    plt.title("Graph 1: Average response time vs request rate")
    plt.grid(alpha=0.3)
    plt.legend()
    save("graph1_response_time_vs_rate.png")


def graph2():
    path = os.path.join(M04, "fixed", "r3_rate100", "pods.csv")
    if not os.path.exists(path):
        print("skip graph 2: no", path)
        return
    rows = [r for r in read_csv(path) if r["pod"].startswith("emi-web")]
    if not rows:
        print("skip graph 2: no emi-web rows in", path)
        return
    t0 = ts(rows[0]["timestamp"])
    series = defaultdict(lambda: ([], []))
    for r in rows:
        xs, ys = series[r["pod"]]
        xs.append((ts(r["timestamp"]) - t0).total_seconds())
        ys.append(100.0 * float(r["cpu_millicores"]) / CPU_REQUEST_M)
    plt.figure(figsize=(8, 5))
    for pod, (xs, ys) in sorted(series.items()):
        plt.plot(xs, ys, marker="o", label=pod)
    plt.xlabel("Time (s)")
    plt.ylabel("CPU utilization (% of 100m request)")
    plt.title("Graph 2: Per-pod CPU, 100 req/s with 3 replicas")
    plt.grid(alpha=0.3)
    plt.legend(fontsize=8)
    save("graph2_pod_cpu_100rps_3replicas.png")


def graph3():
    hpa_path = os.path.join(M04, "autoscale", "hpa.csv")
    phases_path = os.path.join(M04, "autoscale", "phases.csv")
    if not (os.path.exists(hpa_path) and os.path.exists(phases_path)):
        print("skip graph 3: missing autoscale results")
        return
    hpa = read_csv(hpa_path)
    phases = read_csv(phases_path)
    t0 = ts(phases[0]["start"])

    def rel(v):
        return (ts(v) - t0).total_seconds() / 60

    rate_x, rate_y = [], []
    for p in phases:
        rate_x += [rel(p["start"]), rel(p["end"])]
        rate_y += [int(p["rate"])] * 2

    hx, cpu, reps = [], [], []
    for r in hpa:
        x = rel(r["timestamp"])
        if x < 0:
            continue
        hx.append(x)
        cpu.append(float(r["cpu_utilization_percent"]) if r["cpu_utilization_percent"] else float("nan"))
        reps.append(int(r["current_replicas"]) if r["current_replicas"] else float("nan"))

    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    axes[0].plot(rate_x, rate_y, color="tab:blue")
    axes[0].set_ylabel("Request rate\n(req/s)")
    axes[1].plot(hx, cpu, marker=".", color="tab:red")
    axes[1].axhline(50, linestyle="--", color="gray", label="HPA target 50%")
    axes[1].set_ylabel("Avg CPU\n(% of request)")
    axes[1].legend(loc="upper right")
    axes[2].step(hx, reps, where="post", color="tab:green")
    axes[2].set_ylabel("Web replicas")
    axes[2].set_ylim(0, 6)
    axes[2].set_xlabel("Time (minutes)")
    for ax in axes:
        ax.grid(alpha=0.3)
    fig.suptitle("Graph 3: Autoscaling test (10 -> 100 -> 10 req/s)")
    fig.tight_layout()
    save("graph3_autoscaling.png")


def save(name):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close("all")
    print("wrote", path)


if __name__ == "__main__":
    graph1()
    graph2()
    graph3()
