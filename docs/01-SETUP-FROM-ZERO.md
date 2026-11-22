# Step 0 — Setup from zero (before Milestone 01)

Goal: from your PC, open an SSH session on the Ubuntu server, install every tool the assignment needs, and get this repository onto the server.

Nothing in this step is graded, but every later step depends on it.

---

## 0.1 Find out what kind of Ubuntu server you have

| Your situation | How you see its screen the first time |
|---|---|
| **VM** on your PC (VirtualBox / VMware / Hyper-V) | Open VirtualBox, select the VM, click **Start**. A console window opens. |
| **Cloud VM** (AWS, Azure, GCP, DigitalOcean) | You don't get a screen. Use the provider dashboard to read its **Public IP** and go straight to 0.4. |
| **Physical machine** (separate computer / lab PC) | Sit at its keyboard and monitor for the first login. |

## 0.2 Log in on the server console (VM or physical only)

**Run on: UBUNTU SERVER console (the VM window or physical keyboard)**

1. At `login:` type your Ubuntu **username** (the one created at install, for example `student`) and press **Enter**.
2. At `Password:` type your password and press **Enter**. Nothing appears while you type; that is normal.
3. You now see a prompt like `student@ubuntu-server:~$`. That is the server shell.

## 0.3 Get the server's IP address

**Run on: UBUNTU SERVER console**

```bash
hostname -I
```

- **What it does:** prints the server's IP address(es).
- **Why:** SSH needs an address to connect to.
- Use the **first** address, for example `192.168.1.50`. Ignore `172.17.0.1` (that is Docker's internal network).

More detail, if you see several addresses:

```bash
ip -br a
```

Look for the interface that is `UP` (often `enp0s3`, `ens33` or `eth0`). The number before `/24` is the IP.

> **VirtualBox users:** if the IP starts with `10.0.2.` the VM uses **NAT** and your PC cannot reach it directly. Either switch the VM to **Bridged Adapter** (VM Settings > Network > Attached to: Bridged Adapter, then reboot the VM and run `hostname -I` again), or add a port-forward rule in NAT (Host Port 2222 → Guest Port 22) and later use `ssh -p 2222 student@127.0.0.1`.

Write these down. You'll use them in every guide:

```text
SERVER_IP   = ______________   (e.g. 192.168.1.50)
SERVER_USER = ______________   (e.g. student)
```

## 0.4 Make sure the SSH server is running on Ubuntu

**Run on: UBUNTU SERVER console**

```bash
sudo systemctl status ssh --no-pager
```

- **What it does:** shows whether the SSH server (`sshd`) is running.
- **Why:** `ssh` on your PC is only the client; the server must be listening on port 22.
- `sudo` asks for your Ubuntu password the first time.

If it says `Unit ssh.service could not be found` or `inactive`:

```bash
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
sudo systemctl status ssh --no-pager
```

You should now see `active (running)`.

If the firewall is enabled, allow SSH:

```bash
sudo ufw status
sudo ufw allow OpenSSH      # only if the line above says "Status: active"
```

## 0.5 Connect from your PC with SSH

**Run on: YOUR PC**

- **Windows:** press the Windows key, type `PowerShell`, open it.
- **Mac:** open **Terminal** (Applications > Utilities).
- **Linux:** open your terminal.

Check the SSH client exists:

```bash
ssh -V
```

(Windows: if it says "not recognized", go to Settings > Apps > Optional features > Add a feature > **OpenSSH Client**, then reopen PowerShell.)

Connect (replace with your values):

```bash
ssh student@192.168.1.50
```

- The first time, it asks `Are you sure you want to continue connecting (yes/no)?` Type `yes` and press Enter. Your PC remembers the server's fingerprint.
- Type your Ubuntu password (nothing is shown) and press Enter.
- The prompt changes to `student@ubuntu-server:~$`. You are now **inside SSH**: every command you type runs on the server.

Cloud VM with a key file instead of a password:

```bash
ssh -i path/to/key.pem ubuntu@PUBLIC_IP
```

| Error | Meaning / fix |
|---|---|
| `Connection timed out` | Wrong IP, VM is off, or VirtualBox NAT (see 0.3) |
| `Connection refused` | SSH server not running → redo 0.4 on the console |
| `Permission denied` | Wrong username or password |

To leave SSH: type `exit` (or press Ctrl+D).

### Opening several SSH windows (needed in Milestones 03 and 04)

Some experiments need 2–3 terminals at the same time (for example, one watching pods, one sending requests). Open another PowerShell / Terminal window on your PC and run the same `ssh student@SERVER_IP` again. Each window is an independent session on the same server.

## 0.6 Check the server has enough resources

**Run on: UBUNTU SERVER (inside SSH)**

```bash
lsb_release -a     # Ubuntu version (22.04 or 24.04 expected)
nproc              # number of CPU cores
free -h            # memory
df -h /            # free disk space
```

- **Why:** Minikube with 3 MongoDB pods + 5 web pods + Ingress needs roughly **4 CPUs, 6 GB RAM, 20 GB free disk**. It still works with **2 CPUs / 4 GB**, but response times in Milestone 04 will be higher (that's fine, just report what you measure).
- Note the numbers. You'll use them in `minikube start` and put them in the report's "Environment" section.

## 0.7 Install basic packages

**Run on: UBUNTU SERVER (inside SSH)**

```bash
sudo apt update
sudo apt install -y git curl ca-certificates jq httperf apache2-utils sysstat python3 python3-matplotlib
```

| Package | Used for |
|---|---|
| `git` | clone/push the repository |
| `curl` | send test requests |
| `jq` | pretty-print JSON responses |
| `httperf` | load generator (Milestone 04) |
| `apache2-utils` | provides `ab` (ApacheBench), an alternative load tool |
| `sysstat` | provides `mpstat` (host CPU) |
| `python3-matplotlib` | draws the graphs |

## 0.8 Docker

You probably installed Docker in an earlier assignment. Check:

**Run on: UBUNTU SERVER (inside SSH)**

```bash
docker version
docker run --rm hello-world
```

If both work without `sudo`, skip to 0.9.

If `docker` is not found:

```bash
sudo apt install -y docker.io
sudo systemctl enable --now docker
```

If you get `permission denied ... docker.sock`, add yourself to the `docker` group:

```bash
sudo usermod -aG docker $USER
exit
```

Then SSH in again from your PC (group membership only applies to new logins) and re-run `docker run --rm hello-world`.

- **Why:** Minikube's `docker` driver runs the whole Kubernetes node inside a Docker container, and you build the app image with Docker.

## 0.9 kubectl and Minikube

**Run on: UBUNTU SERVER (inside SSH)**

```bash
kubectl version --client
minikube version
```

If either is missing:

```bash
# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -m 0755 kubectl /usr/local/bin/kubectl && rm kubectl

# minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube && rm minikube-linux-amd64
```

(If `uname -m` prints `aarch64`, replace `amd64` with `arm64` in both URLs.)

## 0.10 Node.js 20 (only needed to run the app locally in Milestone 01)

**Run on: UBUNTU SERVER (inside SSH)**

```bash
node -v
```

If it's missing or older than v20:

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node -v      # should print v20.x
npm -v
```

## 0.11 Get the repository onto the server

The code for this assignment lives in this project. To clone it you first need a Git remote:

- In Cursor, click the **Create repo** pill on this project to create the repository, then copy its HTTPS URL (for example `https://github.com/<you>/emi-k8s-assignment4.git`).
- Or, if you'd rather use your own GitHub account: create an **empty** repository on github.com, download this project, and push it there (`git remote add origin <url> && git push -u origin main`).

Then:

**Run on: UBUNTU SERVER (inside SSH)**

```bash
cd ~
git clone <YOUR_REPO_URL> assignment4
cd assignment4
ls
```

You should see `app  docs  k8s  README.md  results  scripts`.

Set your name for commits (once per server):

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

**Pushing from the server (GitHub):** GitHub doesn't accept your account password over HTTPS. Create a **Personal Access Token** at github.com > Settings > Developer settings > Personal access tokens (scope: `repo`). When `git push` asks for a password, paste the token. To avoid pasting it every time:

```bash
git config --global credential.helper store
```

Make the scripts executable (once):

```bash
chmod +x scripts/*.sh scripts/*.py
```

## 0.12 Setup checklist

**Run on: UBUNTU SERVER (inside SSH)**

```bash
whoami; hostname; hostname -I
docker version --format '{{.Server.Version}}'
kubectl version --client
minikube version
node -v
httperf --version | head -1
python3 -c "import matplotlib; print('matplotlib', matplotlib.__version__)"
ls ~/assignment4
```

Save this output for the report's **Environment** section:

```bash
cd ~/assignment4
mkdir -p results/m01
{ date; whoami; hostname; lsb_release -d; nproc; free -h; docker version --format 'docker {{.Server.Version}}'; kubectl version --client; minikube version; node -v; } > results/environment.txt 2>&1
cat results/environment.txt
```

### Setup done when
- [ ] You can `ssh SERVER_USER@SERVER_IP` from your PC
- [ ] `docker run --rm hello-world` works without `sudo`
- [ ] `kubectl`, `minikube`, `node` (v20+), `httperf`, `python3-matplotlib` are installed
- [ ] The repo is cloned at `~/assignment4`
- [ ] `results/environment.txt` exists

Next: [02-MILESTONE-01.md](02-MILESTONE-01.md)
