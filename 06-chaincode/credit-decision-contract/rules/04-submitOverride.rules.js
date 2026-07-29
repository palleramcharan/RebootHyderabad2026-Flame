'use strict';

class SubmitOverrideRule {
  validate(decision, overrideApproved, overrideReason, overrideBy) {
    const errors = [];

    if (!decision) {
      errors.push('decision object is required');
      return { valid: false, errors };
    }

    if (typeof overrideApproved !== 'boolean') {
      errors.push('overrideApproved is required and must be a boolean');
    }

    return { valid: errors.length === 0, errors };
  }

  execute(ctx, decision, overrideApproved, overrideReason, overrideBy) {
    decision.overrideApproved = overrideApproved;
    decision.status = overrideApproved ? 'OVERRIDE_APPROVED' : 'OVERRIDE_REJECTED';

    decision.addTransaction('TX004', overrideApproved ? 'COMPLETED' : 'REJECTED', {
      action: 'SUBMIT_OVERRIDE',
      overrideApproved,
      overrideReason: overrideReason || '',
      overrideBy: overrideBy || 'SYSTEM',
    });

    decision.currentStep = 'TX005';
    return decision;
  }
}

module.exports = SubmitOverrideRule;
