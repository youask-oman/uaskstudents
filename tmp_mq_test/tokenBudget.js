"use strict";
/**
 * Token Budget Configuration
 *
 * Central configuration for token limits and budgets used in the solve flow.
 * These values help prevent token overflow errors when sending requests to OpenAI.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.MATH_HEAVY_THRESHOLDS = exports.MIN_QUESTION_MARKS_FOR_WARNING = exports.MULTI_QUESTION_PATTERNS = exports.CONTEXT_SAFETY_MARGIN = exports.CURRENT_MODEL = exports.MODEL_CONTEXT_LIMITS = void 0;
exports.getModelContextLimit = getModelContextLimit;
exports.willRequestFit = willRequestFit;
// ============================================================================
// REQUEST BUDGET
// ============================================================================
/**
 * Estimated tokens used by system prompt + JSON schema
 * This includes the solver system prompt and structured output schema
 */
/**
 * Expected output tokens for a typical solution
 * Solutions can include steps, explanations, visuals, etc.
 */
// ============================================================================
// MODEL CONTEXT LIMITS
// ============================================================================
/**
 * Model context limits (tokens)
 * Keep these updated as models change
 */
exports.MODEL_CONTEXT_LIMITS = {
    'gpt-4o': 128000,
    'gpt-5-mini': 128000,
    'gpt-4-turbo': 128000,
    'gpt-4': 8192,
    'gpt-3.5-turbo': 16385,
    'default': 16385, // Safe default
};
/** Current model being used (can be overridden by env) */
exports.CURRENT_MODEL = process.env.NEXT_PUBLIC_OPENAI_MODEL || 'gpt-5-mini';
/** Get context limit for current model */
function getModelContextLimit() {
    return exports.MODEL_CONTEXT_LIMITS[exports.CURRENT_MODEL] || exports.MODEL_CONTEXT_LIMITS['default'];
}
// ============================================================================
// SAFETY MARGINS
// ============================================================================
/**
 * Safety margin multiplier (0.9 = use only 90% of context)
 * This prevents edge cases where estimates are slightly off
 */
exports.CONTEXT_SAFETY_MARGIN = 0.9;
/**
 * Calculate if a request will fit within the model's context
 */
function willRequestFit(inputTokens, policy) {
    const limit = getModelContextLimit();
    const safeLimit = Math.floor(limit * exports.CONTEXT_SAFETY_MARGIN);
    const estimatedTotal = policy.systemAndSchemaBudget + inputTokens + policy.expectedOutputBudget;
    return {
        fits: estimatedTotal <= safeLimit,
        estimatedTotal,
        limit: safeLimit,
        headroom: safeLimit - estimatedTotal,
    };
}
// ============================================================================
// MULTI-QUESTION DETECTION PATTERNS
// ============================================================================
/** Patterns that indicate multiple questions */
exports.MULTI_QUESTION_PATTERNS = [
    /\bQ\d{1,3}\b/gi, // Q1, Q2, ... Q12
    /^\s*\d{1,3}[.)]\s*/gm, // 1), 2), ... 12)
    /^\s*\([a-e]\)\s*/gm, // (a), (b), etc.
    /^\s*[a-e]\)\s*/gm, // a), b), etc.
    /\balso\s+(?:find|solve|calculate|compute)/gi,
    /\bthen\s+(?:find|solve|calculate|compute)/gi,
    /\bnext\s+(?:find|solve|calculate|compute)/gi,
];
/** Minimum question marks to trigger multi-question warning */
exports.MIN_QUESTION_MARKS_FOR_WARNING = 2;
// ============================================================================
// MATH-HEAVY DETECTION THRESHOLDS
// ============================================================================
/**
 * Thresholds for detecting math-heavy content
 * If 2+ conditions are met, content is considered math-heavy
 */
exports.MATH_HEAVY_THRESHOLDS = {
    /** Minimum LaTeX command count (\frac, \sqrt, etc.) */
    latexCommands: 2,
    /** Minimum operator count (= + - * / < > ≤ ≥) */
    operators: 5,
    /** Minimum digit count */
    digits: 10,
    /** Minimum parentheses count */
    parentheses: 6,
    /** Minimum lines with equation patterns */
    equationLines: 2,
};
