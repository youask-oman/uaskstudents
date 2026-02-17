/**
 * Token Budget Configuration
 *
 * Central configuration for token limits and budgets used in the solve flow.
 * These values help prevent token overflow errors when sending requests.
 */

export interface TokenBudgetPolicy {
    textInputMax: number;
    textInputMaxChars: number;
    systemAndSchemaBudget: number;
    expectedOutputBudget: number;
}

/**
 * Model context limits (tokens)
 * Keep these updated as models change.
 */
export const FIXED_OPENAI_MODEL = "gpt-5-mini" as const;

export const MODEL_CONTEXT_LIMITS: Record<string, number> = {
    [FIXED_OPENAI_MODEL]: 128000,
    default: 8192,
};

const ENV_OPENAI_MODEL = (
    process.env.OPENAI_MODEL_DEFAULT ||
    process.env.NEXT_PUBLIC_OPENAI_MODEL ||
    FIXED_OPENAI_MODEL
).trim();

/** Current model pulled from env and validated against the fixed runtime model. */
export const CURRENT_MODEL =
    ENV_OPENAI_MODEL === FIXED_OPENAI_MODEL ? ENV_OPENAI_MODEL : FIXED_OPENAI_MODEL;

/** Get context limit for current model */
export function getModelContextLimit(): number {
    return MODEL_CONTEXT_LIMITS[CURRENT_MODEL] || MODEL_CONTEXT_LIMITS.default;
}

/**
 * Safety margin multiplier (0.9 = use only 90% of context)
 */
export const CONTEXT_SAFETY_MARGIN = 0.9;

/**
 * Calculate if a request will fit within the model's context.
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
