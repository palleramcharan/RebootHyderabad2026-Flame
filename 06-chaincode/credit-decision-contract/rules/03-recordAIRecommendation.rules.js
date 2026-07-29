'use strict';

class RecordAIRecommendationRule {
  validate(decision, recommendedAmount, confidenceScore, recommendationReason) {
    const errors = [];

    if (!decision) {
      errors.push('decision object is required');
      return { valid: false, errors };
    }

    if (recommendedAmount == null || typeof recommendedAmount !== 'number' || recommendedAmount < 0) {
      errors.push('recommendedAmount is required and must be a non-negative number');
    }

    if (confidenceScore == null || typeof confidenceScore !== 'number') {
      errors.push('confidenceScore is required and must be a number');
    }

    if (confidenceScore < 0 || confidenceScore > 1) {
      errors.push('confidenceScore must be between 0 and 1');
    }

    if (!recommendationReason || typeof recommendationReason !== 'string') {
      errors.push('recommendationReason is required and must be a string');
    }

    return { valid: errors.length === 0, errors };
  }

  execute(ctx, decision, recommendedAmount, confidenceScore, recommendationReason, modelVersion) {
    decision.aiRecommendation = { recommendedAmount, confidenceScore, recommendationReason, modelVersion };
    decision.status = 'AI_REVIEWED';

    decision.addTransaction('TX003', 'COMPLETED', {
      action: 'RECORD_AI_RECOMMENDATION',
      recommendedAmount,
      confidenceScore,
      modelVersion: modelVersion || 'v2.1',
    });

    decision.currentStep = 'TX004';
    return decision;
  }
}

module.exports = RecordAIRecommendationRule;
