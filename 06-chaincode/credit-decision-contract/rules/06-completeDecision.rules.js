'use strict';

class CompleteDecisionRule {
  validate(decision, bookingReference, disbursementAccount) {
    const errors = [];

    if (!decision) {
      errors.push('decision object is required');
      return { valid: false, errors };
    }

    if (!bookingReference || typeof bookingReference !== 'string') {
      errors.push('bookingReference is required and must be a string');
    }

    if (!disbursementAccount || typeof disbursementAccount !== 'string') {
      errors.push('disbursementAccount is required and must be a string');
    }

    return { valid: errors.length === 0, errors };
  }

  execute(ctx, decision, bookingReference, disbursementAccount, disbursementAmount) {
    decision.bookingReference = bookingReference;
    decision.disbursementAccount = disbursementAccount;
    decision.disbursementAmount = disbursementAmount || decision.approvalAmount;
    decision.disbursementCompleted = true;
    decision.status = 'COMPLETED';
    decision.currentStep = 'COMPLETED';

    decision.addTransaction('TX006', 'COMPLETED', {
      action: 'COMPLETE_DECISION',
      bookingReference,
      disbursementAccount,
      disbursementAmount: decision.disbursementAmount,
    });

    return decision;
  }
}

module.exports = CompleteDecisionRule;
