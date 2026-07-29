'use strict';

const crypto = require('crypto');

class AuditEvent {
  constructor(fields = {}) {
    this.auditId = fields.auditId || '';
    this.applicationId = fields.applicationId || '';
    this.submissionId = fields.submissionId || '';
    this.correlationId = fields.correlationId || '';
    this.businessEvent = fields.businessEvent || '';
    this.workflowStep = fields.workflowStep || '';
    this.service = fields.service || '';
    this.operation = fields.operation || '';
    this.userId = fields.userId || '';
    this.timestamp = fields.timestamp || new Date().toISOString();
    this.eventCategory = fields.eventCategory || 'AUDIT';
    this.eventSeverity = fields.eventSeverity || 'INFO';
    this.sequence = fields.sequence || 0;
    this.eventVersion = fields.eventVersion || '1.0';
    this.currentHash = fields.currentHash || '';
    this.previousHash = fields.previousHash || '';
    this.evidenceHash = fields.evidenceHash || '';
    this.transactionId = fields.transactionId || '';
    this.blockNumber = fields.blockNumber || 0;
    this.channelName = fields.channelName || '';
    this.mspId = fields.mspId || '';
    this.eventKey = fields.eventKey || '';
    this.changedFields = fields.changedFields || [];
    this.metadata = fields.metadata || {};
  }

  computeHash() {
    const sortedFields = this.changedFields.map(f => {
      const keys = Object.keys(f).sort();
      const o = {};
      for (const k of keys) o[k] = f[k];
      return o;
    });
    const data = [
      this.applicationId,
      this.businessEvent,
      this.timestamp,
      this.evidenceHash,
      this.correlationId,
      JSON.stringify(sortedFields),
      String(this.sequence),
    ].join('|');
    return crypto.createHash('sha256').update(data).digest('hex');
  }

  validate() {
    const errors = [];
    if (!this.auditId) errors.push('auditId is required');
    if (!this.applicationId) errors.push('applicationId is required');
    if (!this.submissionId) errors.push('submissionId is required');
    if (!this.correlationId) errors.push('correlationId is required');
    if (!this.businessEvent) errors.push('businessEvent is required');
    if (!this.service) errors.push('service is required');
    if (!this.userId) errors.push('userId is required');
    if (!this.timestamp) errors.push('timestamp is required');
    if (!this.evidenceHash) errors.push('evidenceHash is required');
    if (!this.currentHash) errors.push('currentHash is required');
    if (!this.mspId) errors.push('mspId is required');
    return { valid: errors.length === 0, errors };
  }

  static fromBuffer(buffer) {
    return new AuditEvent(JSON.parse(buffer.toString()));
  }

  toBuffer() {
    return Buffer.from(JSON.stringify(this));
  }
}

module.exports = AuditEvent;
