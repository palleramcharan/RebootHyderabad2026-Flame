'use strict';

class ApproveDecisionRule {
  validate(decision, approvedBy, approvalAmount, interestRate) {
    const errors = [];

    if (!decision) {
      errors.push('decision object is required');
      return { valid: false, errors };
    }

    if (!approvedBy || typeof approvedBy !== 'string') {
      errors.push('approvedBy is required and must be a string');
    }

    if (approvalAmount == null || typeof approvalAmount !== 'number' || approvalAmount <= 0) {
      errors.push('approvalAmount is required and must be a positive number');
    }

    if (interestRate == null || typeof interestRate !== 'number' || interestRate < 0) {
      errors.push('interestRate is required and must be a non-negative number');
    }

    return { valid: errors.length === 0, errors };
  }

  execute(ctx, decision, approvedBy, approvalAmount, interestRate, approvalNotes) {
    decision.finalApproved = true;
    decision.approvedBy = approvedBy;
    decision.approvalAmount = approvalAmount;
    decision.interestRate = interestRate;
    decision.approvalNotes = approvalNotes || '';
    decision.status = 'APPROVED';

    decision.addTransaction('TX005', 'COMPLETED', {
      action: 'APPROVE_DECISION',
      approvedBy,
      approvalAmount,
      interestRate,
    });

    decision.currentStep = 'TX006';
    return decision;
  }
}

module.exports = ApproveDecisionRule;
