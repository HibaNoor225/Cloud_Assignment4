# results/

Raw outputs of every experiment. Filled in on the Mac while following the guides in `docs/`.

| Folder | Contents |
|---|---|
| `environment.txt` | Mac and tool versions (setup step M0.8) |
| `m01/` | Local API test output |
| `m02/` | Image check, `get_all.txt`, `rs_status.txt`, `mongo_init_job.log`, `persistence_test.txt` |
| `m03/` | Load distribution tables, watch logs, self-healing and rolling-update logs |
| `m04/fixed/` | 15 runs (`r<replicas>_rate<rps>/httperf.txt`, `pods.csv`, `host_cpu.csv`) and `summary.csv` |
| `m04/autoscale/` | HPA test: `hpa.csv`, `pods.csv`, `host_cpu.csv`, `phases.csv`, `httperf_*.txt`, `hpa_describe.txt` |
| `graphs/` | Graph 1–3 PNGs from `scripts/make_graphs.py` |
| `screenshots/` | Browser screenshots used in the report |
