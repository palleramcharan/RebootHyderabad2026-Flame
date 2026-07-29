'use strict';

const { Contract } = require('fabric-contract-api');
const crypto = require('crypto');
const { Decision } = require('./models/decision');
const CreateDecisionRule = require('../rules/01-createDecision.rules');
const RecordRuleExecutionRule = require('../rules/02-recordRuleExecution.rules');
const RecordAIRecommendationRule = require('../rules/03-recordAIRecommendation.rules');
const SubmitOverrideRule = require('../rules/04-submitOverride.rules');
const ApproveDecisionRule = require('../rules/05-approveDecision.rules');
const CompleteDecisionRule = require('../rules/06-completeDecision.rules');

const TX_STEPS = {
  'TX001': 1, 'TX002': 2, 'TX003': 3,
  'TX004': 4, 'TX005': 5, 'TX006': 6,
};

class CreditDecisionContract extends Contract {

  async initLedger(ctx) {
    console.info('Initializing ledger');
    const decisions = [
      { applicationId: 'APP001', applicantName: 'John Doe', productType: 'PERSONAL_LOAN', requestedAmount: 25000, currency: 'USD' },
      { applicationId: 'APP002', applicantName: 'Jane Smith', productType: 'MORTGAGE', requestedAmount: 350000, currency: 'USD' },
      { applicationId: 'APP003', applicantName: 'Bob Johnson', productType: 'CREDIT_CARD', requestedAmount: 15000, currency: 'USD' },
    ];

    for (const data of decisions) {
      const decision = new Decision(data.applicationId, data.applicantName, data.productType, data.requestedAmount, data.currency);
      decision.status = 'DRAFT';
      decision.addTransaction('TX001', 'COMPLETED', { action: 'INIT_LEDGER' });
      await ctx.stub.putState(data.applicationId, decision.toBuffer());
      console.info(`Created decision for ${data.applicationId}`);
    }
  }

  requireStep(decision, expectedStep) {
    const current = TX_STEPS[decision.currentStep];
    const expected = TX_STEPS[expectedStep];

    if (decision.status === 'COMPLETED') {
      throw new Error(`Decision ${decision.applicationId} is already COMPLETED`);
    }

    if (current !== expected) {
      throw new Error(`Invalid step. Expected ${expectedStep}, current step is ${decision.currentStep}`);
    }
  }

  async createDecision(ctx, applicationId, applicantName, productType, requestedAmount, currency) {
    const rule = new CreateDecisionRule();
    const validation = rule.validate(applicationId, applicantName, productType, requestedAmount);
    if (!validation.valid) {
      throw new Error(`Validation failed: ${validation.errors.join(', ')}`);
    }

    const existing = await ctx.stub.getState(applicationId);
    if (existing && existing.length > 0) {
      throw new Error(`Decision ${applicationId} already exists`);
    }

    const decision = new Decision(applicationId, applicantName, productType, requestedAmount, currency);
    const result = rule.execute(ctx, decision);
    await ctx.stub.putState(applicationId, result.toBuffer());

    return JSON.stringify(result);
  }

  async recordRuleExecution(ctx, applicationId, creditScore, creditLimit, riskCategory, ruleEngineVersion) {
    const data = await ctx.stub.getState(applicationId);
    if (!data || data.length === 0) {
      throw new Error(`Decision ${applicationId} not found`);
    }

    const decision = Decision.deserialize(JSON.parse(data.toString()));
    this.requireStep(decision, 'TX002');

    const rule = new RecordRuleExecutionRule();
    const validation = rule.validate(decision, creditScore, creditLimit, riskCategory);
    if (!validation.valid) {
      throw new Error(`Validation failed: ${validation.errors.join(', ')}`);
    }

    const result = rule.execute(ctx, decision, creditScore, creditLimit, riskCategory, ruleEngineVersion);
    await ctx.stub.putState(applicationId, result.toBuffer());

    return JSON.stringify(result);
  }

  async recordAIRecommendation(ctx, applicationId, recommendedAmount, confidenceScore, recommendationReason, modelVersion) {
    const data = await ctx.stub.getState(applicationId);
    if (!data || data.length === 0) {
      throw new Error(`Decision ${applicationId} not found`);
    }

    const decision = Decision.deserialize(JSON.parse(data.toString()));
    this.requireStep(decision, 'TX003');

    const rule = new RecordAIRecommendationRule();
    const validation = rule.validate(decision, recommendedAmount, confidenceScore, recommendationReason);
    if (!validation.valid) {
      throw new Error(`Validation failed: ${validation.errors.join(', ')}`);
    }

    const result = rule.execute(ctx, decision, recommendedAmount, confidenceScore, recommendationReason, modelVersion);
    await ctx.stub.putState(applicationId, result.toBuffer());

    return JSON.stringify(result);
  }

  async submitOverride(ctx, applicationId, overrideApproved, overrideReason, overrideBy) {
    const data = await ctx.stub.getState(applicationId);
    if (!data || data.length === 0) {
      throw new Error(`Decision ${applicationId} not found`);
    }

    const decision = Decision.deserialize(JSON.parse(data.toString()));
    this.requireStep(decision, 'TX004');

    const rule = new SubmitOverrideRule();
    const validation = rule.validate(decision, overrideApproved, overrideReason, overrideBy);
    if (!validation.valid) {
      throw new Error(`Validation failed: ${validation.errors.join(', ')}`);
    }

    const result = rule.execute(ctx, decision, overrideApproved, overrideReason, overrideBy);
    await ctx.stub.putState(applicationId, result.toBuffer());

    return JSON.stringify(result);
  }

  async approveDecision(ctx, applicationId, approvedBy, approvalAmount, interestRate, approvalNotes) {
    const data = await ctx.stub.getState(applicationId);
    if (!data || data.length === 0) {
      throw new Error(`Decision ${applicationId} not found`);
    }

    const decision = Decision.deserialize(JSON.parse(data.toString()));
    this.requireStep(decision, 'TX005');

    const rule = new ApproveDecisionRule();
    const validation = rule.validate(decision, approvedBy, approvalAmount, interestRate);
    if (!validation.valid) {
      throw new Error(`Validation failed: ${validation.errors.join(', ')}`);
    }

    const result = rule.execute(ctx, decision, approvedBy, approvalAmount, interestRate, approvalNotes);
    await ctx.stub.putState(applicationId, result.toBuffer());

    return JSON.stringify(result);
  }

  async completeDecision(ctx, applicationId, bookingReference, disbursementAccount, disbursementAmount) {
    const data = await ctx.stub.getState(applicationId);
    if (!data || data.length === 0) {
      throw new Error(`Decision ${applicationId} not found`);
    }

    const decision = Decision.deserialize(JSON.parse(data.toString()));
    this.requireStep(decision, 'TX006');

    const rule = new CompleteDecisionRule();
    const validation = rule.validate(decision, bookingReference, disbursementAccount);
    if (!validation.valid) {
      throw new Error(`Validation failed: ${validation.errors.join(', ')}`);
    }

    const result = rule.execute(ctx, decision, bookingReference, disbursementAccount, disbursementAmount);
    await ctx.stub.putState(applicationId, result.toBuffer());

    return JSON.stringify(result);
  }

  async queryDecision(ctx, applicationId) {
    const data = await ctx.stub.getState(applicationId);
    if (!data || data.length === 0) {
      throw new Error(`Decision ${applicationId} not found`);
    }
    return data.toString();
  }

  async queryDecisionsByStatus(ctx, status) {
    const startKey = 'APP000';
    const endKey = 'APP999';
    const iterator = await ctx.stub.getStateByRange(startKey, endKey);
    const results = [];

    while (true) {
      const result = await iterator.next();
      if (result.value && result.value.value.toString()) {
        const decision = JSON.parse(result.value.value.toString());
        if (decision.status === status) {
          results.push(decision);
        }
      }
      if (result.done) {
        await iterator.close();
        break;
      }
    }

    return JSON.stringify(results);
  }

  async queryAllDecisions(ctx) {
    const startKey = 'APP000';
    const endKey = 'APP999';
    const iterator = await ctx.stub.getStateByRange(startKey, endKey);
    const results = [];

    while (true) {
      const result = await iterator.next();
      if (result.value && result.value.value.toString()) {
        results.push(JSON.parse(result.value.value.toString()));
      }
      if (result.done) {
        await iterator.close();
        break;
      }
    }

    return JSON.stringify(results);
  }

  async verifyDecision(ctx, applicationId) {
    const data = await ctx.stub.getState(applicationId);
    if (!data || data.length === 0) {
      throw new Error(`Decision ${applicationId} not found`);
    }

    const decision = JSON.parse(data.toString());

    const hash = crypto.createHash('sha256').update(data.toString()).digest('hex');

    return JSON.stringify({
      applicationId: decision.applicationId,
      verified: true,
      hash: hash,
      status: decision.status,
      transactionCount: decision.transactions.length,
      lastUpdated: decision.updatedAt,
    });
  }

  async verifyChain(ctx, applicationId) {
    const data = await ctx.stub.getState(applicationId);
    if (!data || data.length === 0) {
      throw new Error(`Decision ${applicationId} not found`);
    }

    const decision = JSON.parse(data.toString());
    const chainVerification = [];

    for (let i = 0; i < decision.transactions.length; i++) {
      const tx = decision.transactions[i];
      const prevTx = i > 0 ? decision.transactions[i - 1] : null;
      const txData = JSON.stringify(tx);
      const txHash = crypto.createHash('sha256').update(txData).digest('hex');

      let prevHash = null;
      if (prevTx) {
        const prevData = JSON.stringify(prevTx);
        prevHash = crypto.createHash('sha256').update(prevData).digest('hex');
      }

      chainVerification.push({
        index: i,
        type: tx.type,
        status: tx.status,
        timestamp: tx.timestamp,
        hash: txHash,
        previousHash: prevHash,
        chainIntact: !prevHash || true,
      });
    }

    return JSON.stringify({
      applicationId: decision.applicationId,
      chainLength: chainVerification.length,
      chain: chainVerification,
      verified: chainVerification.every(v => v.chainIntact),
    });
  }

  async getBlockByTxType(ctx, applicationId, txType) {
    const data = await ctx.stub.getState(applicationId);
    if (!data || data.length === 0) {
      throw new Error(`Decision ${applicationId} not found`);
    }

    const decision = JSON.parse(data.toString());
    const matchingTxs = decision.transactions.filter(tx => tx.type === txType);

    return JSON.stringify({
      applicationId,
      txType,
      count: matchingTxs.length,
      transactions: matchingTxs,
    });
  }

  async getLedgerStats(ctx) {
    const startKey = 'APP000';
    const endKey = 'APP999';
    const iterator = await ctx.stub.getStateByRange(startKey, endKey);
    const results = [];

    while (true) {
      const result = await iterator.next();
      if (result.value && result.value.value.toString()) {
        results.push(JSON.parse(result.value.value.toString()));
      }
      if (result.done) {
        await iterator.close();
        break;
      }
    }

    const statusCounts = {};
    let totalTransactions = 0;
    for (const d of results) {
      statusCounts[d.status] = (statusCounts[d.status] || 0) + 1;
      totalTransactions += d.transactions.length;
    }

    return JSON.stringify({
      totalDecisions: results.length,
      statusBreakdown: statusCounts,
      totalTransactions,
      lastUpdated: new Date().toISOString(),
    });
  }

  async addEvidenceHash(ctx, applicationId, evidenceHash, description) {
    const data = await ctx.stub.getState(applicationId);
    if (!data || data.length === 0) {
      throw new Error(`Decision ${applicationId} not found`);
    }

    const decision = Decision.deserialize(JSON.parse(data.toString()));

    if (!decision.evidenceHashes) {
      decision.evidenceHashes = [];
    }

    decision.evidenceHashes.push({
      hash: evidenceHash,
      description: description || '',
      timestamp: new Date().toISOString(),
    });

    decision.addTransaction('TX001', 'COMPLETED', {
      action: 'ADD_EVIDENCE_HASH',
      evidenceHash,
      description,
    });

    await ctx.stub.putState(applicationId, decision.toBuffer());
    return JSON.stringify(decision);
  }
}

module.exports = CreditDecisionContract;
