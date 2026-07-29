'use strict';

const express = require('express');
const config = require('./config');
const FabricConnector = require('./fabric-connector');

const app = express();
app.use(express.json({ limit: '10mb' }));

const fabric = new FabricConnector();

async function ensureConnected(req, res, next) {
  try {
    if (!fabric.contract) await fabric.connect();
    next();
  } catch (err) {
    res.status(503).json({ error: 'Fabric connection failed', detail: err.message });
  }
}

app.post('/audit/events', ensureConnected, async (req, res) => {
  try {
    console.log('POST /audit/events body keys:', Object.keys(req.body));
    const bodyStr = JSON.stringify(req.body);
    console.log('POST /audit/events body length:', bodyStr.length);
    const result = await fabric.CreateAuditEvent(bodyStr);
    res.status(201).json(result);
  } catch (err) {
    console.error('POST /audit/events error:', err.message);
    res.status(500).json({ error: 'Failed to submit audit event', detail: err.message });
  }
});

app.get('/audit/events', ensureConnected, async (_req, res) => {
  try {
    const results = await fabric.GetAllAuditEvents();
    res.json(results);
  } catch (err) {
    res.status(500).json({ error: 'Failed to list audit events', detail: err.message });
  }
});

app.get('/audit/events/:eventKey', ensureConnected, async (req, res) => {
  try {
    const result = await fabric.ReadAuditEvent(req.params.eventKey);
    res.json(result);
  } catch (err) {
    if (err.message.includes('not found')) {
      return res.status(404).json({ error: 'Audit event not found', eventKey: req.params.eventKey });
    }
    res.status(500).json({ error: 'Failed to read audit event', detail: err.message });
  }
});

app.get('/audit/applications/:applicationId/events', ensureConnected, async (req, res) => {
  try {
    const result = await fabric.GetApplicationAuditHistory(req.params.applicationId);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: 'Failed to get application audit history', detail: err.message });
  }
});

app.get('/audit/applications/:applicationId/timeline', ensureConnected, async (req, res) => {
  try {
    const result = await fabric.GetApplicationTimeline(req.params.applicationId);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: 'Failed to get application timeline', detail: err.message });
  }
});

app.get('/audit/applications/:applicationId/field-changes', ensureConnected, async (req, res) => {
  try {
    const result = await fabric.GetFieldChangeHistory(req.params.applicationId);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: 'Failed to get field change history', detail: err.message });
  }
});

app.get('/audit/applications/:applicationId/state', ensureConnected, async (req, res) => {
  try {
    const result = await fabric.GetCurrentApplicationState(req.params.applicationId);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: 'Failed to get application state', detail: err.message });
  }
});

app.get('/audit/applications/:applicationId/verify-chain', ensureConnected, async (req, res) => {
  try {
    const result = await fabric.VerifyAuditHashChain(req.params.applicationId);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: 'Failed to verify hash chain', detail: err.message });
  }
});

app.get('/audit/applications/:applicationId/verify-integrity', ensureConnected, async (req, res) => {
  try {
    const result = await fabric.VerifyBlockchainIntegrity(req.params.applicationId);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: 'Failed to verify integrity', detail: err.message });
  }
});

app.get('/audit/by-service/:service', ensureConnected, async (req, res) => {
  try {
    const result = await fabric.GetEventsByService(req.params.service);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: 'Failed to get events by service', detail: err.message });
  }
});

app.get('/audit/by-user/:userId', ensureConnected, async (req, res) => {
  try {
    const result = await fabric.GetEventsByUser(req.params.userId);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: 'Failed to get events by user', detail: err.message });
  }
});

app.get('/audit/by-correlation/:correlationId', ensureConnected, async (req, res) => {
  try {
    const result = await fabric.GetEventsByCorrelationId(req.params.correlationId);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: 'Failed to get events by correlation id', detail: err.message });
  }
});

app.get('/audit/by-date', ensureConnected, async (req, res) => {
  try {
    const startDate = req.query.start;
    const endDate = req.query.end;
    if (!startDate || !endDate) {
      return res.status(400).json({ error: 'start and end query params required' });
    }
    const result = await fabric.GetEventsByDate(startDate, endDate);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: 'Failed to get events by date', detail: err.message });
  }
});

app.post('/audit/verify-evidence/:eventKey', ensureConnected, async (req, res) => {
  try {
    const evidenceHash = req.body.evidenceHash;
    if (!evidenceHash) {
      return res.status(400).json({ error: 'evidenceHash is required in body' });
    }
    const result = await fabric.VerifyEvidence(req.params.eventKey, evidenceHash);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: 'Failed to verify evidence', detail: err.message });
  }
});

app.get('/audit/statistics', ensureConnected, async (_req, res) => {
  try {
    const result = await fabric.GetAuditStatistics();
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: 'Failed to get audit statistics', detail: err.message });
  }
});

app.get('/audit/block/:blockNumber', ensureConnected, async (req, res) => {
  try {
    const result = await fabric.GetBlockMetadata(req.params.blockNumber);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: 'Failed to get block metadata', detail: err.message });
  }
});

app.get('/audit/transaction/:transactionId', ensureConnected, async (req, res) => {
  try {
    const result = await fabric.GetTransactionMetadata(req.params.transactionId);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: 'Failed to get transaction metadata', detail: err.message });
  }
});

app.get('/health/live', (_req, res) => {
  res.json({ status: 'alive', service: 'fabric-adapter', version: '2.0.0' });
});

app.get('/health/ready', async (_req, res) => {
  try {
    const ready = await fabric.isNetworkReady();
    if (ready) {
      res.json({ status: 'ready', channel: config.CHANNEL_NAME, chaincode: config.CHAINCODE_NAME });
    } else {
      res.status(503).json({ status: 'not_ready' });
    }
  } catch (err) {
    res.status(503).json({ status: 'error', detail: err.message });
  }
});

app.get('/health', async (_req, res) => {
  try {
    const ready = await fabric.isNetworkReady();
    res.json({
      status: ready ? 'ready' : 'not_ready',
      channel: config.CHANNEL_NAME,
      chaincode: config.CHAINCODE_NAME,
      peer: config.getPeerEndpoint(),
    });
  } catch (err) {
    res.status(503).json({ status: 'error', detail: err.message });
  }
});

app.listen(config.PORT, () => {
  console.log(`Fabric adapter v2.0.0 listening on port ${config.PORT}`);
  console.log(`Channel: ${config.CHANNEL_NAME}, Chaincode: ${config.CHAINCODE_NAME}`);
});

process.on('SIGTERM', async () => { await fabric.close(); process.exit(0); });
process.on('SIGINT', async () => { await fabric.close(); process.exit(0); });
