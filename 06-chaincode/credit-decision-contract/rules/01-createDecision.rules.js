'use strict';

class CreateDecisionRule {
  validate(applicationId, applicantName, productType, requestedAmount) {
    const errors = [];

    if (!applicationId || typeof applicationId !== 'string') {
      errors.push('applicationId is required and must be a string');
    }

    if (!applicantName || typeof applicantName !== 'string') {
      errors.push('applicantName is required and must be a string');
    }

    if (!productType || typeof productType !== 'string') {
      errors.push('productType is required and must be a string');
    }

    if (requestedAmount == null || typeof requestedAmount !== 'number' || requestedAmount <= 0) {
      errors.push('requestedAmount is required and must be a positive number');
    }

    return { valid: errors.length === 0, errors };
  }

  execute(ctx, decision) {
    decision.status = 'DRAFT';
    decision.addTransaction('TX001', 'COMPLETED', {
      action: 'CREATE_DECISION',
      message: `Decision created for ${decision.applicantName}`,
    });
    decision.currentStep = 'TX002';
    return decision;
  }
}

module.exports = CreateDecisionRule;
