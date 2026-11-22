#!/usr/bin/env python3
"""Records profiling data to CSV files until stopped (Ctrl+C / SIGTERM) or --duration ends.

  pods.csv      every 15 s: timestamp, pod, cpu_millicores, memory_mib   (kubectl top pods -n emi)
  host_cpu.csv  every 1 s:  timestamp, cpu_percent                        (host-wide: /proc/stat on Linux, psutil on macOS)
  hpa.csv       every 15 s (only with --hpa): timestamp, current_replicas, desired_replicas,
                cpu_utilization_percent, raw   (kubectl get hpa emi-web -n emi)

Usage: python3 scripts/monitor.py --out-dir results/m04/fixed/r3_rate100 [--hpa] [--duration 60]
"""
import argparse
import csv
import os
import signal
import subprocess
import threading
import time
from datetime import datetime

NS = os.environ.get("NS", "emi")
stop = threading.Event()


def now():
    return datetime.now().isoformat(timespec="seconds")


def kubectl(*args):
    try:
        return subprocess.run(["kubectl", *args], capture_output=True, text=True, timeout=20).stdout
    except (subprocess.SubprocessError, OSError):
        return ""


def read_proc_stat():
    with open("/proc/stat") as f:
        fields = [int(x) for x in f.readline().split()[1:]]
    idle = fields[3] + fields[4]  # idle + iowait
    return idle, sum(fields)


def host_cpu_sampler():
    """Returns a function giving host-wide CPU % since its previous call.

    Linux reads /proc/stat directly; macOS (no /proc) uses psutil.
    """
    if os.path.exists("/proc/stat"):
        state = list(read_proc_stat())

        def sample():
            idle1, total1 = read_proc_stat()
            dt = total1 - state[1]
            pct = 100.0 * (1 - (idle1 - state[0]) / dt) if dt else 0.0
            state[:] = [idle1, total1]
            return pct

        return sample

    import psutil

    psutil.cpu_percent(interval=None)
    return lambda: psutil.cpu_percent(interval=None)


def host_cpu_loop(path):
    sample = host_cpu_sampler()
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "cpu_percent"])
        while not stop.wait(1):
            w.writerow([now(), round(sample(), 1)])
            f.flush()


def parse_qty(value, unit):
    value = value.strip()
    if unit == "cpu":
        return int(value[:-1]) if value.endswith("m") else int(float(value) * 1000)
    for suffix, factor in (("Ki", 1 / 1024), ("Mi", 1), ("Gi", 1024)):
        if value.endswith(suffix):
            return round(float(value[: -len(suffix)]) * factor, 1)
    return round(float(value) / (1024 * 1024), 1)


def pods_loop(path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "pod", "cpu_millicores", "memory_mib"])
        while True:
            ts = now()
            for line in kubectl("top", "pods", "-n", NS, "--no-headers").splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    w.writerow([ts, parts[0], parse_qty(parts[1], "cpu"), parse_qty(parts[2], "mem")])
            f.flush()
            if stop.wait(15):
                return


def hpa_loop(path):
    jsonpath = (
        "{.status.currentReplicas},{.status.desiredReplicas},"
        "{.status.currentMetrics[0].resource.current.averageUtilization}"
    )
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "current_replicas", "desired_replicas", "cpu_utilization_percent", "raw"])
        while True:
            ts = now()
            values = kubectl("get", "hpa", "emi-web", "-n", NS, "-o", f"jsonpath={jsonpath}").strip().split(",")
            raw = " ".join(kubectl("get", "hpa", "emi-web", "-n", NS, "--no-headers").split())
            values += [""] * (3 - len(values))
            w.writerow([ts, *values[:3], raw])
            f.flush()
            print(f"{ts}  {raw}", flush=True)
            if stop.wait(15):
                return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--hpa", action="store_true", help="also record kubectl get hpa every 15 s")
    ap.add_argument("--duration", type=float, default=0, help="seconds to run (0 = until stopped)")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    threads = [
        threading.Thread(target=host_cpu_loop, args=(os.path.join(args.out_dir, "host_cpu.csv"),)),
        threading.Thread(target=pods_loop, args=(os.path.join(args.out_dir, "pods.csv"),)),
    ]
    if args.hpa:
        threads.append(threading.Thread(target=hpa_loop, args=(os.path.join(args.out_dir, "hpa.csv"),)))
    for t in threads:
        t.start()

    start = time.time()
    while not stop.is_set():
        if args.duration and time.time() - start >= args.duration:
            stop.set()
        time.sleep(0.5)
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
