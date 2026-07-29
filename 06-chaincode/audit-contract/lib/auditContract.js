'use strict';

const { Contract } = require('fabric-contract-api');
const AuditEvent = require('./models/auditEvent');

class AuditContract extends Contract {

  async CreateAuditEvent(ctx, auditEventJson) {
    const data = JSON.parse(auditEventJson);

    // Resolve previousHash from the last committed event for this application
    const appId = data.applicationId;
    const currentSequence = parseInt(data.sequence) || 0;
    let previousHash = '';
    if (appId && currentSequence > 0) {
      try {
        const historyJson = await this.GetApplicationAuditHistory(ctx, appId);
        const history = JSON.parse(historyJson);
        const prevEvents = history.filter(e => (parseInt(e.sequence) || 0) < currentSequence);
        if (prevEvents.length > 0) {
          previousHash = prevEvents[prevEvents.length - 1].currentHash || '';
        }
      } catch (_) {
        // No prior events — start a new hash chain
      }
    }
    data.previousHash = previousHash;

    const event = new AuditEvent(data);
    event.currentHash = event.computeHash();

    const validation = event.validate();
    if (!validation.valid) {
      throw new Error(`Audit event validation failed: ${validation.errors.join('; ')}`);
    }

    const eventKey = `AUDIT-${event.auditId}-${ctx.stub.getTxID()}`;
    event.eventKey = eventKey;
    event.transactionId = ctx.stub.getTxID();

    const existing = await ctx.stub.getState(eventKey);
    if (existing && existing.length > 0) {
      throw new Error(`Duplicate event key: ${eventKey}`);
    }

    await ctx.stub.putState(eventKey, event.toBuffer());

    return JSON.stringify({
      eventKey,
      auditId: event.auditId,
      currentHash: event.currentHash,
      previousHash: event.previousHash,
      txId: ctx.stub.getTxID(),
      status: 'COMMITTED',
    });
  }

  async ReadAuditEvent(ctx, eventKey) {
    const data = await ctx.stub.getState(eventKey);
    if (!data || data.length === 0) {
      throw new Error(`Audit event not found: ${eventKey}`);
    }
    return data.toString();
  }

  async GetApplicationAuditHistory(ctx, applicationId) {
    const query = { selector: { applicationId }, use_index: ['_design/applicationId', 'applicationId'] };
    const iterator = await ctx.stub.getQueryResult(JSON.stringify(query));
    const results = [];
    while (true) {
      const res = await iterator.next();
      if (res.value && res.value.value && res.value.value.toString()) {
        results.push(JSON.parse(res.value.value.toString()));
      }
      if (res.done) {
        await iterator.close();
        break;
      }
    }
    results.sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
    return JSON.stringify(results);
  }

  async GetApplicationTimeline(ctx, applicationId) {
    const events = JSON.parse(await this.GetApplicationAuditHistory(ctx, applicationId));
    const timeline = [];
    for (const evt of events) {
      timeline.push({
        auditId: evt.auditId,
        businessEvent: evt.businessEvent,
        workflowStep: evt.workflowStep,
        service: evt.service,
        timestamp: evt.timestamp,
        sequence: evt.sequence,
        currentHash: evt.currentHash,
        previousHash: evt.previousHash,
        transactionId: evt.transactionId,
        eventKey: evt.eventKey,
      });
    }
    return JSON.stringify(timeline);
  }

  async GetFieldChangeHistory(ctx, applicationId) {
    const events = JSON.parse(await this.GetApplicationAuditHistory(ctx, applicationId));
    const changes = [];
    for (const evt of events) {
      if (evt.changedFields && evt.changedFields.length > 0) {
        changes.push({
          auditId: evt.auditId,
          businessEvent: evt.businessEvent,
          service: evt.service,
          timestamp: evt.timestamp,
          changedFields: evt.changedFields,
          transactionId: evt.transactionId,
        });
      }
    }
    return JSON.stringify(changes);
  }

  async GetEventsByApplication(ctx, applicationId) {
    return await this.GetApplicationAuditHistory(ctx, applicationId);
  }

  async GetEventsByService(ctx, service) {
    const query = { selector: { service }, use_index: ['_design/service', 'service'] };
    return await this._queryAll(ctx, query);
  }

  async GetEventsByUser(ctx, userId) {
    const query = { selector: { userId }, use_index: ['_design/userId', 'userId'] };
    return await this._queryAll(ctx, query);
  }

  async GetEventsByDate(ctx, startDate, endDate) {
    const query = {
      selector: {
        timestamp: { $gte: startDate, $lte: endDate },
      },
    };
    return await this._queryAll(ctx, query);
  }

  async GetEventsByCorrelationId(ctx, correlationId) {
    const query = { selector: { correlationId } };
    return await this._queryAll(ctx, query);
  }

  async VerifyEvidence(ctx, eventKey, expectedEvidenceHash) {
    const data = await ctx.stub.getState(eventKey);
    if (!data || data.length === 0) {
      return JSON.stringify({ eventKey, exists: false, verified: false, reason: 'Event not found' });
    }
    const event = JSON.parse(data.toString());
    const verified = event.evidenceHash === expectedEvidenceHash;
    return JSON.stringify({
      eventKey,
      exists: true,
      verified,
      storedEvidenceHash: event.evidenceHash,
      providedEvidenceHash: expectedEvidenceHash,
      applicationId: event.applicationId,
      service: event.service,
      timestamp: event.timestamp,
    });
  }

  async VerifyAuditHashChain(ctx, applicationId) {
    const events = JSON.parse(await this.GetApplicationAuditHistory(ctx, applicationId));
    const results = [];
    for (let i = 0; i < events.length; i++) {
      const evt = events[i];
      const expectedPrevHash = i === 0 ? '' : events[i - 1].currentHash;
      const prevMatch = evt.previousHash === expectedPrevHash;
      const recalc = new AuditEvent(evt);
      const hashMatch = recalc.computeHash() === evt.currentHash;
      results.push({
        sequence: evt.sequence,
        auditId: evt.auditId,
        eventKey: evt.eventKey,
        previousHashMatch: prevMatch,
        currentHashMatch: hashMatch,
        storedPreviousHash: evt.previousHash,
        expectedPreviousHash: expectedPrevHash,
      });
    }
    const chainIntact = results.every(r => r.previousHashMatch && r.currentHashMatch);
    return JSON.stringify({ applicationId, chainIntact, eventCount: events.length, entries: results });
  }

  async VerifyBlockchainIntegrity(ctx, applicationId) {
    const events = JSON.parse(await this.GetApplicationAuditHistory(ctx, applicationId));
    const results = [];
    for (const evt of events) {
      const txId = evt.transactionId;
      const eventKey = evt.eventKey;
      results.push({
        auditId: evt.auditId,
        eventKey,
        transactionId: txId,
        blockNumber: evt.blockNumber,
      });
    }
    return JSON.stringify({ applicationId, eventCount: results.length, entries: results });
  }

  async GetCurrentApplicationState(ctx, applicationId) {
    const events = JSON.parse(await this.GetApplicationAuditHistory(ctx, applicationId));
    if (events.length === 0) {
      return JSON.stringify({ applicationId, exists: false });
    }
    const latest = events[events.length - 1];
    return JSON.stringify({
      applicationId,
      exists: true,
      latestAuditId: latest.auditId,
      latestService: latest.service,
      latestBusinessEvent: latest.businessEvent,
      latestTimestamp: latest.timestamp,
      latestTransactionId: latest.transactionId,
      latestBlockNumber: latest.blockNumber,
      currentHash: latest.currentHash,
      previousHash: latest.previousHash,
      totalEvents: events.length,
    });
  }

  async GetAuditStatistics(ctx) {
    const iterator = await ctx.stub.getStateByRange('', '');
    const stats = {
      totalEvents: 0,
      byService: {},
      byEventCategory: {},
      bySeverity: {},
      byApplication: {},
      latestTimestamp: null,
    };
    while (true) {
      const res = await iterator.next();
      if (res.value && res.value.value && res.value.value.toString()) {
        try {
          const evt = JSON.parse(res.value.value.toString());
          stats.totalEvents++;
          stats.byService[evt.service] = (stats.byService[evt.service] || 0) + 1;
          stats.byEventCategory[evt.eventCategory] = (stats.byEventCategory[evt.eventCategory] || 0) + 1;
          stats.bySeverity[evt.eventSeverity] = (stats.bySeverity[evt.eventSeverity] || 0) + 1;
          stats.byApplication[evt.applicationId] = (stats.byApplication[evt.applicationId] || 0) + 1;
          if (!stats.latestTimestamp || evt.timestamp > stats.latestTimestamp) {
            stats.latestTimestamp = evt.timestamp;
          }
        } catch (_) {}
      }
      if (res.done) {
        await iterator.close();
        break;
      }
    }
    return JSON.stringify(stats);
  }

  async GetBlockMetadata(ctx, blockNumber) {
    const block = await ctx.stub.getBlockByNumber(parseInt(blockNumber));
    return JSON.stringify({
      blockNumber: blockNumber,
      dataHash: block.header.data_hash.toString('hex'),
      previousHash: block.header.previous_hash.toString('hex'),
      txCount: block.data.data.length,
      txIds: block.data.data.map(tx => tx.payload.header.channel_header.tx_id),
    });
  }

  async GetTransactionMetadata(ctx, transactionId) {
    const tx = await ctx.stub.getTransactionByID(transactionId);
    if (!tx) {
      return JSON.stringify({ transactionId, found: false });
    }
    return JSON.stringify({
      transactionId,
      found: true,
      validationCode: tx.validation_code,
      timestamp: tx.payload.header.channel_header.timestamp,
      channelId: tx.payload.header.channel_header.channel_id,
      type: tx.payload.header.channel_header.type,
    });
  }

  async AuditEventExists(ctx, eventKey) {
    const data = await ctx.stub.getState(eventKey);
    return JSON.stringify({ exists: !!(data && data.length > 0) });
  }

  async GetAllAuditEvents(ctx) {
    const startKey = '';
    const endKey = '';
    const iterator = await ctx.stub.getStateByRange(startKey, endKey);
    const results = [];
    while (true) {
      const res = await iterator.next();
      if (res.value && res.value.value && res.value.value.toString()) {
        const event = JSON.parse(res.value.value.toString());
        event.eventKey = res.value.key;
        results.push(event);
      }
      if (res.done) {
        await iterator.close();
        break;
      }
    }
    return JSON.stringify(results);
  }

  async _queryAll(ctx, query) {
    const iterator = await ctx.stub.getQueryResult(JSON.stringify(query));
    const results = [];
    while (true) {
      const res = await iterator.next();
      if (res.value && res.value.value && res.value.value.toString()) {
        results.push(JSON.parse(res.value.value.toString()));
      }
      if (res.done) {
        await iterator.close();
        break;
      }
    }
    return JSON.stringify(results);
  }
}

module.exports = AuditContract;
