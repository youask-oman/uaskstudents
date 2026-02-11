/**
 * Token Budget Configuration
 * 
 * Central configuration for token limits and budgets used in the solve flow.
 * These values help prevent token overflow errors when sending requests to OpenAI.
 */

// ============================================================================
// INPUT LIMITS
// ============================================================================

export interface TokenBudgetPolicy {
    textInputMax: number;
    textInputMaxChars: number;
    systemAndSchemaBudget: number;
    expectedOutputBudget: number;
}

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
export const MODEL_CONTEXT_LIMITS: Record<string, number> = {
    'gpt-4o': 128000,
    'gpt-5-mini': 128000,
    'gpt-4-turbo': 128000,
    'gpt-4': 8192,
    'gpt-3.5-turbo': 16385,
    'default': 16385, // Safe default
};

/** Current model being used (can be overridden by env) */
export const CURRENT_MODEL = process.env.NEXT_PUBLIC_OPENAI_MODEL || 'gpt-5-mini';

/** Get context limit for current model */
export function getModelContextLimit(): number {
    return MODEL_CONTEXT_LIMITS[CURRENT_MODEL] || MODEL_CONTEXT_LIMITS['default'];
}

// ============================================================================
// SAFETY MARGINS
// ============================================================================

/** 
 * Safety margin multiplier (0.9 = use only 90% of context)
 * This prevents edge cases where estimates are slightly off
 */
export const CONTEXT_SAFETY_MARGIN = 0.9;

/**
 * Calculate if a request will fit within the model's context
 */
export function willRequestFit(inputTokens: number, policy: TokenBudgetPolicy): {
    fits: boolean;
    estimatedTotal: number;
    limit: number;
    headroom: number;
} {
    const limit = getModelContextLimit();
    const safeLimit = Math.floor(limit * CONTEXT_SAFETY_MARGIN);
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
export const MULTI_QUESTION_PATTERNS = [
    /\bQ[12345]\b/gi,           // Q1, Q2, etc.
    /^\s*[12345]\)\s*/gm,       // 1), 2), etc.
    /^\s*\([a-e]\)\s*/gm,       // (a), (b), etc.
    /^\s*[a-e]\)\s*/gm,         // a), b), etc.
    /\balso\s+(?:find|solve|calculate|compute)/gi,
    /\bthen\s+(?:find|solve|calculate|compute)/gi,
    /\bnext\s+(?:find|solve|calculate|compute)/gi,
];

/** Minimum question marks to trigger multi-question warning */
export const MIN_QUESTION_MARKS_FOR_WARNING = 2;

// ============================================================================
// MATH-HEAVY DETECTION THRESHOLDS
// ============================================================================

/** 
 * Thresholds for detecting math-heavy content
 * If 2+ conditions are met, content is considered math-heavy
 */
export const MATH_HEAVY_THRESHOLDS = {
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
