# Step 0 (macOS) — Setup from zero on a Mac, no Ubuntu needed

Everything runs directly on your Mac: Docker Desktop, Minikube (Docker driver), kubectl, the app and the load tests. There's no SSH and no tunnels. Every command is typed in the Mac **Terminal** app, and the browser is the Mac's own browser.

The PDF covers this case explicitly: *"run `minikube tunnel` and use 127.0.0.1 on Windows and macOS with the Docker driver."*

> Wherever the milestone guides say **Run on: UBUNTU SERVER (inside SSH)**, run that command in your Mac Terminal instead. Skip every `ssh ...` and `ssh -L ...` step. Each milestone guide has an **On a Mac** box listing the few differences.

---

## M0.1 Open Terminal

Press **Cmd + Space**, type `Terminal`, press Enter. You can open more windows with **Cmd + N** (Milestone 03 needs 2–3 at once).

## M0.2 Check your Mac's resources

```bash
sw_vers                                      # macOS version
uname -m                                     # arm64 = Apple Silicon (M1/M2/M3/M4), x86_64 = Intel
sysctl -n hw.ncpu                            # CPU cores
echo "$(( $(sysctl -n hw.memsize) / 1073741824 )) GB RAM"
df -h /                                      # free disk (need about 20 GB)
```

Write them down for the report's "Environment" section and for choosing Minikube's size:

| Mac RAM | Docker Desktop memory | `minikube start` flags |
|---|---|---|
| 16 GB or more | 8 GB | `--cpus=4 --memory=6144` |
| 8 GB | 6 GB | `--cpus=2 --memory=4096` (works; response times in Milestone 04 will be higher) |

## M0.3 Install Homebrew (the macOS package manager)

```bash
brew --version
```

If it says `command not found`:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

- It asks for your Mac login password (nothing is shown while typing) and may install the Xcode Command Line Tools (which include `git`).
- At the end it prints **Next steps** with two `echo ... >> ~/.zprofile` / `eval ...` lines. **Copy and run them.** On Apple Silicon they look like:

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

Then `brew --version` must work.

## M0.4 Install the tools

```bash
brew install git kubectl minikube node jq httperf tmux
brew install --cask docker
```

| Tool | Used for |
|---|---|
| `git` | your repository |
| `kubectl` | controlling Kubernetes |
| `minikube` | the single-node Kubernetes cluster |
| `node` | running the app locally in Milestone 01 |
| `jq` | pretty-printing JSON |
| `httperf` | load generator, Milestone 04 |
| `tmux` | optional, keeps long tests in a named session |
| Docker Desktop (`--cask docker`) | runs containers and the Minikube node |

Check:

```bash
git --version; kubectl version --client; minikube version; node -v; httperf --version | head -1
```

`node -v` must be v20 or newer. `ab` (ApacheBench) is already built into macOS, but we use httperf because it can send a different random body with every request.

## M0.5 Start Docker Desktop and give it enough resources

1. Open **Applications > Docker**. Accept the terms; you can skip signing in.
2. Wait until the whale icon in the menu bar says **Docker Desktop is running**.
3. Docker icon > **Settings > Resources**: set **CPUs** to at least 4 (2 on small Macs) and **Memory** per the table in M0.2. Click **Apply & restart**.

Verify:

```bash
docker version
docker run --rm hello-world
```

Docker Desktop must be **running** every time you work on the assignment (Minikube lives inside it).

## M0.6 Python for the graphs and profiling

Use a virtual environment in the project folder. It keeps the packages separate from macOS's own Python.

```bash
cd ~/assignment4                         # after you clone the repo in M0.7
python3 -m venv .venv
source .venv/bin/activate
pip install matplotlib psutil
```

- `matplotlib` draws the 3 graphs; `psutil` reads the Mac's CPU % every second (`scripts/monitor.py`).
- In **every new Terminal window** where you run Milestone 04 scripts, first run `cd ~/assignment4 && source .venv/bin/activate`. The prompt shows `(.venv)` when it's active.

## M0.7 Your personal Git repository

1. Sign in at [github.com](https://github.com) with **your own** account.
2. Click **+ > New repository**. Name it something like `ds584-assignment4`, leave it **empty** (no README, no .gitignore), choose Public (or Private and add your instructor as a collaborator). Click **Create repository**.
3. Copy its HTTPS URL, e.g. `https://github.com/<your-username>/ds584-assignment4.git`.

Clone it, with your **personal** username in the URL (so a company GitHub login saved in the Keychain isn't used by mistake):

```bash
cd ~
git clone https://<your-username>@github.com/<your-username>/ds584-assignment4.git assignment4
cd assignment4
ls            # app  docs  k8s  README.md  results  scripts
chmod +x scripts/*.sh scripts/*.py
```

Set your identity **for this repository only** (no `--global`, so any other Git account on this Mac, e.g. a work one, is unaffected). Do this before your first commit:

```bash
git config user.name "Your Name"
git config user.email "the-email-on-your-github-account"
git config user.email          # check: prints your personal email inside this folder
```

**Pushing from the Mac:** GitHub doesn't accept your account password in Terminal. Create a **Personal Access Token** (github.com > Settings > Developer settings > Personal access tokens > Tokens (classic) > Generate, scope `repo`) and paste it when `git push` asks for a password. macOS saves it in the Keychain, so you only do this once.

## M0.8 Setup checklist

```bash
cd ~/assignment4
mkdir -p results
{ date; sw_vers; uname -m; echo "cores: $(sysctl -n hw.ncpu)"; echo "ram GB: $(( $(sysctl -n hw.memsize) / 1073741824 ))"; \
  docker version --format 'docker {{.Server.Version}}'; kubectl version --client; minikube version; node -v; } > results/environment.txt 2>&1
cat results/environment.txt
```

### Setup done when
- [ ] Docker Desktop is running and `docker run --rm hello-world` works
- [ ] `kubectl`, `minikube`, `node` (v20+), `httperf` are installed
- [ ] Repo cloned at `~/assignment4`, `.venv` created with matplotlib + psutil
- [ ] `results/environment.txt` exists

Next: [02-MILESTONE-01.md](02-MILESTONE-01.md) (read its **On a Mac** box first)

---

## Quick reference: Mac differences per milestone

| Milestone | Ubuntu-over-SSH guide says | On your Mac do this instead |
|---|---|---|
| All | "Run on: UBUNTU SERVER (inside SSH)" | Run it in Mac Terminal |
| All | `ssh ...`, `ssh -L ...` tunnels | Skip them |
| 01 | Browser via `ssh -L 3000:...` | Open **http://localhost:3000** directly |
| 02 | `minikube start -p emi --driver=docker --cpus=4 --memory=6144` | Same (use the flags from the M0.2 table) |
| 02 | Browser via `ssh -L 8080:...` | Open **http://localhost:8080** directly |
| 03 | `echo "$(minikube ip) emi.local" \| sudo tee -a /etc/hosts` | `echo "127.0.0.1 emi.local" \| sudo tee -a /etc/hosts`, then in a **separate Terminal** run `minikube tunnel` and leave it open |
| 03 | Edit the PC's hosts file + `ssh -L 80:...` | Not needed; the line above already covers the Mac |
| 04 | `tmux` to survive SSH drops | Optional. Keep the Mac awake: run long scripts as `caffeinate -i scripts/...` |
| 04 | `python3-matplotlib` from apt | `source .venv/bin/activate` first in each Terminal |
