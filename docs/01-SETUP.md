# Step 0 — Setup on your Mac (from zero)

Everything in this assignment runs **on your Mac**: Docker Desktop, Minikube (Docker driver), kubectl, the app, MongoDB and the load tests. You don't need Ubuntu, SSH or a second computer. Every command is typed in the Mac **Terminal** app, and you use the Mac's own browser.

The PDF covers this case: *"run `minikube tunnel` and use 127.0.0.1 on Windows and macOS with the Docker driver."*

---

## M0.1 Open Terminal

Press **Cmd + Space**, type `Terminal`, press **Enter**.

- A new Terminal window: **Cmd + N**. Milestone 03 needs 2–3 windows open at once.
- Paste a command with **Cmd + V**, then press **Enter**.
- Stop a running command with **Ctrl + C**.
- When Terminal asks for a **Password**, type your Mac login password. Nothing appears while typing; that's normal.

## M0.2 Check your Mac's resources

```bash
sw_vers                                                    # macOS version
uname -m                                                   # arm64 = Apple Silicon (M1–M4), x86_64 = Intel
sysctl -n hw.ncpu                                          # CPU cores
echo "$(( $(sysctl -n hw.memsize) / 1073741824 )) GB RAM"  # memory
df -h /                                                    # free disk, about 20 GB needed
```

Write the numbers down. You'll use them for Docker/Minikube sizing and in the report's "Environment" section.

| Mac RAM | Docker Desktop memory | `minikube start` flags (Milestone 02) |
|---|---|---|
| 16 GB or more | 8 GB | `--cpus=4 --memory=6144` |
| 8 GB | 6 GB | `--cpus=2 --memory=4096` (works; response times in Milestone 04 will be higher, which is fine to report) |

## M0.3 Install Homebrew (the macOS package manager)

```bash
brew --version
```

If it says `command not found`, install it:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

- It asks for your Mac password and then **Press RETURN/ENTER to continue**. Press Enter.
- It downloads the **Xcode Command Line Tools** (includes `git`). This step can sit on "Downloading..." for 5–30 minutes. Don't close the window.
- At the end it prints `Installation successful!` and **Next steps**.

Make `brew` available in Terminal (Apple Silicon path, `/opt/homebrew`):

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
brew --version
```

(Intel Macs: Homebrew lives in `/usr/local` and is usually found automatically.)

## M0.4 Install the tools

```bash
brew install git kubectl minikube node jq httperf tmux
```

| Tool | Used for |
|---|---|
| `git` | your repository |
| `kubectl` | controlling Kubernetes |
| `minikube` | the single-node Kubernetes cluster |
| `node` | running the app locally in Milestone 01 |
| `jq` | pretty-printing JSON in Terminal |
| `httperf` | load generator (Milestone 04) |
| `tmux` | optional; keeps long tests in a named session |

Check:

```bash
git --version
kubectl version --client
minikube version
node -v              # must be v20 or newer
httperf --version | head -1
```

`ab` (ApacheBench) is already built into macOS, but we use httperf because it can send a **different random body** with every request, which the PDF asks for.

## M0.5 Docker Desktop

Check whether it's installed:

```bash
ls /Applications | grep -i docker
```

- Prints `Docker.app`: it's installed, continue below.
- Prints nothing: install it with `brew install --cask docker` (or download it from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/), choosing Apple Silicon or Intel).

Start it: **Cmd + Space**, type `Docker`, press **Enter**. Accept the terms, skip sign-in, and wait until the whale icon in the menu bar says **Docker Desktop is running**.

Give it enough resources: whale icon > **Settings > Resources**. Set **CPUs** to 4 (2 on small Macs) and **Memory** per the M0.2 table, then click **Apply & restart**.

```bash
docker version
docker run --rm hello-world        # prints "Hello from Docker!"
```

> Docker Desktop must be **running every time** you work on the assignment, because Minikube lives inside it.

## M0.6 Your repository

Your personal repo is **https://github.com/HibaNoor225/Cloud_Assignment4**. If you already did these steps with the zip, skip to M0.7.

1. Create a **Personal Access Token** on github.com (signed in as HibaNoor225): profile picture > **Settings > Developer settings > Personal access tokens > Tokens (classic) > Generate new token (classic)**, tick **repo**, generate, copy it. Don't share it.
2. Clone, copy the project files in, set your identity for this folder only, and push:

```bash
cd ~
git clone https://HibaNoor225@github.com/HibaNoor225/Cloud_Assignment4.git assignment4
cd ~/assignment4
unzip -q ~/Downloads/Cloud_Assignment4.zip -d /tmp/a4
cp -R /tmp/a4/Cloud_Assignment4/. .
rm -rf /tmp/a4

git config user.name "Hiba Noor"
git config user.email "your-personal-email@example.com"   # this folder only; your work Git account is unaffected

chmod +x scripts/*.sh scripts/*.py
git add -A
git commit -m "Initial project: EMI app, Kubernetes manifests, scripts, guides"
git branch -M main
git push -u origin main          # Password = the token from step 1
```

- `HibaNoor225@` in the URL makes Git use your personal account even if a work GitHub login is saved in the Keychain.
- The Keychain remembers the token, so later pushes don't ask again.

## M0.7 Python environment (graphs and CPU recording)

```bash
cd ~/assignment4
python3 -m venv .venv
source .venv/bin/activate
pip install matplotlib psutil
```

- `matplotlib` draws the 3 graphs; `psutil` records the Mac's CPU % every second.
- `.venv` is in `.gitignore`, so it isn't pushed.
- In **every new Terminal window** where you run Milestone 04 scripts, run `cd ~/assignment4 && source .venv/bin/activate` first. The prompt shows `(.venv)` when it's active.

## M0.8 Record your environment (for the report)

```bash
cd ~/assignment4
mkdir -p results
{ date; sw_vers; uname -m; echo "cores: $(sysctl -n hw.ncpu)"; echo "ram GB: $(( $(sysctl -n hw.memsize) / 1073741824 ))"; \
  docker version --format 'docker {{.Server.Version}}'; kubectl version --client; minikube version; node -v; } > results/environment.txt 2>&1
cat results/environment.txt
git add results/environment.txt
git commit -m "Record environment"
git push
```

### Setup done when
- [ ] `brew --version` works
- [ ] Docker Desktop is running and `docker run --rm hello-world` works
- [ ] `kubectl`, `minikube`, `node` (v20+), `httperf`, `jq` installed
- [ ] `~/assignment4` exists and is pushed to `github.com/HibaNoor225/Cloud_Assignment4`
- [ ] `.venv` created with matplotlib + psutil
- [ ] `results/environment.txt` pushed

Next: [02-MILESTONE-01.md](02-MILESTONE-01.md)
