/**
 * Token Estimation Utility
 * 
 * Fast, client-side token estimation for math/text content.
 * Uses heuristics to estimate token count without requiring the actual tokenizer.
 */

import { MATH_HEAVY_THRESHOLDS } from './tokenBudget';

// ============================================================================
// TYPES
// ============================================================================

export interface TokenEstimate {
    /** Estimated token count */
    tokens: number;
    /** Whether content was detected as math-heavy */
    mode: 'normal' | 'mathHeavy';
    /** Character count */
    chars: number;
    /** Breakdown of detection signals */
    signals: {
        latexCommands: number;
        operators: number;
        digits: number;
        parentheses: number;
        equationLines: number;
    };
}

// ============================================================================
// DETECTION PATTERNS
// ============================================================================

/** LaTeX command patterns */
const LATEX_PATTERNS = [
    /\\frac/g,
    /\\sqrt/g,
    /\\begin/g,
    /\\end/g,
    /\\sum/g,
    /\\prod/g,
    /\\int/g,
    /\\lim/g,
    /\\log/g,
    /\\sin|\\cos|\\tan/g,
    /\\alpha|\\beta|\\gamma|\\delta|\\theta|\\pi/g,
    /\\infty/g,
    /\\pm/g,
    /\\times|\\div/g,
    /\\cdot/g,
    /\\leq|\\geq|\\neq/g,
    /\\left|\\right/g,
    /\\\[|\\\]/g,
    /\\\(|\\\)/g,
];

/** Math operator pattern */
const OPERATOR_PATTERN = /[=+\-*/×÷<>≤≥≠^_{}]/g;

/** Digit pattern */
const DIGIT_PATTERN = /\d/g;

/** Parentheses pattern */
const PAREN_PATTERN = /[()[\]{}]/g;

/** Equation-like line pattern (contains = with stuff on both sides) */
const EQUATION_LINE_PATTERN = /^.*\w.*=.*\w.*$/;

// ============================================================================
// MAIN ESTIMATION FUNCTION
// ============================================================================

/**
 * Estimate token count for input text
 * 
 * Uses character-based heuristics with adjustments for math-heavy content.
 * 
 * Normal text: ~4 chars per token
 * Math-heavy: ~2.5 chars per token (math symbols often tokenize inefficiently)
 * 
 * @param text - Input text to estimate
 * @returns TokenEstimate with count, mode, and signal breakdown
 */
export function estimateTokens(text: string): TokenEstimate {
    const chars = text.length;

    if (chars === 0) {
        return {
            tokens: 0,
            mode: 'normal',
            chars: 0,
            signals: { latexCommands: 0, operators: 0, digits: 0, parentheses: 0, equationLines: 0 },
        };
    }

    // Count signals
    const signals = {
        latexCommands: countLatexCommands(text),
        operators: (text.match(OPERATOR_PATTERN) || []).length,
        digits: (text.match(DIGIT_PATTERN) || []).length,
        parentheses: (text.match(PAREN_PATTERN) || []).length,
        equationLines: countEquationLines(text),
    };

    // Determine if math-heavy (2+ thresholds exceeded)
    let triggersExceeded = 0;
    if (signals.latexCommands >= MATH_HEAVY_THRESHOLDS.latexCommands) triggersExceeded++;
    if (signals.operators >= MATH_HEAVY_THRESHOLDS.operators) triggersExceeded++;
    if (signals.digits >= MATH_HEAVY_THRESHOLDS.digits) triggersExceeded++;
    if (signals.parentheses >= MATH_HEAVY_THRESHOLDS.parentheses) triggersExceeded++;
    if (signals.equationLines >= MATH_HEAVY_THRESHOLDS.equationLines) triggersExceeded++;

    const isMathHeavy = triggersExceeded >= 2;

    // Calculate token estimate
    // Normal: ~4 chars/token, Math-heavy: ~2.5 chars/token
    const charsPerToken = isMathHeavy ? 2.5 : 4;
    const tokens = Math.ceil(chars / charsPerToken);

    return {
        tokens,
        mode: isMathHeavy ? 'mathHeavy' : 'normal',
        chars,
        signals,
    };
}

/**
 * Count LaTeX commands in text
 */
function countLatexCommands(text: string): number {
    let count = 0;
    for (const pattern of LATEX_PATTERNS) {
        const matches = text.match(pattern);
        if (matches) count += matches.length;
    }
    // Also check for basic LaTeX markers
    if (text.includes('\\')) count += 1;
    if (text.includes('^') && text.includes('_')) count += 1;
    return count;
}

/**
 * Count lines that look like equations
 */
function countEquationLines(text: string): number {
    const lines = text.split('\n');
    let count = 0;
    for (const line of lines) {
        if (EQUATION_LINE_PATTERN.test(line.trim())) {
            count++;
        }
    }
    return count;
}

// ============================================================================
// QUICK VALIDATION FUNCTIONS
// ============================================================================

/**
 * Quick check if input exceeds token limit
 */
export function isInputTooLong(text: string, maxTokens: number = 1000): boolean {
    const estimate = estimateTokens(text);
    return estimate.tokens > maxTokens;
}

/**
 * Get a user-friendly status message for token estimate
 */
export function getTokenStatus(estimate: TokenEstimate, maxTokens: number = 1000): {
    status: 'ok' | 'warning' | 'error';
    message: string;
    percentage: number;
} {
    const percentage = Math.round((estimate.tokens / maxTokens) * 100);

    if (estimate.tokens > maxTokens) {
        return {
            status: 'error',
            message: 'Input too long. Please split into smaller parts.',
            percentage: Math.min(percentage, 150),
        };
    }

    if (percentage > 80) {
        return {
            status: 'warning',
            message: 'Approaching token limit. Consider splitting.',
            percentage,
        };
    }

    return {
        status: 'ok',
        message: '',
        percentage,
    };
}
