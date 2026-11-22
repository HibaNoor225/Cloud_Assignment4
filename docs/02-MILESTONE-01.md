# Milestone 01 — Develop a Loan EMI Calculator with MongoDB

## What the PDF asks

Build an EMI calculator with **HTML, jQuery, Bootstrap** and a server-side framework (we use **Node.js + Express**). The server computes

```text
EMI = P · r · (1 + r)^n / ((1 + r)^n − 1)     where r = annual rate ÷ 12 ÷ 100, n = months
```

| # | Requirement | Where it is implemented |
|---|---|---|
| 1 | Form with P, annual rate %, months; validate positive numbers on **client and server** | `app/public/index.html` + `app/public/app.js` (client), `app/emi.js` `validate()` (server) |
| 2 | `POST /api/emi` returns EMI, total payment, total interest, **pod name (from `HOSTNAME`)** and **pod IP** | `app/server.js` |
| 3 | `GET /api/history` returns the last 10 calculations, newest first | `app/server.js` (`sort({createdAt:-1}).limit(10)`) |
| 4 | `GET /health` returns 200 **only** when MongoDB is reachable (later used as the readiness probe) | `app/server.js` (runs MongoDB `ping`, returns 503 otherwise) |
| 5 | Every calculation saved in collection `calculations` with `principal, rate, months, emi, servedBy, createdAt` | `app/server.js` `insertOne(...)` |
| 6 | Connection string only from env var `MONGO_URL`; no hard-coded hosts / IPs / passwords | `app/server.js` exits if `MONGO_URL` is missing |
| – | No postback: AJAX submit, only the result panel and history table update | `app/public/app.js` (`e.preventDefault()` + `$.ajax`) |

The PDF allows testing this milestone **locally with a MongoDB container**, and that's what we do here. No Kubernetes yet.

> **On a Mac:** run every "UBUNTU SERVER" command in Mac Terminal (Docker Desktop must be running). Skip Step 1.1's `ssh` and Step 1.7's tunnel; open **http://localhost:3000** directly in your browser. Screenshot with **Cmd + Shift + 4**.

## Deliverables for Milestone 01

1. **Screenshot of the UI** showing the result for **P = 500000, rate = 12%, n = 24**, with the **history table** visible.
2. **Link to the Git repository** with the source code.

Expected result for that input (so you can check the screenshot):

| Field | Value |
|---|---|
| Monthly EMI | **23,536.74** |
| Total payment | **564,881.67** |
| Total interest | **64,881.67** |

---

## Step 1.1 — Open SSH and go to the project

**Run on: YOUR PC**

```bash
ssh SERVER_USER@SERVER_IP
```

**Run on: UBUNTU SERVER (inside SSH)**

```bash
cd ~/assignment4
git pull
```

- **Why `git pull`:** makes sure you have the latest version of the code.

## Step 1.2 — Read the code once (understand what you're submitting)

```bash
cat app/emi.js
cat app/server.js
```

- `emi.js`: the formula and the validation (positive numbers; months must be a whole number).
- `server.js`: the three endpoints plus static file serving. Look for `process.env.MONGO_URL` (requirement 6) and `process.env.HOSTNAME` (requirement 2).

## Step 1.3 — Start MongoDB in a Docker container

**Run on: UBUNTU SERVER (inside SSH)**

```bash
docker run -d --name emi-mongo -p 27017:27017 mongo:7.0
docker ps
```

- **What:** downloads the official MongoDB 7 image and runs it in the background (`-d`), reachable on the server at `localhost:27017`.
- **Why:** the app needs a MongoDB to store calculations. A container is quick and disposable.
- `docker ps` should list `emi-mongo` with status `Up`.

(If it says the name is already in use from an earlier attempt: `docker start emi-mongo`.)

## Step 1.4 — Install the app's dependencies and run the unit test

```bash
cd ~/assignment4/app
npm install
npm test
```

- **What:** `npm install` downloads Express and the MongoDB driver into `node_modules/`. `npm test` checks the formula: 500000 / 12% / 24 must give 23,536.74.
- **Expected:** `# pass 2`, `# fail 0`.

## Step 1.5 — Start the app with `MONGO_URL`

```bash
MONGO_URL="mongodb://localhost:27017/emidb" PORT=3000 node server.js
```

- **What:** sets the environment variable `MONGO_URL` for this one command and starts the server on port 3000.
- **Why env var:** the PDF forbids hard-coding the database address; Kubernetes will inject a different `MONGO_URL` later.
- **Expected:** `emi-web 1.0 listening on :3000 as <hostname> (<ip>)`.
- Leave this window running. It's now busy serving the app.

## Step 1.6 — Test the API from a second SSH window

Open a **second** terminal on your PC and SSH in again.

**Run on: UBUNTU SERVER (second SSH window)**

```bash
cd ~/assignment4
curl -s http://localhost:3000/health | jq
curl -s -X POST http://localhost:3000/api/emi -H 'Content-Type: application/json' \
     -d '{"principal":500000,"rate":12,"months":24}' | jq
curl -s -X POST http://localhost:3000/api/emi -H 'Content-Type: application/json' \
     -d '{"principal":-5,"rate":12,"months":24}' | jq
curl -s http://localhost:3000/api/history | jq
```

| Command | What you should see | Proves requirement |
|---|---|---|
| `/health` | `{"status":"ok",...}` | 4 |
| POST valid | `emi: 23536.74`, `totalPayment`, `totalInterest`, `servedBy`, `podIp` | 2 |
| POST `-5` | `{"errors":["principal must be a positive number"]}` (HTTP 400) | 1 (server validation) |
| `/api/history` | list, newest first | 3 |

Optional: save the output as extra evidence:

```bash
mkdir -p results/m01
{ curl -s localhost:3000/health; echo; \
  curl -s -X POST localhost:3000/api/emi -H 'Content-Type: application/json' -d '{"principal":500000,"rate":12,"months":24}'; echo; \
  curl -s localhost:3000/api/history; echo; } | tee results/m01/api_test.txt
```

Check the documents in MongoDB (requirement 5):

```bash
docker exec emi-mongo mongosh emidb --quiet --eval 'db.calculations.find({}, {_id:0}).sort({createdAt:-1}).limit(3).toArray()'
```

You'll see `principal, rate, months, emi, servedBy, createdAt`.

Check that `/health` really depends on MongoDB:

```bash
docker stop emi-mongo
curl -s -w '  HTTP %{http_code}\n' http://localhost:3000/health     # expect HTTP 503
docker start emi-mongo
sleep 3
curl -s -w '  HTTP %{http_code}\n' http://localhost:3000/health     # expect HTTP 200
```

## Step 1.7 — Open the app in your PC's browser (SSH tunnel)

The app listens on the **server's** `localhost:3000`, which your PC's browser can't see directly. An SSH tunnel forwards a port on your PC to that port on the server.

Open a **third** terminal on your PC (don't SSH in normally; run this instead):

**Run on: YOUR PC**

```bash
ssh -L 3000:localhost:3000 SERVER_USER@SERVER_IP
```

- **What:** "anything my PC sends to *its own* port 3000, carry through SSH to the server's `localhost:3000`".
- Keep this window open while you use the browser.

Now open the browser on your PC and go to **http://localhost:3000**.

## Step 1.8 — Take the deliverable screenshot

1. In the form enter **500000**, **12**, **24** and click **Calculate EMI**.
2. The page doesn't reload; only the **Result** panel and **History** table update (AJAX, no postback).
3. Check the result: EMI **23,536.74**, total **564,881.67**, interest **64,881.67**.
4. Make sure the **history table** is visible in the same screenshot (zoom out with Ctrl+minus if needed).
5. Take the screenshot:
   - Windows: **Win + Shift + S**, then save the image.
   - Mac: **Cmd + Shift + 4**.
6. Save it as `m01_ui_500000_12_24.png`.

Optional extra screenshot: type `-5` in the loan amount and click Calculate. The field turns red (client-side validation).

Keep screenshots in a folder on your PC (for example `Assignment4-screenshots/`). They go into the PDF report.

## Step 1.9 — Stop the local run and push

**Run on: UBUNTU SERVER**

- In the first SSH window press **Ctrl+C** to stop `node server.js`.
- Stop the local MongoDB (it isn't needed for Kubernetes): `docker stop emi-mongo`

Commit any outputs:

```bash
cd ~/assignment4
git add results/
git commit -m "Milestone 01: local API test output"
git push
```

Copy the repository URL; that's the second M01 deliverable.

### Milestone 01 done when
- [ ] `npm test` passes
- [ ] `/health` gives 200 with MongoDB up and 503 with it down
- [ ] Screenshot `m01_ui_500000_12_24.png` shows EMI 23,536.74 and the history table
- [ ] You have the Git repository link

Next: [03-MILESTONE-02.md](03-MILESTONE-02.md)
