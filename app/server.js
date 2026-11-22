const os = require('os');
const path = require('path');
const express = require('express');
const { MongoClient } = require('mongodb');
const { calculateEmi, validate } = require('./emi');

const PORT = Number(process.env.PORT || 3000);
const MONGO_URL = process.env.MONGO_URL;
const APP_VERSION = process.env.APP_VERSION || '1.0';

if (!MONGO_URL) {
  console.error('MONGO_URL environment variable is required');
  process.exit(1);
}

const client = new MongoClient(MONGO_URL, {
  serverSelectionTimeoutMS: 3000,
  connectTimeoutMS: 3000,
});
const calculations = () => client.db().collection('calculations');

function podIp() {
  if (process.env.POD_IP) return process.env.POD_IP;
  for (const addrs of Object.values(os.networkInterfaces())) {
    for (const a of addrs || []) {
      if (a.family === 'IPv4' && !a.internal) return a.address;
    }
  }
  return '127.0.0.1';
}

const servedBy = process.env.HOSTNAME || os.hostname();
const servedByIp = podIp();

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: false }));
app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/version', (req, res) => {
  res.json({ version: APP_VERSION, servedBy, podIp: servedByIp });
});

app.post('/api/emi', async (req, res) => {
  const { principal, rate, months, errors } = validate(req.body || {});
  if (errors.length) return res.status(400).json({ errors });

  const result = calculateEmi(principal, rate, months);
  try {
    await calculations().insertOne({
      principal,
      rate,
      months,
      emi: result.emi,
      servedBy,
      createdAt: new Date(),
    });
  } catch (err) {
    console.error('insert failed:', err.message);
    return res.status(503).json({ errors: ['database unavailable'] });
  }

  res.json({ principal, rate, months, ...result, servedBy, podIp: servedByIp, version: APP_VERSION });
});

app.get('/api/history', async (req, res) => {
  try {
    const rows = await calculations()
      .find({}, { projection: { _id: 0 } })
      .sort({ createdAt: -1 })
      .limit(10)
      .toArray();
    res.json(rows);
  } catch (err) {
    console.error('history failed:', err.message);
    res.status(503).json({ errors: ['database unavailable'] });
  }
});

app.get('/health', async (req, res) => {
  try {
    await client.db().command({ ping: 1 });
    res.status(200).json({ status: 'ok', servedBy });
  } catch (err) {
    res.status(503).json({ status: 'mongo unreachable', error: err.message });
  }
});

const server = app.listen(PORT, () => {
  console.log(`emi-web ${APP_VERSION} listening on :${PORT} as ${servedBy} (${servedByIp})`);
});

function shutdown(signal) {
  console.log(`${signal} received, shutting down`);
  server.close(() => client.close().finally(() => process.exit(0)));
  setTimeout(() => process.exit(0), 10000).unref();
}
process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
