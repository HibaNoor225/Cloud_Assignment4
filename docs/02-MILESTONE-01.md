# Milestone 01 — Develop a Loan EMI Calculator with MongoDB

All commands: **Mac Terminal**, inside `~/assignment4`. Docker Desktop must be running.

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
| 4 | `GET /health` returns 200 **only** when MongoDB is reachable (later the readiness probe) | `app/server.js` (MongoDB `ping`, 503 otherwise) |
| 5 | Every calculation saved in collection `calculations` with `principal, rate, months, emi, servedBy, createdAt` | `app/server.js` `insertOne(...)` |
| 6 | Connection string only from env var `MONGO_URL`; no hard-coded hosts / IPs / passwords | `app/server.js` exits if `MONGO_URL` is missing |
| – | No postback: AJAX submit, only the result panel and history table update | `app/public/app.js` (`e.preventDefault()` + `$.ajax`) |

The PDF allows testing this milestone **locally with a MongoDB container**, which is what we do here. No Kubernetes yet.

## Deliverables for Milestone 01

1. **Screenshot of the UI** with the result for **P = 500000, rate = 12%, n = 24** and the **history table** visible.
2. **Link to the Git repository**: `https://github.com/HibaNoor225/Cloud_Assignment4`.

Expected values (to check your screenshot):

| Field | Value |
|---|---|
| Monthly EMI | **23,536.74** |
| Total payment | **564,881.67** |
| Total interest | **64,881.67** |

---

## Step 1.1 — Go to the project

```bash
cd ~/assignment4
git pull
```

- **Why `git pull`:** makes sure your folder matches what's on GitHub.

## Step 1.2 — Read the code once (understand what you submit)

```bash
cat app/emi.js
cat app/server.js
```

- `emi.js`: the formula, rounding to 2 decimals, and validation (positive numbers; months must be whole).
- `server.js`: the three endpoints plus serving the web page. Look for `process.env.MONGO_URL` (requirement 6) and `process.env.HOSTNAME` (requirement 2).
- `app/public/app.js`: the jQuery code that sends the form with AJAX and redraws only the result and history.

## Step 1.3 — Start MongoDB in a Docker container

```bash
docker run -d --name emi-mongo -p 27017:27017 mongo:7.0
docker ps
```

- **What:** downloads the official MongoDB 7 image and runs it in the background (`-d`), reachable on your Mac at `localhost:27017`.
- **Why:** the app needs a database to store calculations; a container is quick and disposable.
- `docker ps` lists `emi-mongo` with status `Up`.

(If it says the name is already in use: `docker start emi-mongo`.)

## Step 1.4 — Install dependencies and run the unit test

```bash
cd ~/assignment4/app
npm install
npm test
```

- `npm install` downloads Express and the MongoDB driver into `app/node_modules/` (not pushed to Git).
- `npm test` checks the formula: 500000 / 12% / 24 must give 23,536.74.
- **Expected:** `# pass 2` and `# fail 0`.

## Step 1.5 — Start the app with `MONGO_URL` (Terminal window 1)

```bash
MONGO_URL="mongodb://localhost:27017/emidb" PORT=3000 node server.js
```

- **What:** sets `MONGO_URL` for this command only and starts the server on port 3000.
- **Why an env var:** the PDF forbids hard-coding the database address. Kubernetes will give it a different `MONGO_URL` later without changing the code.
- **Expected:** `emi-web 1.0 listening on :3000 as <your-mac-name> (<ip>)`.
- Leave this window running.

## Step 1.6 — Test the API (Terminal window 2)

Press **Cmd + N** for a new window:

```bash
cd ~/assignment4
curl -s http://localhost:3000/health | jq
curl -s -X POST http://localhost:3000/api/emi -H 'Content-Type: application/json' \
     -d '{"principal":500000,"rate":12,"months":24}' | jq
curl -s -X POST http://localhost:3000/api/emi -H 'Content-Type: application/json' \
     -d '{"principal":-5,"rate":12,"months":24}' | jq
curl -s http://localhost:3000/api/history | jq
```

| Command | You should see | Proves |
|---|---|---|
| `/health` | `{"status":"ok",...}` | req. 4 |
| POST valid | `emi: 23536.74`, `totalPayment`, `totalInterest`, `servedBy`, `podIp` | req. 2 |
| POST `-5` | `{"errors":["principal must be a positive number"]}` (HTTP 400) | req. 1 (server validation) |
| `/api/history` | list, newest first | req. 3 |

Save it as evidence:

```bash
mkdir -p results/m01
{ curl -s localhost:3000/health; echo; \
  curl -s -X POST localhost:3000/api/emi -H 'Content-Type: application/json' -d '{"principal":500000,"rate":12,"months":24}'; echo; \
  curl -s -X POST localhost:3000/api/emi -H 'Content-Type: application/json' -d '{"principal":-5,"rate":12,"months":24}'; echo; \
  curl -s localhost:3000/api/history; echo; } | tee results/m01/api_test.txt
```

Check the stored documents (req. 5):

```bash
docker exec emi-mongo mongosh emidb --quiet --eval 'db.calculations.find({}, {_id:0}).sort({createdAt:-1}).limit(3).toArray()' | tee results/m01/mongo_documents.txt
```

You'll see `principal, rate, months, emi, servedBy, createdAt`.

Check that `/health` really depends on MongoDB (req. 4):

```bash
docker stop emi-mongo
curl -s -w '  HTTP %{http_code}\n' http://localhost:3000/health | tee results/m01/health_check.txt       # HTTP 503
docker start emi-mongo
sleep 3
curl -s -w '  HTTP %{http_code}\n' http://localhost:3000/health | tee -a results/m01/health_check.txt    # HTTP 200
```

## Step 1.7 — Open the app and take the deliverable screenshot

1. In Safari or Chrome, open **http://localhost:3000**.
2. Enter **500000**, **12**, **24** and click **Calculate EMI**.
3. The page doesn't reload; only the **Result** panel and **History** table update (AJAX, no postback).
4. Check: EMI **23,536.74**, total **564,881.67**, interest **64,881.67**.
5. Make sure the **history table** is visible too (zoom out with **Cmd + minus** if needed).
6. Screenshot: press **Cmd + Shift + 4**, then **Space**, and click the browser window. The PNG is saved on your **Desktop**.
7. Move and rename it into the repo:

```bash
mkdir -p ~/assignment4/results/screenshots
mv ~/Desktop/Screenshot*.png ~/assignment4/results/screenshots/m01_ui_500000_12_24.png
```

(If there are several screenshots on the Desktop, move the right one by its full name instead.)

Optional extra screenshot: type `-5` in the loan amount and click Calculate. The field turns red (client-side validation). Save it as `m01_client_validation.png`.

## Step 1.8 — Stop and push

- Window 1: press **Ctrl + C** to stop `node server.js`.
- Stop the local MongoDB (Kubernetes runs its own from Milestone 02): `docker stop emi-mongo`

```bash
cd ~/assignment4
git add results/
git commit -m "Milestone 01: API tests and UI screenshot"
git push
```

### Milestone 01 done when
- [ ] `npm test` passes
- [ ] `results/m01/health_check.txt` shows 503 with MongoDB stopped and 200 with it running
- [ ] `results/screenshots/m01_ui_500000_12_24.png` shows EMI 23,536.74 and the history table
- [ ] Pushed to `github.com/HibaNoor225/Cloud_Assignment4`

Next: [03-MILESTONE-02.md](03-MILESTONE-02.md)
