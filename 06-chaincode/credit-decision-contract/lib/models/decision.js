'use strict';

class TransactionEntry {
  constructor(type, status, timestamp, details = {}) {
    this.type = type;
    this.status = status;
    this.timestamp = timestamp || new Date().toISOString();
    this.details = details;
  }
}

class Decision {
  constructor(applicationId, applicantName, productType, requestedAmount, currency) {
    this.applicationId = applicationId;
    this.applicantName = applicantName;
    this.productType = productType;
    this.requestedAmount = requestedAmount;
    this.currency = currency || 'USD';
    this.status = 'DRAFT';
    this.currentStep = 'TX001';
    this.transactions = [];
    this.creditScore = null;
    this.aiRecommendation = null;
    this.overrideApproved = false;
    this.finalApproved = false;
    this.disbursementCompleted = false;
    this.createdAt = new Date().toISOString();
    this.updatedAt = this.createdAt;
  }

  addTransaction(type, status, details = {}) {
    const entry = new TransactionEntry(type, status, new Date().toISOString(), details);
    this.transactions.push(entry);
    this.updatedAt = entry.timestamp;
    return entry;
  }

  static fromBuffer(buffer) {
    return JSON.parse(buffer.toString());
  }

  static deserialize(data) {
    const decision = Object.assign(new Decision(), data);
    decision.transactions = data.transactions || [];
    return decision;
  }

  toBuffer() {
    return Buffer.from(JSON.stringify(this));
  }
}

module.exports = { Decision, TransactionEntry };
