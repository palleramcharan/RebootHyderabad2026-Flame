'use strict';

class RecordRuleExecutionRule {
  validate(decision, creditScore, creditLimit, riskCategory) {
    const errors = [];

    if (!decision) {
      errors.push('decision object is required');
      return { valid: false, errors };
    }

    if (creditScore == null || typeof creditScore !== 'number') {
      errors.push('creditScore is required and must be a number');
    }

    if (creditScore < 300 || creditScore > 900) {
      errors.push('creditScore must be between 300 and 900');
    }

    if (!riskCategory || typeof riskCategory !== 'string') {
      errors.push('riskCategory is required and must be a string');
    }

    const validCategories = ['LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH'];
    if (!validCategories.includes(riskCategory)) {
      errors.push(`riskCategory must be one of: ${validCategories.join(', ')}`);
    }

    return { valid: errors.length === 0, errors };
  }

  execute(ctx, decision, creditScore, creditLimit, riskCategory, ruleEngineVersion) {
    decision.creditScore = creditScore;
    decision.creditLimit = creditLimit;
    decision.riskCategory = riskCategory;
    decision.status = 'RULE_EXECUTED';

    decision.addTransaction('TX002', 'COMPLETED', {
      action: 'RECORD_RULE_EXECUTION',
      creditScore,
      creditLimit,
      riskCategory,
      ruleEngineVersion: ruleEngineVersion || 'v1.0',
    });

    decision.currentStep = 'TX003';
    return decision;
  }
}

module.exports = RecordRuleExecutionRule;
